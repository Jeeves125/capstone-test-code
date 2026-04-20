#version 430
#extension GL_ARB_shader_draw_parameters : enable

layout(std430, binding = 0) buffer Models {
    mat4 model[];
};

layout(std430, binding = 1) buffer TextureUVData {
    vec4 texture_uv_data[];
};

layout(location = 0) in vec3 in_position;
layout(location = 1) in vec2 in_texcoord;

out vec2 v_uv;
out vec3 v_world_pos;
out vec2 v_texcoord;
flat out vec4 v_texture_uv_data;

uniform mat4 projection;
uniform mat4 view;

void main() {
    vec4 world_pos = model[gl_BaseInstanceARB] * vec4(in_position, 1.0);
    v_world_pos = world_pos.xyz;
    v_uv = in_position.xy * 0.5 + 0.5;
    v_texcoord = in_texcoord;
    v_texture_uv_data = texture_uv_data[gl_BaseInstanceARB];

    gl_Position = projection * view * world_pos;
}