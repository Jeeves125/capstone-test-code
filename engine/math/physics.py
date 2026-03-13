import os
import numpy as np
import moderngl
from ..rendering import Model, load_compute_shader, create_model_matrix
from ..constants import CTX, set_compute_uniforms
from .transform import Transform
from .float3 import Float3

def round_to_nearest(value, nearest):
    return round(value / nearest) * nearest
  
def ceil_to_nearest(value, nearest):
    return int(-(-value // nearest)) * nearest
  
class PhysicsObject:
  def __init__(self, transform=None):
    self.transform = transform if transform is not None else Transform()
    self.velocity = Float3(0,0,0)
    
  def update(self, delta_time: float):
    self.transform.position += self.velocity * delta_time
    
  def is_colliding_model(self, model: Model, verbose=False):
    pass

  def collide_with_model(self, model: Model):
    pass
  
class Capsule(PhysicsObject):
  def __init__(self, transform: Transform, height: 3, radius: float):
    super().__init__(transform)
    self.start = self.transform.position + Float3(0, height / 2, 0)
    self.end = self.transform.position - Float3(0, height / 2, 0)
    self.radius = radius
    self.height = height

  def is_colliding_model(self, model, verbose=False, give_raw_output=False):
    uniforms = {
      "capsule_start": self.start.as_tuple(),
      "capsule_end": self.end.as_tuple(),
      "capsule_radius": self.radius,
    }

    collision_info = Collisions._run_collide_shader(Collisions._capsule_model_compute, model, uniforms, verbose=verbose, raw_output=give_raw_output)

    return collision_info[0] == 1 if not verbose else collision_info


  def collide_with_model(self, model):
    uniforms = {
      "capsule_start": self.start.as_tuple(),
      "capsule_end": self.end.as_tuple(),
      "capsule_radius": self.radius,
    }
    
    collision_info = self.is_colliding_model(model, verbose=True, give_raw_output=True)
    condensed_buff = Collisions._count_and_condense_collisions(collision_info, model)
    if (condensed_buff is None):
      return False, 0, 0, 0, 0
    
    resolve_data = Collisions._run_resolve_shader(Collisions._capsule_model_resolve_compute, model, uniforms, condensed_buff)

    return resolve_data   # is_collision, slide_collision, resolve_x, resolve_y, resolve_z

  def __getattribute__(self, name):
    if (name == "start"):
      return self.transform.position + Float3(0, self.height / 2, 0)
    if (name == "end"):
      return self.transform.position - Float3(0, self.height / 2, 0)
    return super().__getattribute__(name)

class Box(PhysicsObject):
  def __init__(self, center: Float3, halfsize: Float3):
    super().__init__()
    self.center = center
    self.halfsize = halfsize

class Sphere(PhysicsObject):
  def __init__(self, center: Float3, radius: float):
    super().__init__()
    self.center = center
    self.radius = radius

class Plane(PhysicsObject):
  def __init__(self, point: Float3, normal: Float3):
    super().__init__()
    self.point = point
    self.normal = normal

class Triangle(PhysicsObject):
  def __init__(self, v0: Float3, v1: Float3, v2: Float3):
    super().__init__()
    self.v0 = v0
    self.v1 = v1
    self.v2 = v2
    

class Collisions:
  __loaded = False
  _box_model_compute = None
  _capsule_model_compute = None
  _capsule_model_resolve_compute = None
  _count_collisions_compute = None
  _condense_collisions_compute = None

  def _load_shaders():
    # If collision shaders already loaded, skip
    if Collisions.__loaded:
      return

    Collisions._count_collisions_compute = load_compute_shader(os.path.join('collision', 'count_collisions.glsl'))
    Collisions._condense_collisions_compute = load_compute_shader(os.path.join('collision', 'condense_collisions.glsl'))

    Collisions._box_model_compute = load_compute_shader(os.path.join('collision', 'detection', 'box_model_collision.glsl'))

    Collisions._capsule_model_compute = load_compute_shader(os.path.join('collision', 'detection', 'capsule_model_collision.glsl'))
    Collisions._capsule_model_resolve_compute = load_compute_shader(os.path.join('collision', 'resolution', 'capsule_model_collision.glsl'))

    # with open(os.path.join('Software Rasterizer', 'shaders', 'collision', 'count_collisions.glsl'), 'r') as f:
    #   count_collisions_src = f.read()
    #   Collisions._count_collisions_compute = CTX.compute_shader(count_collisions_src)

    # with open(os.path.join('Software Rasterizer', 'shaders', 'collision', 'condense_collisions.glsl'), 'r') as f:
    #   condense_collisions_src = f.read()
    #   Collisions._condense_collisions_compute = CTX.compute_shader(condense_collisions_src)

    # with open(os.path.join('Software Rasterizer', 'shaders', 'collision', 'detection', 'box_model_collision.glsl'), 'r') as f:
    #   box_model_compute_src = f.read()
    #   Collisions._box_model_compute = CTX.compute_shader(box_model_compute_src)
      
    # with open(os.path.join('Software Rasterizer', 'shaders', 'collision', 'detection', 'capsule_model_collision.glsl'), 'r') as f:
    #   capsule_model_compute_src = f.read()
    #   Collisions._capsule_model_compute = CTX.compute_shader(capsule_model_compute_src)
    # with open(os.path.join('Software Rasterizer', 'shaders', 'collision', 'resolution', 'capsule_model_collision.glsl'), 'r') as f:
    #   capsule_model_resolve_compute_src = f.read()
    #   Collisions._capsule_model_resolve_compute = CTX.compute_shader(capsule_model_resolve_compute_src)
    
    Collisions.__loaded = True

  # Cache buffers for reuse, rather than creating new ones each time (MEMORY OPTIMIZATION)
  __buffers: dict[tuple[int, str], moderngl.Buffer] = {}
  def __get_buffer(size: int, dtype='f4', fill_bytes=None) -> moderngl.Buffer:
    key = (size, dtype)
    if key not in Collisions.__buffers:
      Collisions.__buffers[key] = CTX.buffer(data=(fill_bytes if fill_bytes is not None else np.zeros(size, dtype=dtype).tobytes()))
    elif fill_bytes is not None:
      Collisions.__buffers[key].write(fill_bytes)

    return Collisions.__buffers[key]

  def _get_vert_count(model: Model):
    if model.buffer_based and model.buffers != None:
      vert_buff = model.buffers[0]
    else:
      vert_buff = Collisions.__get_buffer(size=model.positions.nbytes, dtype='f4', fill_bytes=model.positions.tobytes())

    num_vertices = vert_buff.size // (3 * 4)  # 3 floats per vertex, 4 bytes per float
    return num_vertices

  def _run_collide_shader(compute, model: Model, uniforms, verbose=False, override_out_size=None, override_group_count=None, raw_output=False):
    vert_buff = None
    
    if model.buffer_based and model.buffers != None:
      vert_buff = model.buffers[0]
    else:
      vert_buff = Collisions.__get_buffer(size=model.positions.nbytes, dtype='f4', fill_bytes=model.positions.tobytes())

    num_vertices = vert_buff.size // (3 * 4)  # 3 floats per vertex, 4 bytes per float
    num_triangles = num_vertices // 3 # 3 vertices per triangle

    outsize = num_triangles if override_out_size is None else override_out_size

    out_collision_info = Collisions.__get_buffer(size=(outsize if verbose else 1), dtype='f4', fill_bytes=np.zeros((outsize if verbose else 1), dtype='f4').tobytes())  # Reserve space for output (float size is 4 bytes)

    # Don't use 0, 1, and 2 because those are used by the world generator compute shader
    vert_buff.bind_to_storage_buffer(3)
    out_collision_info.bind_to_storage_buffer(4)
    
    uniforms['num_vertices'] = num_vertices
    uniforms['verbose'] = 1 if verbose else 0

    set_compute_uniforms(compute, uniforms)
    
    compute['model_matrix'].write(create_model_matrix(model.transform).tobytes())

    groups_x = ((num_triangles + 63) // 64) if override_group_count is None else override_group_count

    compute.run(groups_x)

    if raw_output:
      return out_collision_info
    
    result_array = np.frombuffer(out_collision_info.read(), dtype='f4')
    return result_array

  def _run_resolve_shader(compute, model: Model, uniforms, condensed_buffer):
    vert_buff = None
    
    if model.buffer_based and model.buffers != None:
      vert_buff = model.buffers[0]
    else:
      vert_buff = Collisions.__get_buffer(size=model.positions.nbytes, dtype='f4', fill_bytes=model.positions.tobytes())

    num_vertices = vert_buff.size // (3 * 4)  # 3 floats per vertex, 4 bytes per float
    # num_triangles = num_vertices // 3 # 3 vertices per triangle

    outsize = 5  # 5 float output
    # is_collision, resolve_x, resolve_y, resolve_z, slide_collision

    out_collision_info = Collisions.__get_buffer(size=outsize, dtype='f4', fill_bytes=np.zeros(outsize, dtype='f4').tobytes())  # Reserve space for output (float size is 4 bytes)

    # Don't use 0, 1, and 2 because those are used by the world generator compute shader
    vert_buff.bind_to_storage_buffer(3)
    out_collision_info.bind_to_storage_buffer(4)
    condensed_buffer.bind_to_storage_buffer(5)

    uniforms['num_vertices'] = num_vertices

    set_compute_uniforms(compute, uniforms)
    
    compute['model_matrix'].write(create_model_matrix(model.transform).tobytes())

    groups_x = 1  # Only need one group for resolution

    compute.run(groups_x)

    return np.frombuffer(out_collision_info.read(), dtype='f4')
  
  def _count_collisions(collision_info_buffer: moderngl.Buffer, num_vertices):
    num_triangles = num_vertices // 3

    out_count_info = Collisions.__get_buffer(size=1, dtype='u4', fill_bytes=np.zeros(1, dtype='u4').tobytes())  # Single int output

    collision_info_buffer.bind_to_storage_buffer(3)
    out_count_info.bind_to_storage_buffer(4)
    

    Collisions._count_collisions_compute['num_vertices'].value = num_vertices

    groups_x = (num_triangles + 63) // 64

    Collisions._count_collisions_compute.run(groups_x)

    count_result = np.frombuffer(out_count_info.read(), dtype=np.uint32)

    return int(count_result[0])

  def _condense_collisions(collision_info_buffer: moderngl.Buffer, collision_count: int, num_vertices: int):
    out_condensed_info = Collisions.__get_buffer(size=collision_count, dtype='u4', fill_bytes=np.zeros(collision_count, dtype='u4').tobytes())
    counter_buffer = Collisions.__get_buffer(size=1, dtype='u4', fill_bytes=np.zeros(1, dtype=np.uint32).tobytes())

    collision_info_buffer.bind_to_storage_buffer(3)
    out_condensed_info.bind_to_storage_buffer(4)
    counter_buffer.bind_to_storage_buffer(5)
    
    Collisions._condense_collisions_compute['num_vertices'].value = num_vertices
    
    num_triangles = num_vertices // 3

    groups_x = (num_triangles + 63) // 64

    Collisions._condense_collisions_compute.run(groups_x)

    return out_condensed_info
  
  def _count_and_condense_collisions(collision_info: moderngl.Buffer, model: Model):
    num_vertices = Collisions._get_vert_count(model)
    count = Collisions._count_collisions(collision_info, num_vertices)
    if (count == 0):
      return None
    condensed_buffer = Collisions._condense_collisions(collision_info, count, num_vertices)
    return condensed_buffer

    
# Make sure to call this once during initialization, whether or not this is the main file
Collisions._load_shaders()
