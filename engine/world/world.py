import math, moderngl
import noise, numpy as np, os
import random
from ..math import Float2, Float3, Transform
from ..constants import CTX, PROGRAM, SHADERS_PATH
from ..rendering import Model, Camera, IGameObject, Texture

class World(IGameObject):
  def __init__(self, chunk_size: int, lod_levels: int = 5):
    self.model = None
    
    self.noise_shape = (256, 256)
    self.noise_scale = 100.0
    self.noise_octaves = 2
    self.noise_persistence = 0.5
    self.noise_lacunarity = 2.0

    self.ground_tex_cache = Texture.create("world_ground", CTX.texture((1, 1), 4, data=b'\xff\xff\xff\xff'))
    self.chunks: dict[tuple[int, int], list[Model]] = {}
    self.chunk_buffs: dict[tuple[int, int], list[tuple[moderngl.Buffer, moderngl.Buffer, moderngl.Buffer]]] = {}
    
    self.time = 10000

    self.camera_chunk_x = int(Camera.active.transform.position.x) // chunk_size
    self.camera_chunk_z = int(Camera.active.transform.position.z) // chunk_size

    self.is_generating = False
    self.queued_chunk: tuple[int, int] = None

    self.setup_cache(chunk_size, lod_levels)

  def create_model_cpu(self, chunk_size: int):
    verts = []
    norms = []
    tex_coords = []
    
    
    
    def get_noise_at(x, z):
      noise1 = noise.pnoise2((x + self.time)/self.noise_scale, 
              (z + self.time)/self.noise_scale, 
              octaves=self.noise_octaves, 
              persistence=self.noise_persistence, 
              lacunarity=self.noise_lacunarity, 
              repeatx=self.noise_shape[0], 
              repeaty=self.noise_shape[1], 
              base=0)
      noise2 = noise.pnoise2((x + self.time)/self.noise_scale, 
              (z + self.time)/self.noise_scale, 
              octaves=self.noise_octaves + 5, 
              persistence=self.noise_persistence + 0.5, 
              lacunarity=self.noise_lacunarity, 
              repeatx=self.noise_shape[0], 
              repeaty=self.noise_shape[1], 
              base=0)

      if (noise1 < 0.10):
        return noise1 / 5
      
      if noise1 > 0.10:
        noise1 = (noise1 / 5) * (0.681 * (46.416 ** noise1))
  
      return (noise1 + (max(0.0, noise1) * noise2))

    heights = [[get_noise_at(x, z) for z in range(chunk_size + 1)] for x in range(chunk_size + 1)]

    def get_vert_pos(x, z):
      return Float3(x, heights[x][z] * 100, z)

    loops = 0

    for x in range(chunk_size):
      for z in range(chunk_size):
        # loops+=1
        # if (loops % ((chunk_size * chunk_size) // 100) == 0):
        #   print(f"Processed {loops} vertices ({(loops / ((chunk_size * chunk_size) // 100))}%)")
        verts.append(get_vert_pos(x, z))                           # 1st triangle
        verts.append(get_vert_pos(x, z + 1))
        verts.append(get_vert_pos(x + 1, z))
        verts.append(get_vert_pos(x + 1, z))                       # 2nd triangle
        verts.append(get_vert_pos(x, z + 1))
        verts.append(get_vert_pos(x + 1, z + 1))
        norms.append(Float3(0, 0, 1))                              # 1st triangle
        norms.append(Float3(0, 0, 1))
        norms.append(Float3(0, 0, 1))
        norms.append(Float3(0, 0, 1))                              # 2nd triangle
        norms.append(Float3(0, 0, 1))
        norms.append(Float3(0, 0, 1))
        tex_coords.append(Float2(x, z))        # 1st triangle
        tex_coords.append(Float2(x, (z + 1)))
        tex_coords.append(Float2((x + 1), z))
        tex_coords.append(Float2((x + 1), z))   # 2nd triangle
        tex_coords.append(Float2(x, (z + 1)))
        tex_coords.append(Float2((x + 1), (z + 1)))


    self.model = Model([Model.VertexData(verts[i], norms[i], tex_coords[i]) for i in range(len(verts))], Transform())
    print("Done!")

  def setup_cache(self, chunk_size: int, lod_levels: int = 5):
    # Load and compile the compute shader
    with open(os.path.join(SHADERS_PATH, 'world_generator.glsl'), 'r') as f:
      self.world_generator_compute = CTX.compute_shader(f.read())

    self.chunk_size = chunk_size

    self.lod_levels = lod_levels
    self.lod_sizes: list[int] = [math.ceil(chunk_size / (2 ** i)) for i in range(lod_levels)]

    self.zero_arrays_vec4 = [np.zeros((self.lod_sizes[i] ** 2) * 6 * 4, dtype=np.float32) for i in range(lod_levels)]
    self.zero_arrays_vec3 = [np.zeros((self.lod_sizes[i] ** 2) * 6 * 3, dtype=np.float32) for i in range(lod_levels)]
    self.zero_arrays_vec2 = [np.zeros((self.lod_sizes[i] ** 2) * 6 * 2, dtype=np.float32) for i in range(lod_levels)]

    # Set uniform values
    self.world_generator_compute["time"].value = self.time
    

  def create_models_gpu(self, chunk_size: int, chunk_x: int, chunk_z: int):
    if (chunk_size != self.chunk_size):
      self.setup_cache(chunk_size) # Reset shader cache if dimensions change

    offset_x = chunk_x * chunk_size
    offset_z = chunk_z * chunk_size

    # List of (vertex_buffer, tex_coord_buffer, normal_buffer) tuples for each LOD level
    lod_buffers: list[tuple[moderngl.Buffer, moderngl.Buffer, moderngl.Buffer]] = []
    lod_models: list[Model] = []

    for i in range(self.lod_levels):
      lod_vert_buff = CTX.buffer(data=self.zero_arrays_vec3[i].tobytes())
      lod_norm_buff = CTX.buffer(data=self.zero_arrays_vec3[i].tobytes())
      lod_tex_coord_buff = CTX.buffer(data=self.zero_arrays_vec2[i].tobytes())

      lod_buffers.append((lod_vert_buff, lod_tex_coord_buff, lod_norm_buff))
      
      # Bind buffers to the compute shader
      lod_buffers[i][0].bind_to_storage_buffer(0)
      lod_buffers[i][1].bind_to_storage_buffer(1)
      lod_buffers[i][2].bind_to_storage_buffer(2)

      lod_size = self.lod_sizes[i]

      # Calculate number of work groups needed (16x16 local size in shader)
      self.groups_x = (lod_size + 7) // 8
      self.groups_y = (lod_size + 7) // 8

      self.world_generator_compute["lod"].value = i
      self.world_generator_compute["lod_size"].value = lod_size
      self.world_generator_compute["offset_x"].value = offset_x
      self.world_generator_compute["offset_z"].value = offset_z

      self.world_generator_compute.run(self.groups_x, self.groups_y)

      new_lod_model = Model([], Transform(), False)
      new_lod_model.transform.position = Float3(offset_x, 0, offset_z)
      new_lod_model.set_texture(self.ground_tex_cache if self.ground_tex_cache != None else Texture.load("cube_tex.png"))
      lod_models.append(new_lod_model)
      
      lod_models[i].generate_vao_with_raw(CTX, PROGRAM, lod_buffers[i][0], lod_buffers[i][1], lod_buffers[i][2])


    return lod_buffers, lod_models
  
  def generate_chunk(self, chunk_x: int, chunk_z: int):
    if (self.chunks.get((chunk_x, chunk_z)) != None):
      return

    buffers, models = self.create_models_gpu(self.chunk_size, chunk_x, chunk_z)

    self.chunk_buffs[(chunk_x, chunk_z)] = buffers
    self.chunks[(chunk_x, chunk_z)] = models
    
  def generate_chunks_around(self, center_chunk_x: int, center_chunk_z: int, radius: int):
    if radius % 2 == 0:
      radius += 1  # Ensure radius is odd to have a center chunk
    
    for dx in range(-radius, radius + 1):
      for dz in range(-radius, radius + 1):
        self.generate_chunk(center_chunk_x + dx, center_chunk_z + dz)

  __debug_chunk_colors: dict[tuple[int, int], tuple[float, float, float]] = {}

  def render(self, generate_around: bool = True):
    self.camera_chunk_x = int(Camera.active.transform.position.x) // self.chunk_size
    self.camera_chunk_z = int(Camera.active.transform.position.z) // self.chunk_size

    if generate_around:
      self.generate_chunks_around(self.camera_chunk_x, self.camera_chunk_z, 1)
      
    for chunk_models in self.chunks.values():
      chunk_x_dist = abs(chunk_models[0].transform.position.x // self.chunk_size - self.camera_chunk_x)
      chunk_z_dist = abs(chunk_models[0].transform.position.z // self.chunk_size - self.camera_chunk_z)
      dist = math.sqrt(chunk_x_dist ** 2 + chunk_z_dist ** 2)
      lod_level = max(min(int(dist), self.lod_levels - 1) - 1, 0)  # Increase LOD level with distance, max to available levels

      # Debug stuff
      chunk_key = (chunk_models[0].transform.position.x // self.chunk_size, chunk_models[0].transform.position.z // self.chunk_size)
      if (World.__debug_chunk_colors.get(chunk_key) == None):
        World.__debug_chunk_colors[chunk_key] = (random.random(), random.random(), random.random())
      PROGRAM['tint'].value = World.__debug_chunk_colors[chunk_key]

      chunk_models[lod_level].render()

  def get_chunk_at(self, position: Float3, lod: int = 0) -> tuple[int, int]:
    chunk_x = int(position.x) // self.chunk_size
    chunk_z = int(position.z) // self.chunk_size
    
    return self.get_chunk(chunk_x, chunk_z, lod)

  def get_chunk(self, chunk_x: int = None, chunk_z: int = None, lod: int = 0) -> Model:
    if chunk_x is None:
      chunk_x = 0
    if chunk_z is None:
      chunk_z = 0
      
    # print(f"Getting chunk at ({chunk_x}, {chunk_z}) LOD {lod}")
      
    chunk = self.chunks.get((chunk_x, chunk_z))
    if chunk is None:
      return None
    
    return chunk[lod]