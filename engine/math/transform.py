from .float3 import Float3
from .float2 import Float2
import math
from pyrr import Quaternion
from pyrr import matrix44, Quaternion

class Transform:
    def __init__(self, position: Float3 = None, scale: Float3 = None):
        self.position = position if position is not None else Float3(0, 0, 0)
        # rotation around {} axis (x = pitch, y = yaw, z = roll)
        self.rotation = Quaternion() # in radians
        self.scale = scale if scale is not None else Float3(1, 1, 1)

        self.on_changed: callable = None

        self.position.on_changed = None
        self.scale.on_changed = None

        self.parent: Transform = None
        self.children: list[Transform] = []
        
        
    def rotate_by_eulers(self, eulers):
        """Rotate this transform by given Euler angles (in radians)."""
        rot_quat = Quaternion.from_eulers([eulers[0], eulers[1], eulers[2]])
        self.rotation = rot_quat * self.rotation   # quaternion multiplication

        if self.on_changed:
            self.on_changed()
            
        
    def look_at(self, target: Float3):
        # compute direction vector
        dx = target.x - self.position.x
        dy = target.y - self.position.y
        dz = target.z - self.position.z

        # if target is at the same position, do nothing
        if dx == 0 and dy == 0 and dz == 0:
            return

        eye = [self.position.x, self.position.y, self.position.z]
        tgt = [target.x, target.y, target.z]
        up = [0.0, 1.0, 0.0]

        # create view matrix (world -> view), then extract the rotation (view's upper-left 3x3)
        # and transpose it to get the world rotation (view rotation inverse)
        view = matrix44.create_look_at(eye, tgt, up)
        rot_mat = view[:3, :3].T

        # convert rotation matrix to quaternion and assign
        self.rotation = Quaternion.from_matrix(rot_mat)

        if self.on_changed:
            self.on_changed()
    
    #                                    right   up      forward
    def get_basis_vectors(self) -> tuple[Float3, Float3, Float3]: # Get the directional vectors for transforming points
        forward = Float3(
            -math.sin(self.rotation.y) * math.cos(self.rotation.x),
            math.sin(self.rotation.x),
            -math.cos(self.rotation.y) * math.cos(self.rotation.x)
        ).normalize()
        
        # Right vector (positive X in camera space)
        world_up = Float3(0, 1, 0)
        right = forward.cross(world_up).normalize()
        
        # Up vector (recalculate to ensure orthogonality)
        up = right.cross(forward).normalize()
        
        return (right, up, forward)
    
    def get_inverse_basis_vectors(self) -> tuple[Float3, Float3, Float3]: # Get the directional vectors for transforming points
        (ihat, jhat, khat) = self.get_basis_vectors()
        ihat_inverse = Float3(ihat.x, jhat.x, khat.x) # Right and left relative
        jhat_inverse = Float3(ihat.y, jhat.y, khat.y) # Up and down relative
        khat_inverse = Float3(ihat.z, jhat.z, khat.z) # Forward and backward relative

        return (ihat_inverse, jhat_inverse, khat_inverse)
    
    def transform_vector(self, ihat: Float3, jhat: Float3, khat: Float3, vector: Float3):
        return vector.x * ihat + vector.y * jhat + vector.z * khat # Transform point by the basis vectors
    
    def __setattr__(self, name, value):
        super().__setattr__(name, value)

        if name == 'on_changed':
            self.position.on_changed = value
            self.scale.on_changed = value