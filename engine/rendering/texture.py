import moderngl
import os, numpy as np
from PIL import Image
from ..constants import CTX, TEXTURES_PATH

class Texture:
    __texture_cache = {}

    def load(texture_path: str) -> str:
        if texture_path in Texture.__texture_cache:
            return texture_path  # Already loaded

        # Load texture from file
        img = Image.open(os.path.join(TEXTURES_PATH, texture_path)).convert('RGB')
        img = img.transpose(Image.FLIP_TOP_BOTTOM)  # Flip for OpenGL coordinates
        texture_data = np.array(img)
        Texture.__texture_cache[texture_path] = CTX.texture(img.size, 3, texture_data.tobytes())
        return texture_path

    def get(texture_path: str) -> moderngl.Texture:
        # Return cached texture or load if not present
        if texture_path not in Texture.__texture_cache:
            Texture.load(texture_path)
        return Texture.__texture_cache[texture_path]
    
    def create(cache_key: str, texture: moderngl.Texture):
        Texture.__texture_cache[cache_key] = texture
        return cache_key