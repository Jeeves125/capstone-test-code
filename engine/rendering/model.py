import os, numpy as np
import moderngl, math
from OpenGL.GL import *
from ..math import Float2, Float3
from ..math.transform import Transform
from ..constants import CTX, PROGRAM, INDIRECT_PROGRAM, MODELS_PATH
from .texture import Texture
from .file_loader import load_compute_shader
from .indirect_render_controller import IndirectRenderController

import numpy as np
import math

from pyrr import Matrix44, Vector3, Quaternion
def create_model_matrix(transform: Transform) -> np.ndarray:
    mat_translate = Matrix44.from_translation(Vector3(transform.position.as_tuple()))
    mat_rotate = Matrix44.from_quaternion(transform.rotation)
    mat_scale = Matrix44.from_scale(Vector3(transform.scale.as_tuple()))
    return (mat_translate * mat_rotate * mat_scale).astype('f4')

# def create_model_matrix(transform):
#     """Return a 4x4 model matrix for a transform with position, rotation, scale.
#        Rotation must be in radians.

#        Convention: column-vector math consistent with GL. Final composition is M = T @ R @ S.
#        Rotation order uses yaw (Y), then pitch (X), then roll (Z): R = R_y @ R_x @ R_z.
       
#        Expected attributes:
#            transform.position.x/y/z
#            transform.rotation.x/y/z   (radians)
#            transform.scale.x/y/z
#     """

#     px, py, pz = transform.position.x, transform.position.y, transform.position.z
#     rx, ry, rz = transform.rotation.x, transform.rotation.y, transform.rotation.z
#     sx, sy, sz = transform.scale.x, transform.scale.y, transform.scale.z

#     # --- SCALE MATRIX ---
#     S = np.array([
#         [sx, 0,  0,  0],
#         [0,  sy, 0,  0],
#         [0,  0,  sz, 0],
#         [0,  0,  0,  1]
#     ], dtype=np.float32)

#     # --- ROTATION MATRICES ---
#     # X rotation (pitch)
#     cx, sx_ = math.cos(rx), math.sin(rx)
#     R_x = np.array([
#         [1, 0,    0,     0],
#         [0, cx,  -sx_,   0],
#         [0, sx_,  cx,    0],
#         [0, 0,    0,     1]
#     ], dtype=np.float32)

#     # Y rotation (yaw)
#     cy, sy_ = math.cos(ry), math.sin(ry)
#     R_y = np.array([
#         [ cy, 0, sy_, 0],
#         [  0, 1,  0,  0],
#         [-sy_,0, cy, 0],
#         [  0, 0,  0, 1]
#     ], dtype=np.float32)

#     # Z rotation (roll)
#     cz, sz_ = math.cos(rz), math.sin(rz)
#     R_z = np.array([
#         [cz, -sz_, 0, 0],
#         [sz_,  cz, 0, 0],
#         [ 0,   0,  1, 0],
#         [ 0,   0,  0, 1]
#     ], dtype=np.float32)

#     # Combine rotations (Y * X * Z) → standard camera-style order
#     R = R_y @ R_x @ R_z

#     # --- TRANSLATION MATRIX ---
#     T = np.array([
#         [1, 0, 0, px],
#         [0, 1, 0, py],
#         [0, 0, 1, pz],
#         [0, 0, 0, 1 ]
#     ], dtype=np.float32)

#     # Final model matrix: T * R * S
#     M = T @ R @ S
#     return M


from abc import ABC, abstractmethod

class IGameObject(ABC):
    @abstractmethod
    def render(self):
        pass

class VertexData:
    def __init__(self, position: Float3, normal: Float3, tex_coord: Float2):
        self.position = position
        self.normal = normal
        self.tex_coord = tex_coord

