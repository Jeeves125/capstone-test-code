import os, pygame, moderngl
import sys, os

""" Setup file paths """
# Resolve path of the entry-point (main) script; fall back to argv[0] or this file
_main = sys.modules.get('__main__')
if _main and getattr(_main, '__file__', None):
    __script_path = os.path.abspath(_main.__file__)
elif sys.argv and sys.argv[0]:
    __script_path = os.path.abspath(sys.argv[0])
else:
    __script_path = os.path.abspath(__file__)
__script_dir = os.path.dirname(__script_path)

# print(f"Script directory: {__script_dir}")

ASSETS_PATH = os.path.join(__script_dir, "assets")
MODELS_PATH = os.path.join(ASSETS_PATH, "models")
TEXTURES_PATH = os.path.join(ASSETS_PATH, "textures")
SHADERS_PATH = os.path.join(ASSETS_PATH, "shaders")

""" Setup window constants & others"""
WIDTH = 1000
HEIGHT = 600

""" Setup pygame constants """
pygame.init()

pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 4)

pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 4)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)

DISPLAY = pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
CLOCK = pygame.time.Clock()

""" Setup ModernGL constants """
CTX = moderngl.create_context()
CTX.viewport = (0, 0, WIDTH, HEIGHT)
CTX.enable(moderngl.CULL_FACE)
CTX.enable(moderngl.DEPTH_TEST)
CTX.depth_func = '<='
CTX.enable(moderngl.BLEND)
CTX.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
CTX.front_face = 'ccw' # Counter-clockwise winding is front face

def __get_shaders():
    with open(os.path.join(SHADERS_PATH, 'vertex_shader.vert'), 'r') as f:
        vertex_shader_src = f.read()
    with open(os.path.join(SHADERS_PATH, 'fragment_shader.frag'), 'r') as f:
        fragment_shader_src = f.read()
    with open(os.path.join(SHADERS_PATH, 'indirect_rendering', 'indirect_vertex_shader.vert'), 'r') as f:
        indirect_vertex_shader_src = f.read()
    with open(os.path.join(SHADERS_PATH, 'indirect_rendering', 'indirect_fragment_shader.frag'), 'r') as f:
        indirect_fragment_shader_src = f.read()
    return vertex_shader_src, fragment_shader_src, indirect_vertex_shader_src, indirect_fragment_shader_src

__vert, __frag, __indirect_vert, __indirect_frag = __get_shaders()
PROGRAM = CTX.program(vertex_shader=__vert, fragment_shader=__frag)
INDIRECT_PROGRAM = CTX.program(vertex_shader=__indirect_vert, fragment_shader=__indirect_frag)

def set_compute_uniforms(shader, uniforms: dict[str, any], ignore_missing: bool = True, log_missing: bool = False):
    for name, value in uniforms.items():
        try:
            if isinstance(value, (list, tuple)) and len(value) in [2, 3, 4]: # If the value is a vec2, 3, or 4
                shader[name].value = tuple(value)
            else:
                shader[name].value = value
        except KeyError as e:
            if not ignore_missing:
                raise e
            elif log_missing:
                print(f"Warning: Uniform '{e.args[0]}' not found in compute shader.")
    
    
