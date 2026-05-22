"""
Stereo Depth Map with Camera Calibration
Uses pre-calibrated camera parameters for improved depth map accuracy.
"""

import argparse

import cv2
import numpy as np
import pickle
import os
import json
import csv
import time

import pygame
from stereo_depth import StereoDepthMapper

class CalibratedStereoDepthMapper():
    def __init__(self, width=640, height=480, calibration_file='stereo_calibration_refined'):
        """Initialize with calibration support."""
        
        self.stereo = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=16*8,  # must be divisible by 16
            blockSize=7,
            P1=8*3*7**2,
            P2=32*3*7**2,
            disp12MaxDiff=1,
            uniquenessRatio=12,
            speckleWindowSize=150,
            speckleRange=2,
            preFilterCap=63,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
        )
        
        # For visualization: closest = white, furthest = black
        self.depth_colormap = None
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self.temporal_depth = None
        self.orientation_checked = False
        self.swap_inputs = False
        
        self.left_calibration = None
        self.right_calibration = None
        
        self.left_map1, self.left_map2 = None, None
        self.right_map1, self.right_map2 = None, None
        self.stereo_calibration = None
        # Advanced post-processing / filters
        self.use_ximgproc = False
        self.right_matcher = None
        self.wls_filter = None
        try:
            import cv2.ximgproc as ximgproc
            # create a right matcher and WLS filter to improve disparity quality
            self.right_matcher = ximgproc.createRightMatcher(self.stereo)
            self.wls_filter = ximgproc.createDisparityWLSFilter(self.stereo)
            # reasonable defaults; user can tune
            self.wls_filter.setLambda(8000.0)
            self.wls_filter.setSigmaColor(1.5)
            self.use_ximgproc = True
            print("ximgproc available: WLS + L-R check enabled")
        except Exception:
            # ximgproc not available (opencv-contrib missing)
            self.use_ximgproc = False
        # Advanced options to improve close-range mapping
        self.use_roi_crop = True
        self.roi = None  # (x, y, w, h) of overlapping rectified area
        self.use_guided_filter = False
        self.guided_filter = None
        try:
            if self.use_ximgproc:
                # guided filter uses ximgproc if available
                self.guided_filter = ximgproc.createGuidedFilter(cv2.cvtColor(np.zeros((10,10,3),dtype=np.uint8), cv2.COLOR_BGR2GRAY), 5, 1.0)
                self.use_guided_filter = True
        except Exception:
            self.use_guided_filter = False

        # Caps for adaptive numDisparities
        self.max_num_disparities = 16 * 20
        self.min_num_disparities = 16 * 4
        self.adaptive_expand_step = 16 * 2
        # runtime flags
        self.diagnostics_enabled = True
        self.tuned_params = None
        self.tuned_params_path = 'stereo_tuned_params.json'
        # Try to load previously tuned params
        self.load_tuned_params()
        # Metric depth display options
        self.metric_display_enabled = False
        self.metric_display_max_m = 5.0  # default display scale (meters)
        # Ensemble matching and temporal options
        self.ensemble_enabled = False
        self.ensemble_block_sizes = [5,7,9]
        self.temporal_median_enabled = False
        self.temporal_median_buffer = []
        self.temporal_median_size = 5
        
        # Prefer full stereo calibration (rectification maps) if available
        stereo_file = f"{calibration_file}.pkl"
        if os.path.exists(stereo_file):
            try:
                with open(stereo_file, 'rb') as f:
                    self.stereo_calibration = pickle.load(f)
                # use maps from stereo calibration
                self.left_map1 = self.stereo_calibration.get('left_map1')
                self.left_map2 = self.stereo_calibration.get('left_map2')
                self.right_map1 = self.stereo_calibration.get('right_map1')
                self.right_map2 = self.stereo_calibration.get('right_map2')
                print('Loaded stereo calibration and rectification maps from', stereo_file)
            except Exception as e:
                print('Failed to load stereo calibration:', e)
    
    def load_calibration(self, camera_id):
        """Load calibration data for a camera."""
        filename = f"camera_{camera_id}_calibration.pkl"
        
        if not os.path.exists(filename):
            return None, None
        
        try:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
            return data['camera_matrix'], data['dist_coeffs']
        except:
            return None, None
    
    def setup_rectification(self, width, height):
        """Setup undistortion maps using available monocular calibration data."""
        left_matrix, left_dist = self.left_calibration
        right_matrix, right_dist = self.right_calibration

        # We only have per-camera intrinsics/distortion from calibrate_cameras.py.
        # Build undistortion maps for each camera independently.
        left_new_matrix, _ = cv2.getOptimalNewCameraMatrix(
            left_matrix, left_dist, (width, height), 1, (width, height)
        )
        right_new_matrix, _ = cv2.getOptimalNewCameraMatrix(
            right_matrix, right_dist, (width, height), 1, (width, height)
        )

        self.left_map1, self.left_map2 = cv2.initUndistortRectifyMap(
            left_matrix, left_dist, np.eye(3), left_new_matrix, (width, height), cv2.CV_32F
        )

        self.right_map1, self.right_map2 = cv2.initUndistortRectifyMap(
            right_matrix, right_dist, np.eye(3), right_new_matrix, (width, height), cv2.CV_32F
        )
    
    def preprocess_frames(self, left, right):
        """Apply calibration/rectification and image preprocessing.

        Returns rectified, CLAHE-enhanced, and mildly blurred grayscale images.
        """
        left_gray = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        right_gray = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)

        # Apply rectification maps first (if available)
        if self.left_map1 is not None and self.right_map1 is not None:
            left_gray = cv2.remap(left_gray, self.left_map1, self.left_map2, cv2.INTER_LINEAR)
            right_gray = cv2.remap(right_gray, self.right_map1, self.right_map2, cv2.INTER_LINEAR)

            # Estimate overlapping ROI once to crop to common region (improves matching density)
            if self.use_roi_crop and self.roi is None:
                self._estimate_overlap_roi()

        # Improve local contrast to help block matching
        left_gray = self.clahe.apply(left_gray)
        right_gray = self.clahe.apply(right_gray)

        # Mild smoothing to reduce noise while preserving edges
        left_gray = cv2.GaussianBlur(left_gray, (3, 3), 0)
        right_gray = cv2.GaussianBlur(right_gray, (3, 3), 0)

        return left_gray, right_gray

    def _estimate_overlap_roi(self):
        """Estimate overlapping ROI between rectified left/right using remap of a mask.

        Sets `self.roi` to (x, y, w, h). If estimation fails, leaves `self.roi` as None.
        """
        try:
            h, w = self.left_map1.shape[:2]
            mask = np.ones((h, w), dtype=np.uint8) * 255
            left_m = cv2.remap(mask, self.left_map1, self.left_map2, cv2.INTER_NEAREST)
            right_m = cv2.remap(mask, self.right_map1, self.right_map2, cv2.INTER_NEAREST)
            both = cv2.bitwise_and(left_m, right_m)
            # find bounding rect of non-zero region
            ys, xs = np.where(both > 0)
            if ys.size and xs.size:
                x0, x1 = xs.min(), xs.max()
                y0, y1 = ys.min(), ys.max()
                # shrink a bit to avoid border artifacts
                pad = 8
                x0 = max(0, x0 + pad)
                y0 = max(0, y0 + pad)
                x1 = min(w - 1, x1 - pad)
                y1 = min(h - 1, y1 - pad)
                if x1 > x0 and y1 > y0:
                    self.roi = (x0, y0, x1 - x0, y1 - y0)
                    print(f"Estimated overlap ROI: {self.roi}")
        except Exception:
            self.roi = None

    def compute_depth(self, left_gray, right_gray):
        """Compute disparity with optional WLS filtering and left-right check.

        Returns (raw_disparity_16s, normalized_uint8_for_display)
        """
        # Optionally crop to overlapping ROI to focus matching where both images have data
        cropped = False
        roi = None
        if self.use_roi_crop and self.roi is not None:
            x, y, w, h = self.roi
            try:
                lg = left_gray[y:y+h, x:x+w]
                rg = right_gray[y:y+h, x:x+w]
                cropped = True
                roi = (x, y, w, h)
            except Exception:
                lg, rg = left_gray, right_gray
        else:
            lg, rg = left_gray, right_gray

        # Compute left disparity on (maybe) cropped images
        # Ensemble matching option: compute disparities with multiple block sizes and fuse
        if self.ensemble_enabled:
            # Rate-limit ensemble computation to avoid per-frame lag
            self._ensemble_counter = getattr(self, '_ensemble_counter', 0) + 1
            do_ensemble = (self._ensemble_counter % getattr(self, 'ensemble_interval', 1) == 0)
            if not do_ensemble and getattr(self, '_last_ensemble_disp', None) is not None:
                # reuse last ensemble result
                disp_left = self._last_ensemble_disp
            else:
                disp_list = []
                base_nd = int(self.stereo.getNumDisparities())
                # optionally downscale input for faster ensemble
                down = getattr(self, 'ensemble_downscale', 1.0)
                if down != 1.0:
                    small_l = cv2.resize(lg, (0,0), fx=down, fy=down, interpolation=cv2.INTER_LINEAR)
                    small_r = cv2.resize(rg, (0,0), fx=down, fy=down, interpolation=cv2.INTER_LINEAR)
                else:
                    small_l, small_r = lg, rg

                for bs in self.ensemble_block_sizes:
                    try:
                        P1 = 8 * 1 * bs * bs
                        P2 = 32 * 1 * bs * bs
                        stereo_tmp = cv2.StereoSGBM_create(
                            minDisparity=0,
                            numDisparities=base_nd,
                            blockSize=bs,
                            P1=P1,
                            P2=P2,
                            disp12MaxDiff=1,
                            uniquenessRatio=10,
                            speckleWindowSize=100,
                            speckleRange=2,
                            preFilterCap=63,
                            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
                        )
                        d = stereo_tmp.compute(small_l, small_r).astype(np.float32) / 16.0
                        # mask invalids as NaN so nanmedian ignores them (fast C implementation)
                        min_disp_tmp = float(stereo_tmp.getMinDisparity())
                        d_masked = np.where(d > min_disp_tmp, d, np.nan)
                        disp_list.append(d_masked)
                    except Exception:
                        continue

                if len(disp_list) == 0:
                    disp_left = self.stereo.compute(lg, rg)
                else:
                    stack = np.stack(disp_list, axis=2)
                    fused = np.nanmedian(stack, axis=2)
                    # replace NaN with a sentinel below min disparity
                    fused = np.nan_to_num(fused, nan=(float(self.stereo.getMinDisparity()) - 1.0))
                    if down != 1.0:
                        # upscale fused back to original ROI size
                        fused = cv2.resize(fused, (lg.shape[1], lg.shape[0]), interpolation=cv2.INTER_LINEAR)
                    disp_left = (fused * 16.0).astype(np.int16)
                # cache last ensemble disparity (as 16S int) to reuse on intermediate frames
                self._last_ensemble_disp = disp_left
        else:
            disp_left = self.stereo.compute(lg, rg)

        # If ximgproc available, compute right disparity and apply WLS
        if self.use_ximgproc and self.right_matcher is not None and self.wls_filter is not None:
            try:
                # compute right disparity on cropped images if used
                if cropped:
                    disp_right = self.right_matcher.compute(rg, lg)
                else:
                    disp_right = self.right_matcher.compute(right_gray, left_gray)
                # WLS expects CV_16S disparities
                if cropped:
                    filtered = self.wls_filter.filter(disp_left, lg, None, disp_right)
                else:
                    filtered = self.wls_filter.filter(disp_left, left_gray, None, disp_right)
                disparity = filtered.astype(np.float32) / 16.0
            except Exception:
                # Fallback to raw left disparity on error
                disparity = disp_left.astype(np.float32) / 16.0
        else:
            disparity = disp_left.astype(np.float32) / 16.0

        # Basic left-right consistency mask if we have a right disparity
        valid_mask = disparity > float(self.stereo.getMinDisparity())

        # Normalize using percentiles for robust contrast
        disparity_normalized = np.zeros(disparity.shape, dtype=np.uint8)
        if np.any(valid_mask):
            vals = disparity[valid_mask]
            low = float(np.percentile(vals, 5))
            high = float(np.percentile(vals, 95))
            if high <= low:
                low = float(vals.min())
                high = float(vals.max())
            if high > low:
                scaled = np.clip((disparity - low) / (high - low), 0.0, 1.0)
                disparity_normalized[valid_mask] = (scaled[valid_mask] * 255.0).astype(np.uint8)

        # Post-processing: median + morphological close to fill small holes
        disparity_normalized = cv2.medianBlur(disparity_normalized, 5)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        disparity_normalized = cv2.morphologyEx(disparity_normalized, cv2.MORPH_CLOSE, kernel)

        # Left-right consistency check (if right disparity computed)
        if self.use_ximgproc and 'disp_right' in locals():
            try:
                # Convert to float disparity (already /16 for filtered)
                # Simple consistency: compute disparity difference between left and reprojected right
                # Here we create a mask where abs(dL - dR) < 1.0
                dL = disparity
                dR = (disp_right.astype(np.float32) / 16.0)
                # Resize/align dR if cropping used
                if cropped:
                    # pad back to full image
                    full_dR = np.zeros_like(dL)
                    full_dR[:] = np.min(dR) - 1.0
                    # place dR into ROI
                    x, y, w, h = roi
                    full_dR[y:y+h, x:x+w] = dR
                    dR = full_dR
                # create consistency mask
                lr_mask = np.abs(dL - dR) < 1.0
                disparity_normalized[~lr_mask] = 0
            except Exception:
                pass

        # Temporal smoothing for video
        # Temporal smoothing for video: either exponential or median buffer
        if self.temporal_median_enabled:
            # append and keep buffer
            self.temporal_median_buffer.append(disparity_normalized.copy())
            if len(self.temporal_median_buffer) > self.temporal_median_size:
                self.temporal_median_buffer.pop(0)
            if len(self.temporal_median_buffer) > 0:
                stack = np.stack(self.temporal_median_buffer, axis=2)
                disparity_normalized = np.median(stack, axis=2).astype(np.uint8)
        else:
            if self.temporal_depth is None:
                self.temporal_depth = disparity_normalized.astype(np.float32)
            else:
                cv2.accumulateWeighted(disparity_normalized, self.temporal_depth, 0.2)
            disparity_normalized = cv2.convertScaleAbs(self.temporal_depth)

        return disp_left, disparity_normalized

    def disparity_to_depth_meters(self, disp16):
        """Convert raw disparity (int16, scale 16) to metric depth (meters).

        Prefers using stereo reprojection matrix `Q` if present in loaded
        `self.stereo_calibration`. Falls back to using `fx` and baseline `T`.
        Returns a float32 array with meters and NaN for invalid pixels.
        """
        disp = disp16.astype(np.float32) / 16.0
        min_disp = float(self.stereo.getMinDisparity())

        # Prepare depth array filled with NaN for invalids
        depth = np.full(disp.shape, np.nan, dtype=np.float32)

        # Use Q if available (best option)
        if self.stereo_calibration and isinstance(self.stereo_calibration, dict) and 'Q' in self.stereo_calibration:
            try:
                Q = self.stereo_calibration['Q']
                points3D = cv2.reprojectImageTo3D(disp, Q)
                depth = points3D[:, :, 2].astype(np.float32)
                depth[disp <= min_disp] = np.nan
                return depth
            except Exception:
                pass

        # Fallback: need fx from intrinsics and baseline from stereo 'T'
        if self.left_calibration[0] is not None and self.stereo_calibration and 'T' in self.stereo_calibration:
            try:
                fx = float(self.left_calibration[0][0, 0])
                T = np.array(self.stereo_calibration['T']).astype(np.float32)
                # baseline is translation along x between cameras
                baseline = abs(float(T[0]))
                # compute depth, avoid div by zero
                depth = (fx * baseline) / (disp + 1e-6)
                depth[disp <= min_disp] = np.nan
                return depth
            except Exception:
                pass

        raise RuntimeError("Need stereo Q or baseline+fx to compute metric depth.")

    def depth_to_colormap(self, depth_m, max_m=None):
        """Map a float32 depth map (meters) to a BGR colormap for display."""
        max_m = max_m or self.metric_display_max_m
        depth = depth_m.copy()
        invalid = ~np.isfinite(depth)
        depth[invalid] = 0.0
        norm = np.clip(depth / float(max_m), 0.0, 1.0)
        disp8 = (norm * 255.0).astype(np.uint8)
        disp8[invalid] = 0
        colored = cv2.applyColorMap(disp8, cv2.COLORMAP_JET)
        return colored

    def auto_tune_on_frame(self, left_gray, right_gray, try_block_sizes=(5,7,9), try_num_disparities=(16*6,16*8,16*10)):
        """Quick automatic tuning of StereoSGBM on a single frame.

        Tries combinations of `numDisparities` and `blockSize` and picks the
        configuration with the best score (valid_ratio - 0.05*std).
        """
        best_score = -1e9
        best_cfg = None
        best_disp = None
        # allow callers to pass custom search lists
        num_disparities_list = try_num_disparities if try_num_disparities is not None else (16*6, 16*8, 16*10)
        block_sizes = try_block_sizes if try_block_sizes is not None else (5,7,9)

        # prepare CSV log if requested
        log_csv = f"auto_tune_log_{int(time.time())}.csv"
        csv_writer = None
        csv_file = None
        try:
            csv_file = open(log_csv, 'w', newline='')
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(['numDisparities','blockSize','P1','P2','valid_ratio','std','score'])
        except Exception:
            csv_writer = None

        for numDisp in num_disparities_list:
            if numDisp % 16 != 0:
                continue
            for bs in block_sizes:
                if bs % 2 == 0:
                    continue
                P1 = 8 * 1 * bs * bs
                P2 = 32 * 1 * bs * bs
                stereo_tmp = cv2.StereoSGBM_create(
                    minDisparity=0,
                    numDisparities=numDisp,
                    blockSize=bs,
                    P1=P1,
                    P2=P2,
                    disp12MaxDiff=1,
                    uniquenessRatio=10,
                    speckleWindowSize=100,
                    speckleRange=2,
                    preFilterCap=63,
                    mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
                )
                disp = stereo_tmp.compute(left_gray, right_gray).astype(np.float32) / 16.0
                min_disp = float(stereo_tmp.getMinDisparity())
                valid = disp > min_disp
                if not np.any(valid):
                    continue
                vals = disp[valid]
                valid_ratio = float(np.mean(valid))
                std = float(np.std(vals))
                score = valid_ratio - 0.05 * std
                # log row
                if csv_writer is not None:
                    csv_writer.writerow([numDisp, bs, P1, P2, valid_ratio, std, score])
                if score > best_score:
                    best_score = score
                    best_cfg = (numDisp, bs, P1, P2)
                    best_disp = disp
        if csv_file is not None:
            try:
                csv_file.close()
            except Exception:
                pass

        # remember last log path for caller
        try:
            self.last_auto_tune_log = os.path.abspath(log_csv)
            print(f"Auto-tune log saved to: {self.last_auto_tune_log}")
        except Exception:
            self.last_auto_tune_log = log_csv

        if best_cfg is not None:
            numDisp, bs, P1, P2 = best_cfg
            # clamp to allowed range
            if numDisp < self.min_num_disparities:
                numDisp = self.min_num_disparities
            if numDisp > self.max_num_disparities:
                numDisp = self.max_num_disparities
            # apply new stereo settings
            self.stereo = cv2.StereoSGBM_create(
                minDisparity=0,
                numDisparities=numDisp,
                blockSize=bs,
                P1=P1,
                P2=P2,
                disp12MaxDiff=1,
                uniquenessRatio=10,
                speckleWindowSize=100,
                speckleRange=2,
                preFilterCap=63,
                mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
            )
            # re-create right matcher / WLS if available
            if self.use_ximgproc:
                try:
                    import cv2.ximgproc as ximgproc
                    self.right_matcher = ximgproc.createRightMatcher(self.stereo)
                    self.wls_filter = ximgproc.createDisparityWLSFilter(self.stereo)
                    self.wls_filter.setLambda(8000.0)
                    self.wls_filter.setSigmaColor(1.5)
                except Exception:
                    pass
            self.tuned_params = {'numDisparities': numDisp, 'blockSize': bs, 'P1': P1, 'P2': P2}
            print(f"Auto-tuned StereoSGBM -> numDisparities={numDisp}, blockSize={bs}")
            return True
        else:
            print("Auto-tune: no valid configuration found on this frame")
            return False

    def auto_tune_full(self, left_gray, right_gray):
        """Run an expanded auto-tune grid and save full CSV report.

        This explores numDisparities from 16*4 to 16*20 and blockSizes 3..13 odd.
        """
        num_list = tuple(range(16*4, 16*20 + 1, 16))
        blocks = tuple([3,5,7,9,11,13])
        print(f"Running full auto-tune: numDisparities={num_list}, blockSizes={blocks}")
        ok = self.auto_tune_on_frame(left_gray, right_gray, try_block_sizes=blocks, try_num_disparities=num_list)
        if ok:
            print(f"Full auto-tune complete. CSV: {getattr(self, 'last_auto_tune_log', 'unknown')}" )
        else:
            print(f"Full auto-tune finished with no valid config. CSV (partial): {getattr(self, 'last_auto_tune_log', 'unknown')}" )
        return ok

    def auto_tune_roi(self, left_gray, right_gray, size_frac=0.5, **kwargs):
        """ROI-focused auto-tune: center-crop the input frames and run auto_tune_on_frame.

        If tuning succeeds, store the ROI as `self.roi` so future matching uses it.
        """
        h, w = left_gray.shape[:2]
        sw = int(w * size_frac)
        sh = int(h * size_frac)
        cx = w // 2
        cy = h // 2
        x0 = max(0, cx - sw // 2)
        y0 = max(0, cy - sh // 2)
        x1 = min(w, x0 + sw)
        y1 = min(h, y0 + sh)
        lg = left_gray[y0:y1, x0:x1]
        rg = right_gray[y0:y1, x0:x1]
        print(f"Auto-tune ROI: ({x0},{y0}) - ({x1},{y1}) size {sw}x{sh}")
        ok = self.auto_tune_on_frame(lg, rg, **kwargs)
        if ok:
            self.roi = (x0, y0, x1 - x0, y1 - y0)
            print(f"Stored ROI for matching: {self.roi}")
        return ok

    def save_tuned_params(self, path=None):
        """Save tuned parameters to JSON file."""
        if self.tuned_params is None:
            print("No tuned parameters to save.")
            return False
        path = path or self.tuned_params_path
        try:
            with open(path, 'w') as f:
                json.dump(self.tuned_params, f, indent=2)
            print(f"Saved tuned parameters to {path}")
            return True
        except Exception as e:
            print("Failed to save tuned parameters:", e)
            return False

    def load_tuned_params(self, path=None):
        """Load tuned parameters from JSON and apply them if present."""
        path = path or getattr(self, 'tuned_params_path', 'stereo_tuned_params.json')
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            # Apply to stereo matcher
            nd = data.get('numDisparities')
            bs = data.get('blockSize')
            P1 = data.get('P1')
            P2 = data.get('P2')
            if nd and bs:
                self.stereo = cv2.StereoSGBM_create(
                    minDisparity=0,
                    numDisparities=nd,
                    blockSize=bs,
                    P1=P1 or 8*1*bs*bs,
                    P2=P2 or 32*1*bs*bs,
                    disp12MaxDiff=1,
                    uniquenessRatio=10,
                    speckleWindowSize=100,
                    speckleRange=2,
                    preFilterCap=63,
                    mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
                )
                if self.use_ximgproc:
                    try:
                        import cv2.ximgproc as ximgproc
                        self.right_matcher = ximgproc.createRightMatcher(self.stereo)
                        self.wls_filter = ximgproc.createDisparityWLSFilter(self.stereo)
                        self.wls_filter.setLambda(8000.0)
                        self.wls_filter.setSigmaColor(1.5)
                    except Exception:
                        pass
                self.tuned_params = data
                print(f"Loaded tuned parameters from {path}")
                return True
        except Exception as e:
            print("Failed to load tuned params:", e)
        return False
    
    def apply_colormap(self, disparity_normalized):
        """Render depth as grayscale: white (closest) to black (furthest)."""
        # disparity_normalized already maps larger disparity (closer) to higher intensity
        # Convert to BGR so downstream display stacking/saving stays unchanged.
        depth_gray = disparity_normalized
        depth_bgr = cv2.cvtColor(depth_gray, cv2.COLOR_GRAY2BGR)
        return depth_bgr

    def run(self, left_frame, right_frame, final_scale_factor=1.0):
        frame_count = 0
        diagnostics = self.diagnostics_enabled

        if left_frame is None or right_frame is None:
            print("Error reading frames. Got NONE")

        left_gray, right_gray = self.preprocess_frames(left_frame, right_frame)

        # Compute depth (returns raw 16S left disparity and display normalized)
        disp16, disp_display = self.compute_depth(left_gray, right_gray)

        # Diagnostics
        min_disp = float(disp16.min()) / 16.0
        max_disp = float(disp16.max()) / 16.0
        valid_ratio = float(np.mean(disp16.astype(np.float32) / 16.0 > float(self.stereo.getMinDisparity()))) * 100.0
        vals = (disp16.astype(np.float32) / 16.0)[(disp16.astype(np.float32) / 16.0) > float(self.stereo.getMinDisparity())]
        mean_disp = float(vals.mean()) if vals.size else 0.0
        std_disp = float(vals.std()) if vals.size else 0.0

        # Apply colormap (grayscale BGR)
        if self.metric_display_enabled:
            try:
                depth_m = self.disparity_to_depth_meters(disp16)
                depth_color = self.depth_to_colormap(depth_m)
            except Exception as e:
                print("Metric depth unavailable:", e)
                depth_color = self.apply_colormap(disp_display)
        else:
            depth_color = self.apply_colormap(disp_display)

        # Resize for display
        depth_display = cv2.resize(depth_color.tobytes(), (depth_color.shape[1] * final_scale_factor, depth_color.shape[0] * final_scale_factor), interpolation=cv2.INTER_NEAREST)
        
        surface = pygame.image.frombuffer(depth_display.tobytes(), depth_display.shape[1::-1], 'BGR')
        surface = surface.convert()
        return surface, {
            'min_disp': min_disp,
            'max_disp': max_disp,
            'valid_ratio': valid_ratio,
            'mean_disp': mean_disp,
            'std_disp': std_disp
        }

        # key = cv2.waitKey(1) & 0xFF
        # if key == ord('q'):
        #     break
        # elif key == ord('s'):
        #     filename = f"depth_map_{frame_count}.png"
        #     cv2.imwrite(filename, depth_color)
        #     print(f"Saved depth map as {filename}")
        # elif key == ord('t'):
        #     print("Running auto-tune on current frame...")
        #     ok = self.auto_tune_on_frame(left_gray, right_gray)
        #     if ok:
        #         print("Auto-tune applied — new matcher active.")
        # elif key == ord('T'):
        #     print("Running FULL auto-tune (expanded grid) on current frame... this may take a while")
        #     ok = self.auto_tune_full(left_gray, right_gray)
        #     if ok:
        #         print("Full auto-tune applied — new matcher active.")
        # elif key == ord('r'):
        #     print("Running ROI-focused auto-tune on current frame...")
        #     ok = self.auto_tune_roi(left_gray, right_gray, size_frac=0.5)
        #     if ok:
        #         print("ROI auto-tune applied — new matcher active.")
        # elif key == ord('p'):
        #     # persist tuned params
        #     saved = self.save_tuned_params()
        #     if saved:
        #         print("Tuned parameters persisted.")
        # elif key == ord('D'):
        #     self.metric_display_enabled = not self.metric_display_enabled
        #     print(f"Metric depth display {'enabled' if self.metric_display_enabled else 'disabled'} (scale={self.metric_display_max_m}m)")
        # elif key == ord('e'):
        #     self.ensemble_enabled = not self.ensemble_enabled
        #     print(f"Ensemble matching {'enabled' if self.ensemble_enabled else 'disabled'}")
        # elif key == ord('m'):
        #     self.temporal_median_enabled = not self.temporal_median_enabled
        #     print(f"Temporal median {'enabled' if self.temporal_median_enabled else 'disabled'} (size={self.temporal_median_size})")
        # elif key == ord('d'):
        #     diagnostics = not diagnostics

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calibrated Stereo Depth Mapping with OpenCV")
    parser.add_argument('--left_id', type=int, default=1, help='Camera ID for left camera (default: 1)')
    parser.add_argument('--right_id', type=int, default=2, help='Camera ID for right camera (default: 2)')
    parser.add_argument('--format', type=str, default='MJPG', help='Video format (default: MJPG)')
    parser.add_argument('--backend', type=str, default='v4l2', help='OpenCV video backend (default: v4l2)')
    args = parser.parse_args()
    mapper = CalibratedStereoDepthMapper(left_camera_id=args.left_id, right_camera_id=args.right_id, width=640, height=480, format=args.format, backend=args.backend)
    mapper.run()
