import os
import numpy as np
import moderngl
from OpenGL.GL import *

from .texture import Texture
from .file_loader import load_compute_shader
from ..constants.constants import WIDTH, HEIGHT, CTX, INDIRECT_PROGRAM, set_compute_uniforms


def _load_ind_compute_shader(file_path: str) -> moderngl.ComputeShader:
    return load_compute_shader(os.path.join("indirect_rendering", file_path))

class IndirectRenderController:
    __cmd_dtype = np.dtype([
        ('count', np.uint32),         # number of vertices to draw
        ('instanceCount', np.uint32), # how many instances
        ('first', np.uint32),         # first vertex offset
        ('baseInstance', np.uint32)   # base instance (for SSBO index)
    ])
    __matrix_update_compute: moderngl.ComputeShader = None
    __model_capacity_update_compute: moderngl.ComputeShader = None

    def __init__(self, scene_x = 0, scene_y = 0, scene_width: int = WIDTH, scene_height: int = HEIGHT):
        if (IndirectRenderController.__model_capacity_update_compute == None):
            IndirectRenderController.__model_capacity_update_compute = _load_ind_compute_shader("model_capacity_update.glsl")
            
        if IndirectRenderController.__matrix_update_compute == None:
            IndirectRenderController.__matrix_update_compute = _load_ind_compute_shader("model_matrix_update.glsl")
        
        
        self.__models: list = []
        self.__model_count: int = 0
        
        self.__models_increment = 10000
        self.__max_models = 10000
        
        self.__current_vertices = 0
        self.__vertices_increment = 100000
        self.__max_vertices = 100000

        # Multi-draw indirect rendering resources
        self.__indirect_buffer: moderngl.Buffer = None

        self.__matrix_buffer: moderngl.Buffer = None
        self._updated_transform_indices: set[int] = set()
        self.__updated_transform_buffer: moderngl.Buffer = None

        self.__texture_atlas: moderngl.Texture = None
        self.__texture_atlas_uv_data_buffer: moderngl.Buffer = None
        self.__combined_vao: moderngl.VertexArray = None
        self.__combined_vbo: moderngl.Buffer = None
        self.__combined_tex_coords: moderngl.Buffer = None

        self.__added_models_this_frame: list = []
        self.__added_indirect_buffer = CTX.buffer(reserve=1 * IndirectRenderController.__cmd_dtype.itemsize)
        self.__added_texture_atlas_uv_data_buffer = CTX.buffer(reserve=1 * 4 * 4)  # 4 floats per model
        self.__added_combined_vbo = CTX.buffer(reserve=1 * 3 * 4)
        self.__added_combined_tex_coords = CTX.buffer(reserve=1 * 2 * 4)
        
        self.__removed_models_this_frame: list = [] # Fake for now, just set them inactive.

    def add_model(self, model):
        self.__models.append(model)
        self.__model_count += 1

        self.__added_models_this_frame.append(model)
        
    """
    Multi draw indirect rendering setup and methods
    """
    def build_indirect_command_buffer(self):
        if self.__indirect_buffer is not None: # If already built, return it
            return self.__indirect_buffer

        commands = np.zeros(len(self.__models), dtype=IndirectRenderController.__cmd_dtype)
        offset = 0
        for i in range(len(self.__models)):
            commands[i]['count'] = self.__models[i].positions.shape[0]
            commands[i]['instanceCount'] = 1
            commands[i]['first'] = offset
            commands[i]['baseInstance'] = i  # which model matrix to use
            offset += self.__models[i].positions.shape[0]
            
        self.__indirect_buffer = CTX.buffer(reserve=self.__max_models * IndirectRenderController.__cmd_dtype.itemsize)
        self.__indirect_buffer.write(commands.tobytes())
        return self.__indirect_buffer

    def build_matrix_ssbo(self):
        if self.__matrix_buffer is not None:  # If already built, return it
            return self.__matrix_buffer

        self.__matrix_buffer = CTX.buffer(np.array([mod.matrix for mod in self.__models], dtype='f4').tobytes())
        return self.__matrix_buffer
    
    def update_matrix_ssbo(self):
        # print("Updating matrix SSBO")
        if self.__matrix_buffer == None:
            return self.build_matrix_ssbo()

        self.__matrix_buffer.bind_to_storage_buffer(0)

        updated_transform_data: list[float] = []
        
        for mod_index in self._updated_transform_indices:
            mod = self.__models[mod_index]
            updated_transform_data.extend([
                mod_index,
                mod.transform.position.x, mod.transform.position.y, mod.transform.position.z,
                mod.transform.scale.x, mod.transform.scale.y, mod.transform.scale.z,
                mod.transform.rotation.x, mod.transform.rotation.y, mod.transform.rotation.z, mod.transform.rotation.w
            ])
            
        

        if self.__updated_transform_buffer == None:
            self.__updated_transform_buffer = CTX.buffer(reserve=11 * 4)  # 11 floats per model

        self.__updated_transform_buffer.orphan(size=len(updated_transform_data) * 4)
        self.__updated_transform_buffer.write(np.array(updated_transform_data, dtype='f4').tobytes())
        self.__updated_transform_buffer.bind_to_storage_buffer(1)

        groups_x = (len(updated_transform_data) + 63) // 64

        IndirectRenderController.__matrix_update_compute.run(group_x=groups_x)

        self._updated_transform_indices.clear()
            
    def build_advanced_texture_atlas(self):
        if self.__texture_atlas != None and self.__texture_atlas_uv_data_buffer != None:
            return self.__texture_atlas, self.__texture_atlas_uv_data_buffer

        model_unique_textures = []
        model_unique_tex_uv_offsets = []
        
        width_needed = 0
        height_needed = 0
        
        components = 3 # RGB (or RGBA = 4 if needed)
        
        """ Find and log all unique cached textures used by models """
        for mod in self.__models:
            if mod.texture_cache not in model_unique_textures:
                tex: moderngl.Texture = Texture.get(mod.texture_cache)
                width_needed += tex.width
                height_needed = max(height_needed, tex.height)
                model_unique_textures.append(mod.texture_cache)
                
        """ Copy each unique texture into the atlas """
        texture_atlas: moderngl.Texture = CTX.texture((width_needed, height_needed), components)
        texture_atlas.filter = (moderngl.NEAREST, moderngl.NEAREST)  # Nearest neighbor filtering for pixel-perfect textures
        pixel_offset = (0, 0)
        uv_offset = (0.0, 0.0)
        for tex_cache in model_unique_textures:
            tex: moderngl.Texture = Texture.get(tex_cache)
            pixel_scale = (tex.width, tex.height)
            viewport: tuple[int, int, int, int] = (pixel_offset[0], pixel_offset[1], pixel_scale[0], pixel_scale[1])
            texture_atlas.write(tex.read(), viewport=viewport)
            pixel_offset = (pixel_offset[0] + pixel_scale[0], pixel_offset[1])
            model_unique_tex_uv_offsets.append(uv_offset)
            uv_offset = (uv_offset[0] + (tex.width / width_needed), uv_offset[1])

        """ Build UV data for each model to index into the atlas """
        texture_uv_data: list[tuple[float, float, float, float]] = []
        for mod in self.__models:
            tex: moderngl.Texture = Texture.get(mod.texture_cache)
            uv_scale = (tex.width / width_needed, tex.height / height_needed)
            uv_offset_index = model_unique_textures.index(mod.texture_cache)
            uv_offset = model_unique_tex_uv_offsets[uv_offset_index]
            # print(f"Model texture UV offset/scale: {uv_offset}, {uv_scale}")
            texture_uv_data.append((uv_offset[0], uv_offset[1], uv_scale[0], uv_scale[1]))
            
        self.__texture_atlas = texture_atlas
        self.__texture_atlas_uv_data_buffer = CTX.buffer(reserve=self.__max_models * 4 * 4)  # 4 floats per model
        self.__texture_atlas_uv_data_buffer.write(np.array(texture_uv_data, dtype='f4').tobytes())

        return self.__texture_atlas, self.__texture_atlas_uv_data_buffer

    def build_combined_vao(self):
        if self.__combined_vao is not None:
            return self.__combined_vao

        vbuf_np = np.concatenate([mod.positions for mod in self.__models], axis=0).astype('f4')  # shape (model_count*vertex_count, 3)
        self.__current_vertices = vbuf_np.shape[0]
        self.__combined_vbo = CTX.buffer(reserve=self.__max_vertices * 3 * 4)  # Pre-allocate max size
        self.__combined_vbo.write(vbuf_np.tobytes())
        texbuf_np = np.concatenate([mod.tex_coords for mod in self.__models], axis=0).astype('f4')
        self.__combined_tex_coords = CTX.buffer(reserve=self.__max_vertices * 2 * 4)  # Pre-allocate max size
        self.__combined_tex_coords.write(texbuf_np.tobytes())
        
        # Create a single VAO for all models
        self.__combined_vao = CTX.vertex_array(INDIRECT_PROGRAM, [(self.__combined_vbo, '3f', 'in_position'), (self.__combined_tex_coords, '2f', 'in_texcoord')])
        return self.__combined_vao
    
    def try_models_rebuild(self):
        if len(self.__added_models_this_frame) == 0:
            return
        
        """ Get some important information and change max capacities and buffers if needed """
        new_model_count = len(self.__models)
        vertex_delta = sum([mod.positions.shape[0] for mod in self.__added_models_this_frame])
        self.__current_vertices += vertex_delta
        does_exceed_model_capacity = new_model_count > self.__max_models
        does_exceed_vertex_capacity = self.__current_vertices > self.__max_vertices
        
        needed_groups = (len(self.__added_models_this_frame) + 63) // 64
            
        if (does_exceed_model_capacity):
            print("new max models:", self.__max_models + self.__models_increment)
            self.__max_models += self.__models_increment
            self.__indirect_buffer.orphan(size=self.__max_models * IndirectRenderController.__cmd_dtype.itemsize)
            self.__texture_atlas_uv_data_buffer.orphan(size=self.__max_models * 4 * 4)  # 4 floats per model
            needed_groups = (new_model_count + 63) // 64
            
        if (does_exceed_vertex_capacity):
            self.__max_vertices += self.__vertices_increment
            print("new max vertices:", (self.__combined_vbo.size // (3 * 4)), self.__max_vertices)
            self.__combined_vbo.orphan(size=self.__max_vertices * 3 * 4)
            self.__combined_tex_coords.orphan(size=self.__max_vertices * 2 * 4)
            needed_groups = (new_model_count + 63) // 64
            
        """ Compute new / addition buffer data """
        ### BUILD INDIRECT BUFFER
        commands = np.zeros(len(self.__added_models_this_frame), dtype=IndirectRenderController.__cmd_dtype)
        offset = 0
        for i in range(len(self.__added_models_this_frame)):
            commands[i]['count'] = self.__added_models_this_frame[i].positions.shape[0]
            commands[i]['instanceCount'] = 1
            commands[i]['first'] = offset
            commands[i]['baseInstance'] = i  # which model matrix to use
            offset += self.__added_models_this_frame[i].positions.shape[0]
            
        self.__added_indirect_buffer.orphan(size=len(self.__added_models_this_frame) * IndirectRenderController.__cmd_dtype.itemsize)
        self.__added_indirect_buffer.write(commands.tobytes())
        
        ### BUILD TEXTURE UV DATA
        """ REFACTOR THE INITIAL FUNCTION FOR THIS FOR THIS TO BE ABLE TO WORK"""
        self.__added_texture_atlas_uv_data_buffer.orphan(size=len(self.__added_models_this_frame) * 4 * 4)  # 4 floats per model
        
        ### BUILD COMBINED VBO
        vbuf_np = np.concatenate([mod.positions for mod in self.__added_models_this_frame], axis=0).astype('f4')  # shape (model_count*vertex_count, 3)
        self.__added_combined_vbo.orphan(size=vertex_delta * 3 * 4)
        self.__added_combined_vbo.write(vbuf_np.tobytes())
        
        ### BUILD COMBINED TEX COORDS
        texbuf_np = np.concatenate([mod.tex_coords for mod in self.__added_models_this_frame], axis=0).astype('f4')
        self.__added_combined_tex_coords.orphan(size=vertex_delta * 2 * 4)
        self.__added_combined_tex_coords.write(texbuf_np.tobytes())
        
            
        """ Run the compute shader to add to the buffers with new model data """
        
        set_compute_uniforms(IndirectRenderController.__model_capacity_update_compute, {
            'newModelCount': new_model_count,
            'modelDelta': len(self.__added_models_this_frame),
            'newVertexCount': self.__current_vertices,
            'vertexDelta': vertex_delta,
        }, log_missing=True)
        # IndirectRenderController.__model_capacity_update_compute['newModelCount'].value = new_model_count
        # IndirectRenderController.__model_capacity_update_compute['modelDelta'].value = len(self.__added_models_this_frame)
        # IndirectRenderController.__model_capacity_update_compute['newVertexCount'].value = self.__current_vertices
        # IndirectRenderController.__model_capacity_update_compute['vertexDelta'].value = vertex_delta
        
        self.__indirect_buffer.bind_to_storage_buffer(0)
        self.__texture_atlas_uv_data_buffer.bind_to_storage_buffer(1)
        self.__combined_vbo.bind_to_storage_buffer(2)
        self.__combined_tex_coords.bind_to_storage_buffer(3)
        
        self.__added_indirect_buffer.bind_to_storage_buffer(4)
        self.__added_texture_atlas_uv_data_buffer.bind_to_storage_buffer(5)
        self.__added_combined_vbo.bind_to_storage_buffer(6)
        self.__added_combined_tex_coords.bind_to_storage_buffer(7)
        
        IndirectRenderController.__model_capacity_update_compute.run(group_x=needed_groups)
                
        if (self.__combined_vao != None):
            self.__combined_vao.release()
        # Rebuild the Vertex Array Object
        self.__combined_vao = CTX.vertex_array(INDIRECT_PROGRAM, [(self.__combined_vbo, '3f', 'in_position'), (self.__combined_tex_coords, '2f', 'in_texcoord')])
        
        self.__added_models_this_frame.clear()
        
        
    
    def render_indirect(self):
        indirect_buffer: moderngl.Buffer = self.build_indirect_command_buffer()
        matrix_buffer: moderngl.Buffer = self.build_matrix_ssbo()
        texture_atlas, texture_uv_data_buffer = self.build_advanced_texture_atlas()
        combined_vao: moderngl.VertexArray = self.build_combined_vao()
        model_count: int = self.__model_count

        self.try_models_rebuild()

        # Since using raw OpenGL calls, first bind the passed in program
        glUseProgram(INDIRECT_PROGRAM.glo)

        glBindBuffer(GL_DRAW_INDIRECT_BUFFER, indirect_buffer.glo)
        matrix_buffer.bind_to_storage_buffer(0) # Bind Model matrix SSBO to binding point 0
        texture_uv_data_buffer.bind_to_storage_buffer(1)
        texture_atlas.use(2)
        # Bind the vao and issue the multi-draw indirect call
        glBindVertexArray(combined_vao.glo)
        glMultiDrawArraysIndirect(GL_TRIANGLES, None, model_count, 0)
        glBindVertexArray(0)