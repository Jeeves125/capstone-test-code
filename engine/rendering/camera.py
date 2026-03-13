from ..math.transform import Transform
from ..constants.constants import PROGRAM
from .overlay import Overlay
import numpy as np, math
from pyrr import Matrix44

def create_view_matrix() -> np.ndarray:
  """
  Create a view matrix using the look-at approach.
  This ensures the camera rotates around its own position.
  """
  camera = Camera.active

  # Get camera position
  eye = camera.transform.position

  # Calculate forward, right, and up vectors based on camera rotation
  # Forward vector (negative Z in camera space)
  right, up, forward = camera.transform.get_basis_vectors()
  
  # Create the look-at matrix
  # This is equivalent to: translate(-eye) * rotate_to_view_space
  view_matrix = np.array([
      [right.x, up.x, -forward.x, 0],
      [right.y, up.y, -forward.y, 0], 
      [right.z, up.z, -forward.z, 0],
      [-right.x * eye.x - right.y * eye.y - right.z * eye.z,
        -up.x * eye.x - up.y * eye.y - up.z * eye.z,
        forward.x * eye.x + forward.y * eye.y + forward.z * eye.z, 1]
  ], dtype=np.float32)
  
  return view_matrix

def create_projection_matrix() -> np.ndarray:
    # Lazy import to avoid circular dependency at module import time
    camera = Camera.active

    aspect_ratio = None
    if camera.aspect_ratio is None:
        try:
            # Import only when needed, after engine/constants are initialized
            from ..constants.constants import WIDTH, HEIGHT
            aspect_ratio = WIDTH / HEIGHT
        except Exception:
            # Fallback if constants not available yet
            aspect_ratio = 1.0

    fov_rad = math.radians(camera.fov)
    f = 1.0 / math.tan(fov_rad / 2.0)
    
    # Column-major format for ModernGL
    return np.array([
        [f/aspect_ratio,  0,  0,                          0],
        [0,               f,  0,                          0],
        [0,               0,  -(camera.far+camera.near)/(camera.far-camera.near),    -1],
        [0,               0,  -(2*camera.far*camera.near)/(camera.far-camera.near),   0]
    ], dtype=np.float32)

class Camera:
    active = None

    def __init__(self):
        self.transform = Transform()
        self.fov = 45.0  # Field of view in degrees
        self.near = 0.1
        self.far = 1000.0
        self.aspect_ratio = None  # If None, will use engine's WIDTH/HEIGHT when creating projection matrix
        self.overlay: Overlay = None
        if Camera.active is None:
            Camera.active = self

    def set_active(self):
        Camera.active = self
        PROGRAM['projection'].write(create_projection_matrix().tobytes())