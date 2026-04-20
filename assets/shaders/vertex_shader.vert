#version 330
in vec3 in_position;
in vec2 in_texcoord;
out vec2 v_uv;
out vec2 v_texcoord;
out vec3 v_world_pos;     // world-space position

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

void main() {
  v_uv = in_position.xy * 0.5 + 0.5;
  v_texcoord = in_texcoord;
  // World position and normal (normal mat approximated as upper-left of model)
  vec4 world_pos = model * vec4(in_position, 1.0);
  v_world_pos = world_pos.xyz;
  gl_Position = projection * view * world_pos;
}