class Model(IGameObject):
    __indirect_render_controller = IndirectRenderController()
    __models_instanced: list['Model'] = []
    __model_count = 0

    """
    Track all model instances for later multi-draw indirect rendering
    """
    def get_instances() -> list['Model']:
        return Model.__models_instanced
    
    def __add_instance(self):
        Model.__indirect_render_controller.add_model(self)
        
        Model.__models_instanced.append(self)
        Model.__model_count += 1

    def render_all_indirect():
        Model.__indirect_render_controller.update_matrix_ssbo()
        Model.__indirect_render_controller.render_indirect()
        
    """
    Model loading and instance methods
    """
    @staticmethod
    def load(file_path: str, initial_transform: Transform) -> 'Model':
        """
        Load an OBJ file and return vertex data in the format (position, normal, tex_coord)
        """
        vertex_positions = []
        normals = []
        tex_coords = []
        vertices = []
        
        with open(os.path.join(MODELS_PATH, file_path), 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('v '):  # Vertex position
                    values = line[2:].split()
                    vertex_positions.append(Float3(float(values[0]), float(values[1]), float(values[2])))
                elif line.startswith('vn '):  # Vertex normal
                    values = line[3:].split()
                    normals.append(Float3(float(values[0]), float(values[1]), float(values[2])))
                elif line.startswith('vt '):  # Texture coordinate
                    values = line[3:].split()
                    tex_coords.append(Float2(float(values[0]), float(values[1])))
                elif line.startswith('f '):  # Face
                    Model.__triangulate_face(line[2:].split(), vertex_positions, tex_coords, normals, vertices)
        
        return Model(vertices, initial_transform)

    def __triangulate_face(face_data, positions, tex_coords, normals, vertices):
        """Helper function to triangulate faces and extract vertex data"""
        # Get vertex indices for the face (subtract 1 as OBJ is 1-indexed)
        face_vertices = []
        
        for vertex_str in face_data:
            if not vertex_str:  # Skip empty entries
                continue
                
            indices = vertex_str.split('/')
            pos_idx = int(indices[0]) - 1 if indices[0] else 0
            tex_idx = int(indices[1]) - 1 if len(indices) > 1 and indices[1] else 0
            norm_idx = int(indices[2]) - 1 if len(indices) > 2 and indices[2] else 0
            
            pos = positions[pos_idx] if pos_idx < len(positions) else Float3(0, 0, 0)
            tex = tex_coords[tex_idx] if tex_idx < len(tex_coords) else Float2(0, 0)
            norm = normals[norm_idx] if norm_idx < len(normals) else Float3(0, 0, 0)

            face_vertices.append(VertexData(pos, norm, tex))

        # Triangulate the face (assuming convex)
        for i in range(1, len(face_vertices) - 1):
            vertices.append(face_vertices[0])
            vertices.append(face_vertices[i])
            vertices.append(face_vertices[i + 1])

    """
    Class instance methods
    """
    def __init__(self, vertex_data: list[VertexData], initial_transform: Transform, generate_vao: bool = True):
        self.positions = np.array([v.position.as_tuple() for v in vertex_data], dtype=np.float32)
        self.tex_coords = np.array([v.tex_coord.as_tuple() for v in vertex_data], dtype=np.float32)
        self.normals = np.array([v.normal.as_tuple() for v in vertex_data], dtype=np.float32)
        self.vertex_data: list[VertexData] = vertex_data

        self.model_index = Model.__model_count
        self.parent_scene = None

        self.transform = initial_transform
        
        def on_transform_changed():
            if self.parent_scene != None:
                self.parent_scene.add_updated_transform_index(self.model_index)
                return
            Model.__indirect_render_controller._updated_transform_indices.add(self.model_index)
        self.transform.on_changed = on_transform_changed

        self.buffers: tuple[moderngl.Buffer, moderngl.Buffer, moderngl.Buffer] = None
        self.buffer_based = False

        self.matrix = create_model_matrix(self.transform)
        
        if (generate_vao):
            self.generate_vao(CTX, PROGRAM)
            
        Model.__add_instance(self)
    
    def render(self):
        Texture.get(self.texture_cache).use(0)
        PROGRAM['model'].write(create_model_matrix(self.transform).tobytes())
        self.vao.render(mode=moderngl.TRIANGLES)

    def set_texture(self, texture_cache: str):
        self.texture_cache = texture_cache
        Texture.get(self.texture_cache).filter = (moderngl.NEAREST, moderngl.NEAREST)  # Use nearest neighbor filtering for pixel-perfect textures

    def generate_vao(self, ctx: moderngl.Context, program: moderngl.Program):
        position_buff = ctx.buffer(self.positions.tobytes())
        tex_coord_buff = ctx.buffer(self.tex_coords.tobytes())
        normal_buff = ctx.buffer(self.normals.tobytes())
        
        self.buffers = (position_buff, tex_coord_buff, normal_buff)
        self.buffer_based = True

        self.vao = ctx.vertex_array(
            program,
            [
                (position_buff, '3f', 'in_position'),
                # (tex_coord_buff, '2f', 'in_texcoord'),
                # (normal_buff, '3f', 'in_normal'),
            ]
        )

    def generate_vao_with_raw(self, ctx: moderngl.Context, program: moderngl.Program, pos_buff: moderngl.Buffer, tex_buff: moderngl.Buffer, norm_buff: moderngl.Buffer):
        self.buffers = (pos_buff, tex_buff, norm_buff)
        self.buffer_based = True
        self.vao = ctx.vertex_array(
            program,
            [
                (pos_buff, '3f', 'in_position'),
                (tex_buff, '2f', 'in_texcoord'),
                # (norm_buff, '3f', 'in_normal'),
            ]
        )