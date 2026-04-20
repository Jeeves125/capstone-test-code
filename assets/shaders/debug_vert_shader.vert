#version 430
// in float in_collided;
in vec3 in_vert;
in vec3 in_color;
out vec3 v_color;

uniform mat4 view;
uniform mat4 projection;
uniform bool use_distance_based;

void main() {
  vec4 view_pos = view * vec4(in_vert.xyz, 1.0);
  gl_Position = projection * view_pos;
  
  if (use_distance_based) {
    // Calculate point size based on distance
    float distance = length(view_pos.xyz);
    gl_PointSize = 500.0 / distance;  // Adjust the 100.0 to control base size
  } else {
    gl_PointSize = 10.0; // Fixed size
  }

  v_color = in_color;
}