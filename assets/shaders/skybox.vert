#version 330

layout(location = 0) in vec3 in_pos;

uniform mat4 proj;
uniform mat4 view;

out vec3 tex_dir;

void main() {
    mat4 view_rot = mat4(mat3(view));

    tex_dir = in_pos;

    vec4 pos = proj * view_rot * vec4(in_pos, 1.0);
    gl_Position = pos.xyww;
}
