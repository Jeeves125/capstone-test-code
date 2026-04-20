#version 430
in vec3 v_color;
out vec4 f_color;

void main() {
    vec2 point_coord = gl_PointCoord - vec2(0.5);

    if (length(point_coord) > 0.5) {
        discard;
    }

    f_color = vec4(v_color, 1);
}