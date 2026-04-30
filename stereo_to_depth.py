import numpy as np
import cv2 as cv
from matplotlib import pyplot as plt

# Set both values from camera calibration to get real depth in meters.
FOCAL_LENGTH_PX = None
BASELINE_M = None


def load_images(left_path: str, right_path: str) -> tuple[np.ndarray, np.ndarray]:
	img_l = cv.imread(left_path, cv.IMREAD_GRAYSCALE)
	img_r = cv.imread(right_path, cv.IMREAD_GRAYSCALE)
	if img_l is None or img_r is None:
		raise FileNotFoundError("Could not load IMG_L.jpg or IMG_R.jpg")
	if img_l.shape != img_r.shape:
		raise ValueError("Left and right images must have the same resolution")
	return img_l, img_r


def preprocess(img: np.ndarray) -> np.ndarray:
	# CLAHE improves local contrast and tends to help matching on low-texture regions.
	clahe = cv.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
	out = clahe.apply(img)
	out = cv.GaussianBlur(out, (5, 5), 0)
	return out


def auto_rectify(img_l: np.ndarray, img_r: np.ndarray) -> tuple[np.ndarray, np.ndarray, bool]:
	orb = cv.ORB_create(nfeatures=3000)
	kp_l, des_l = orb.detectAndCompute(img_l, None)
	kp_r, des_r = orb.detectAndCompute(img_r, None)

	if des_l is None or des_r is None:
		return img_l, img_r, False

	matcher = cv.BFMatcher(cv.NORM_HAMMING)
	knn = matcher.knnMatch(des_l, des_r, k=2)

	good = []
	for m, n in knn:
		if m.distance < 0.75 * n.distance:
			good.append(m)

	if len(good) < 20:
		return img_l, img_r, False

	pts_l = np.float32([kp_l[m.queryIdx].pt for m in good])
	pts_r = np.float32([kp_r[m.trainIdx].pt for m in good])

	f_mat, mask = cv.findFundamentalMat(pts_l, pts_r, cv.FM_RANSAC, 1.0, 0.99)
	if f_mat is None or mask is None:
		return img_l, img_r, False

	pts_l_in = pts_l[mask.ravel() == 1]
	pts_r_in = pts_r[mask.ravel() == 1]

	if len(pts_l_in) < 16:
		return img_l, img_r, False

	ok, h_l, h_r = cv.stereoRectifyUncalibrated(pts_l_in, pts_r_in, f_mat, img_l.shape[::-1])
	if not ok:
		return img_l, img_r, False

	rect_l = cv.warpPerspective(img_l, h_l, img_l.shape[::-1])
	rect_r = cv.warpPerspective(img_r, h_r, img_r.shape[::-1])
	return rect_l, rect_r, True


