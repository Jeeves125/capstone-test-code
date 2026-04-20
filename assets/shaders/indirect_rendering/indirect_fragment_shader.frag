#version 430
in vec2 v_uv;
in vec3 v_world_pos;
in vec2 v_texcoord;
flat in vec4 v_texture_uv_data;

out vec4 f_color;

// layout(binding = 2) uniform sampler2DArray texture_array;
layout(binding = 2) uniform sampler2D texture_atlas;

uniform vec4 tint;
uniform float time;

void main() {
    float cos_time = cos(time * 0.5);
    float sin_time = sin(time * 0.5);
    
    vec3 lightDir = vec3(cos_time, 0.0, sin_time);
    
    vec3 normal;
    vec3 dx = dFdx(v_world_pos);
    vec3 dy = dFdy(v_world_pos);
    normal = normalize(cross(dx, dy));
    
    float diffuse = dot(normal, lightDir) * 0.3;
    float lighting = clamp(0.3 + diffuse * 0.7, 0.0, 1.0) * 2.0;
    lighting = min(lighting, 1.0);
    vec2 texture_uv_offset = v_texture_uv_data.xy;
    vec2 texture_uv_scale = v_texture_uv_data.zw;
    vec4 tex = texture(texture_atlas, v_texcoord * texture_uv_scale + texture_uv_offset);
    f_color = vec4(tex.rgb * lighting, tex.a);
    f_color *= tint;
}