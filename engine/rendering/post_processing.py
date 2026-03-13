import numpy as np
from ..constants import CTX, WIDTH, HEIGHT

class PPRPass:
    def __init__(self, fragment_shader_source):
        self.prog = CTX.program(
            vertex_shader="""
            #version 330
            in vec2 in_pos;
            in vec2 in_uv;
            out vec2 uv;
            void main() {
                uv = in_uv;
                gl_Position = vec4(in_pos, 0.0, 1.0);
            }
            """,
            fragment_shader=fragment_shader_source,
        )

        self.quad_data = np.array([
            -1.0, -1.0, 0.0, 0.0,
            1.0, -1.0, 1.0, 0.0,
            -1.0,  1.0, 0.0, 1.0,
            -1.0,  1.0, 0.0, 1.0,
            1.0, -1.0, 1.0, 0.0,
            1.0,  1.0, 1.0, 1.0,
        ], dtype="f4")
        self.quad_vbo = CTX.buffer(self.quad_data.tobytes())
        self.quad_vao = CTX.vertex_array(self.prog, [(self.quad_vbo, "2f 2f", "in_pos", "in_uv")])

        self.fbo = CTX.framebuffer(color_attachments=[CTX.texture((WIDTH, HEIGHT), 4)],
                                   depth_attachment=CTX.depth_renderbuffer((WIDTH, HEIGHT)))

    def apply(self, input_texture):
        self.fbo.use()
        self.fbo.clear(0.0, 0.0, 0.0, 0.0, depth=1.0)

        input_texture.use(location=0)
        self.prog["tex"].value = 0

        self.quad_vao.render()

class PPR:
    __scene_tex = CTX.texture((WIDTH, HEIGHT), 4)
    __scene_fb = CTX.framebuffer(color_attachments=[__scene_tex],
                            depth_attachment=CTX.depth_renderbuffer((WIDTH, HEIGHT)))

    __passes: list[PPRPass] = [
        PPRPass(
            """
            #version 330
            uniform sampler2D tex;
            in vec2 uv;
            out vec4 fragColor;
            void main() {
                vec3 color = texture(tex, uv).rgb;
                
                float avg_color_r = color.r;
                float avg_color_g = color.g;
                float avg_color_b = color.b;
                
                int x_start = -5;
                int x_end = 5;

                int y_start = -5;
                int y_end = 5;

                for (int x = x_start; x <= x_end; x++) {
                    for (int y = y_start; y <= y_end; y++) {
                        if (x == 0 && y == 0) continue; // Skip the center pixel
                        vec2 offset = vec2(float(x), float(y)) / vec2(textureSize(tex, 0));
                        vec2 sampleUV = uv + offset;
                        if (sampleUV.x < 0.0 || sampleUV.x > 1.0 || sampleUV.y < 0.0 || sampleUV.y > 1.0) {
                            continue; // Skip out-of-bounds samples
                        }
                        vec3 neighbor_color = texture(tex, sampleUV).rgb;
                        avg_color_r += neighbor_color.r;
                        avg_color_g += neighbor_color.g;
                        avg_color_b += neighbor_color.b;
                    }
                }
                
                float num_samples = (x_end - x_start + 1) * (y_end - y_start + 1);

                fragColor = vec4(color.r + (avg_color_r / num_samples) * (1 - color.r), color.g + (avg_color_g / num_samples) * (1 - color.g), color.b + (avg_color_b / num_samples) * (1 - color.b), 1.0);
            }
            """
        ),
        PPRPass(
            """
            #version 330
            uniform sampler2D tex;
            in vec2 uv;
            out vec4 fragColor;

            // simple hash-based random
            float rand(vec2 co) {
                return fract(sin(dot(co, vec2(12.9898,78.233))) * 43758.5453);
            }
            
            float IGN(int pixelX, int pixelY)
            {
                // Use GLSL fract() and standard float literals (no 'f' suffix).
                // This produces a deterministic pseudo-random value in [0,1).
                return fract(52.9829189 * fract(0.06711056 * float(pixelX) + 0.00583715 * float(pixelY)));
            }

            void main() {
                ivec2 sz = textureSize(tex, 0);
                // compute integer pixel coordinate of current fragment
                ivec2 center = ivec2(clamp(floor(uv * vec2(sz)), vec2(0.0), vec2(sz) - vec2(1.0)));

                // radius in pixels
                float R = 1;

                // generate two random numbers based on the pixel coordinate
                float r1 = rand(vec2(center)); // IGN(int(center.x), int(center.y));
                float r2 = rand(vec2(center) + vec2(73.123, 41.937)); // IGN(int(center.x) + 73, int(center.y) + 41);

                // polar coordinates: angle in [0,2pi), radius distribution sqrt(u)*R for uniform in circle
                float angle = r1 * 6.28318530718;
                float radius = sqrt(r2) * R;

                // offset in float pixels, round to nearest integer pixel offset
                vec2 ofsF = vec2(cos(angle), sin(angle)) * radius;
                ivec2 ofs = ivec2(round(ofsF));

                ivec2 samplePix = clamp(center + ofs, ivec2(0), sz - ivec2(1));
                vec2 sampleUV = (vec2(samplePix) + 0.5) / vec2(sz);

                vec4 c = texture(tex, sampleUV);
                fragColor = vec4(c.rgb, 1.0);
            }
            """
        ),
        PPRPass(
            """
            #version 330
            uniform sampler2D tex;
            in vec2 uv;
            out vec4 fragColor;

            int roundToNearest(int value, int n) {
                return ((value + n / 2) / n) * n;
            }

            void main() {
                ivec2 sz = textureSize(tex, 0);
                ivec2 pixelCoord = ivec2(clamp(floor(uv * vec2(sz)), vec2(0.0), vec2(sz) - vec2(1.0)));
                int blockSize = abs(int((uv.x - 0.5) * 10.0)) + 1; // Size of the pixelation block
                ivec2 pixelatedCoord = ivec2(roundToNearest(pixelCoord.x, blockSize), roundToNearest(pixelCoord.y, blockSize));
                vec2 pixelatedUV = (vec2(pixelatedCoord) + 0.5) / vec2(sz);
                vec4 color = texture(tex, pixelatedUV);
                // Simple inversion effect
                fragColor = vec4(color.rgb, 1.0);
            }
            """
        ),
    ]

    __final_pass = PPRPass(
        """
            #version 330
            uniform sampler2D tex;
            in vec2 uv;
            out vec4 fragColor;
            void main() {
                fragColor = texture(tex, uv);
            }
        """
    )

    @staticmethod
    def begin_frame_post_processing():
        PPR.__scene_fb.use()
        PPR.__scene_fb.clear(0.0, 0.0, 0.0, 0.0, depth=1.0)

    @staticmethod
    def end_frame_post_processing():
        input_tex = PPR.__scene_tex
        for ppr_pass in PPR.__passes:
            ppr_pass.apply(input_tex)
            input_tex = ppr_pass.fbo.color_attachments[0]

        CTX.screen.use()
        CTX.clear(0.0, 0.0, 0.0, 0.0, depth=1.0)
        input_tex.use(location=0)
        PPR.__final_pass.prog["tex"].value = 0
        PPR.__final_pass.quad_vao.render()
 