def compute_disparity(img_l: np.ndarray, img_r: np.ndarray) -> np.ndarray:
	# numDisparities must be divisible by 16.
	# Use a wider dynamic range to avoid clipping near the disparity ceiling.
	width = img_l.shape[1]
	num_disp = max(16 * 8, ((width // 6) // 16) * 16)
	num_disp = min(num_disp, 16 * 16)
	block_size = 5

	stereo_left = cv.StereoSGBM.create(
		minDisparity=0,
		numDisparities=num_disp,
		blockSize=block_size,
		P1=8 * block_size * block_size,
		P2=32 * block_size * block_size,
		disp12MaxDiff=1,
		uniquenessRatio=10,
		speckleWindowSize=120,
		speckleRange=2,
		preFilterCap=63,
		mode=cv.STEREO_SGBM_MODE_SGBM_3WAY,
	)

	disp_left_raw = stereo_left.compute(img_l, img_r)

	# If contrib modules are available, refine with WLS for cleaner depth maps.
	if hasattr(cv, "ximgproc") and hasattr(cv.ximgproc, "createRightMatcher"):
		stereo_right = cv.ximgproc.createRightMatcher(stereo_left)
		disp_right_raw = stereo_right.compute(img_r, img_l)
		wls = cv.ximgproc.createDisparityWLSFilter(stereo_left)
		wls.setLambda(8000.0)
		wls.setSigmaColor(1.5)
		disp_left_raw = wls.filter(disp_left_raw, img_l, disparity_map_right=disp_right_raw)

	disparity_raw = disp_left_raw.astype(np.float32) / 16.0

	# Mark non-positive disparities as invalid (cannot estimate depth reliably).
	disparity_raw[disparity_raw <= 0.0] = np.nan

	max_disp = float(num_disp - 1)
	if np.nanpercentile(disparity_raw, 99) >= max_disp - 1.0:
		print(f"Warning: disparity is near max range ({max_disp}). Increase numDisparities if needed.")

	return disparity_raw


def postprocess_disparity(disparity: np.ndarray) -> np.ndarray:
	valid = np.isfinite(disparity)
	if not np.any(valid):
		raise RuntimeError("No valid disparity pixels found. Check stereo alignment/rectification.")

	# Fill invalid points with local median for filtering, then restore mask after filtering.
	median_val = float(np.nanmedian(disparity))
	filled = np.where(valid, disparity, median_val).astype(np.float32)
	filled = cv.medianBlur(filled, 5)

	# Remove tiny isolated islands in the valid mask.
	mask_u8 = valid.astype(np.uint8) * 255
	mask_u8 = cv.morphologyEx(mask_u8, cv.MORPH_OPEN, np.ones((3, 3), np.uint8))
	mask_u8 = cv.morphologyEx(mask_u8, cv.MORPH_CLOSE, np.ones((5, 5), np.uint8))
	filled[mask_u8 == 0] = np.nan

	return filled


def disparity_to_display(disparity: np.ndarray) -> np.ndarray:
	valid = np.isfinite(disparity)
	if not np.any(valid):
		raise RuntimeError("No valid disparity to display")

	d_min = np.nanpercentile(disparity, 2)
	d_max = np.nanpercentile(disparity, 98)
	clipped = np.clip(disparity, d_min, d_max)
	disp_norm = (clipped - d_min) / max(d_max - d_min, 1e-6)
	disp_norm[~valid] = 0.0
	return (disp_norm * 255).astype(np.uint8)


def disparity_to_depth_m(disparity: np.ndarray, focal_px: float, baseline_m: float) -> np.ndarray:
	depth = (focal_px * baseline_m) / disparity
	depth[~np.isfinite(disparity)] = np.nan
	depth[depth <= 0] = np.nan
	return depth


def main() -> None:
	img_l, img_r = load_images("IMG_L.jpg", "IMG_R.jpg")

	img_l, img_r, rectified = auto_rectify(img_l, img_r)
	print(f"Auto-rectification: {'ON' if rectified else 'OFF'}")

	# For best results images should be rectified using camera calibration.
	img_l_pre = preprocess(img_l)
	img_r_pre = preprocess(img_r)

	disparity = compute_disparity(img_l_pre, img_r_pre)
	disparity_filtered = postprocess_disparity(disparity)
	disparity_vis = disparity_to_display(disparity_filtered)

	depth_m = None
	if FOCAL_LENGTH_PX is not None and BASELINE_M is not None:
		depth_m = disparity_to_depth_m(disparity_filtered, FOCAL_LENGTH_PX, BASELINE_M)
		print("Depth mode: calibrated meters")
	else:
		print("Depth mode: disparity only (set FOCAL_LENGTH_PX and BASELINE_M for metric depth)")

	plt.figure(figsize=(16, 5))
	plt.subplot(1, 4, 1)
	plt.title("Left")
	plt.imshow(img_l, cmap="gray")
	plt.axis("off")

	plt.subplot(1, 4, 2)
	plt.title("Right")
	plt.imshow(img_r, cmap="gray")
	plt.axis("off")

	plt.subplot(1, 4, 3)
	plt.title("Disparity (filtered)")
	plt.imshow(disparity_vis, cmap="magma")
	plt.axis("off")

	plt.subplot(1, 4, 4)
	if depth_m is None:
		plt.title("Depth unavailable")
		plt.imshow(np.zeros_like(disparity_vis), cmap="gray")
	else:
		depth_clip = np.clip(depth_m, np.nanpercentile(depth_m, 2), np.nanpercentile(depth_m, 98))
		plt.title("Depth (m)")
		plt.imshow(depth_clip, cmap="viridis")
	plt.axis("off")

	plt.tight_layout()
	plt.show()


if __name__ == "__main__":
	main()