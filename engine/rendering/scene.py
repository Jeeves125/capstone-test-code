import moderngl, numpy as np
from .model import IGameObject, Model
from ..constants import CTX, WIDTH, HEIGHT, PROGRAM, INDIRECT_PROGRAM
from .camera import Camera, create_view_matrix
from .overlay import Overlay
from .post_processing import PPR
from .file_loader import load_compute_shader
from .texture import Texture
from .indirect_render_controller import IndirectRenderController

class Scene:
    def __init__(self, scene_x = 0, scene_y = 0, scene_width: int = WIDTH, scene_height: int = HEIGHT):
        self.__renderables: list[IGameObject] = []
        self.__views: list[tuple[Camera, Overlay, tuple[int, int, int, int]]] = []
        self.__indirect_render_controller: IndirectRenderController = IndirectRenderController()
        self.viewport = (scene_x, scene_y, scene_width, scene_height)

    def add_updated_transform_index(self, index: int):
        self.__indirect_render_controller._updated_transform_indices.add(index)

    def add_object(self, obj: IGameObject):
        self.__renderables.append(obj)
        
        print("Adding object to indirect render controller")
        self.__indirect_render_controller.add_model(obj)
        obj.parent_scene = self

    def add_objects(self, objs: list[IGameObject]):
        self.__renderables.extend(objs)
        for obj in objs:
            self.__indirect_render_controller.add_model(obj)
            obj.parent_scene = self


    def add_view(self, camera: Camera = None, x: int = 0, y: int = 0, width: int = 1, height: int = 1):
        if not all(0 <= v <= 1 for v in (x, y, width, height)):
            raise ValueError(f"Viewport parameters x, y, width, height must be in the range (0, 1) but got ({x}, {y}, {width}, {height})")
        
        if camera == None:
            camera = Camera()

        scene_viewport = (self.viewport[0] + self.viewport[2] * x, self.viewport[1] + self.viewport[3] * y, self.viewport[2] * width, self.viewport[3] * height)
        self.__views.append((camera, scene_viewport))

    def render(self):
        prev_viewport = CTX.viewport
        prev_active_cam = Camera.active

        if (len(self.__views) == 0):
            CTX.viewport = self.viewport

            if len(self.__renderables) != 0:
                self.__indirect_render_controller.update_matrix_ssbo()
                self.__indirect_render_controller.render_indirect()

            # for obj in self.__renderables:
            #     obj.render()
                
            if Camera.active is not None and Camera.active.overlay is not None:
                Camera.active.overlay.render()
        else: 
            for view in self.__views:
                CTX.viewport = view[1]
                view[0].set_active()
                PROGRAM['view'].write(create_view_matrix().tobytes())

                if len(self.__renderables) != 0:
                    self.update_matrix_ssbo()

                    texture_atlas, texture_uv_data_buffer = self.build_advanced_texture_atlas()
                    Model.render_indirect(self.build_indirect_command_buffer(), self.build_matrix_ssbo(),
                                        texture_uv_data_buffer, texture_atlas, self.build_combined_vao(), len(self.__renderables))

                # for obj in self.__renderables:
                #     obj.render()
                    
                if view[0].overlay is not None:
                    view[0].overlay.render()

        CTX.viewport = prev_viewport
        if prev_active_cam is not None:
            prev_active_cam.set_active()
            