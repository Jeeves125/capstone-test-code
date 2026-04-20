#version 330
uniform sampler2D model_tex;
in vec2 v_uv;
in vec2 v_texcoord;
in vec3 v_world_pos;

out vec4 f_color;

uniform vec3 tint;
uniform float time;
uniform bool use_flat_shading;

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
    
    vec4 texColor = texture(model_tex, v_texcoord);
    
    f_color = texColor * lighting;
    f_color.rgb += tint * 0.3;
    f_color.rgb = tint * lighting;
    f_color.a = texColor.a;
}