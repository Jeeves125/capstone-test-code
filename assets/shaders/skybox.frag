#version 330

in vec3 tex_dir;

uniform samplerCube skybox;

out vec4 fragColor;

void main() {
    fragColor = texture(skybox, tex_dir);
    vec3 color = tex_dir / length(tex_dir) * 0.5 + 0.5;
    
    fragColor = vec4(color, 1.0);
}