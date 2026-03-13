import os, moderngl
from ..constants import CTX, SHADERS_PATH

def load_compute_shader(shader_path: str) -> moderngl.ComputeShader:
    # Load shader source code from file
    with open(os.path.join(SHADERS_PATH, shader_path), 'r') as f:
        shader_source = f.read()
        compiled = CTX.compute_shader(shader_source)
    return compiled