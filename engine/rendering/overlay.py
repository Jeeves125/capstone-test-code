from ..constants import CTX, WIDTH, HEIGHT
import struct, pygame, moderngl

class Overlay(pygame.Surface):
    # Small screen-space quad (we’ll scale/offset it for the text)
    __overlay_prog = CTX.program(
        vertex_shader='''
            #version 330
            in vec2 in_pos;
            out vec2 uv;
            uniform vec2 pos;
            uniform vec2 scale;
            void main() {
                uv = (in_pos + 1.0) * 0.5;
                vec2 ndc_pos = pos + in_pos * scale;
                gl_Position = vec4(ndc_pos, 0.0, 1.0);
            }
        ''',
        fragment_shader='''
            #version 330
            uniform sampler2D tex;
            in vec2 uv;
            out vec4 fragColor;
            void main() {
                vec4 c = texture(tex, uv);
                // Smooth alpha blending (no hard discard)
                fragColor = c;
            }
        '''
    )

    __overlay_vbo = CTX.buffer(struct.pack(
        "12f",
        -1.0, -1.0,
        1.0, -1.0,
        -1.0,  1.0,
        1.0, -1.0,
        1.0,  1.0,
        -1.0,  1.0
    ))
    __vao_overlay = CTX.simple_vertex_array(__overlay_prog, __overlay_vbo, 'in_pos')

    def __init__(self):
        super().__init__((WIDTH, HEIGHT), pygame.SRCALPHA)
        # Create a persistent texture to avoid per-frame allocations/leaks
        self._tex = CTX.texture((WIDTH, HEIGHT), 4)
        self._tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
    
    def render(self):
        surface_data = pygame.image.tostring(self, "RGBA", True)
        surface_w, surface_h = self.get_size()

        # Reuse the same GL texture; just update its contents each frame
        if (self._tex.size != (surface_w, surface_h)):
            # In case the surface size changes in the future, recreate safely
            self._tex.release()
            self._tex = CTX.texture((surface_w, surface_h), 4)
            self._tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

        self._tex.write(surface_data)
        self._tex.use(0)

        # Draw with blending enabled
        CTX.enable(moderngl.BLEND)
        CTX.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

        CTX.disable(moderngl.DEPTH_TEST)
        Overlay.__overlay_prog['tex'].value = 0
        Overlay.__overlay_prog['pos'].value = (0, 0)
        Overlay.__overlay_prog['scale'].value = (1, 1)
        Overlay.__vao_overlay.render(moderngl.TRIANGLES)
        CTX.enable(moderngl.DEPTH_TEST)
