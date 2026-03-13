import moderngl
from .texture import Texture
from ..constants.constants import CTX, SHADERS_PATH, TEXTURES_PATH
import os, numpy as np, io
from PIL import Image

class Skybox:
  def __init__(self, faces: list[str], projection_matrix: np.ndarray):
    self.cubemap = CTX.texture_cube((512, 512), components=3)
    for i, face in enumerate(faces):

      img = Image.open(os.path.join(TEXTURES_PATH, face)).convert('RGB')

      # Fix upside-down cubemap face
      # img = img.transpose(Image.FLIP_TOP_BOTTOM)

      self.cubemap.write(face=i, data=img.tobytes())
    
    self.cubemap.build_mipmaps()
    
    vertex_shader = ""
    with open(os.path.join(SHADERS_PATH, "skybox.vert")) as f:
        vertex_shader = f.read()
        
    fragment_shader = ""
    with open(os.path.join(SHADERS_PATH, "skybox.frag")) as f:
        fragment_shader = f.read()
        
    self.program = CTX.program(
      vertex_shader=vertex_shader,
      fragment_shader=fragment_shader,
    )
    
    self.cube_vertices = np.array([
        # positions only
        -1, -1, -1,  1, -1, -1,  1,  1, -1, -1,  1, -1,
        -1, -1,  1,  1, -1,  1,  1,  1,  1, -1,  1,  1,
        -1,  1,  1,  -1,  1, -1,  -1, -1, -1,  -1, -1,  1,
        1,  1,  1,   1,  1, -1,   1, -1, -1,   1, -1,  1,
        -1, -1, -1,   1, -1, -1,   1, -1,  1,  -1, -1,  1,
        -1,  1, -1,   1,  1, -1,   1,  1,  1,  -1,  1,  1,
    ], dtype='f4')

    self.vbo = CTX.buffer(self.cube_vertices.tobytes())
    indices = np.array([
        0, 1, 2,  2, 3, 0,
        4, 5, 6,  6, 7, 4,
        8, 9,10, 10,11, 8,
      12,13,14, 14,15,12,
      16,17,18, 18,19,16,
      20,21,22, 22,23,20,
    ], dtype='u4')

    self.ibo = CTX.buffer(indices.tobytes())
    self.vao = CTX.simple_vertex_array(self.program, self.vbo, 'in_pos', index_buffer=self.ibo)
    
    self.program['proj'].write(projection_matrix.astype('f4').tobytes())
    
    
  def render(self, view_matrix: np.ndarray):
    CTX.disable(moderngl.CULL_FACE)  # optional but recommended
    CTX.depth_mask = False           # skybox should not write depth

    self.program['view'].write(view_matrix.astype('f4').tobytes())
    self.cubemap.use(location=0)

    self.vao.render(moderngl.TRIANGLES)
    # or if your cube is indexed:
    # self.vao.render()

    CTX.depth_mask = True
    CTX.enable(moderngl.CULL_FACE)

