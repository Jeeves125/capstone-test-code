#version 430
// Perlin Noise Implementation in GLSL
// Generates fractal noise with customizable parameters

// Improved hash function for better randomness
vec3 hash3(vec3 p) {
    p = vec3(dot(p, vec3(127.1, 311.7, 74.7)),
             dot(p, vec3(269.5, 183.3, 246.1)),
             dot(p, vec3(113.5, 271.9, 124.6)));
    return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}

vec2 hash2(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)),
             dot(p, vec2(269.5, 183.3)));
    return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}

// 3D Perlin noise with improved continuity
float perlin3d(vec3 p) {
    vec3 pi = floor(p);
    vec3 pf = p - pi;
    
    // Quintic interpolation for smoother results
    vec3 w = pf * pf * pf * (pf * (pf * 6.0 - 15.0) + 10.0);
    
    // Sample gradients at cube corners
    float c000 = dot(hash3(pi + vec3(0.0, 0.0, 0.0)), pf - vec3(0.0, 0.0, 0.0));
    float c001 = dot(hash3(pi + vec3(0.0, 0.0, 1.0)), pf - vec3(0.0, 0.0, 1.0));
    float c010 = dot(hash3(pi + vec3(0.0, 1.0, 0.0)), pf - vec3(0.0, 1.0, 0.0));
    float c011 = dot(hash3(pi + vec3(0.0, 1.0, 1.0)), pf - vec3(0.0, 1.0, 1.0));
    float c100 = dot(hash3(pi + vec3(1.0, 0.0, 0.0)), pf - vec3(1.0, 0.0, 0.0));
    float c101 = dot(hash3(pi + vec3(1.0, 0.0, 1.0)), pf - vec3(1.0, 0.0, 1.0));
    float c110 = dot(hash3(pi + vec3(1.0, 1.0, 0.0)), pf - vec3(1.0, 1.0, 0.0));
    float c111 = dot(hash3(pi + vec3(1.0, 1.0, 1.0)), pf - vec3(1.0, 1.0, 1.0));
    
    // Trilinear interpolation with quintic smoothing
    float c00 = mix(c000, c001, w.z);
    float c01 = mix(c010, c011, w.z);
    float c10 = mix(c100, c101, w.z);
    float c11 = mix(c110, c111, w.z);
    
    float c0 = mix(c00, c01, w.y);
    float c1 = mix(c10, c11, w.y);
    
    return mix(c0, c1, w.x);
}

// 2D Perlin noise with improved continuity
float perlin2d(vec2 p) {
    vec2 pi = floor(p);
    vec2 pf = p - pi;
    
    // Quintic interpolation for smoother results
    vec2 w = pf * pf * pf * (pf * (pf * 6.0 - 15.0) + 10.0);
    
    // Sample gradients at square corners
    float c00 = dot(hash2(pi), pf);
    float c01 = dot(hash2(pi + vec2(0.0, 1.0)), pf - vec2(0.0, 1.0));
    float c10 = dot(hash2(pi + vec2(1.0, 0.0)), pf - vec2(1.0, 0.0));
    float c11 = dot(hash2(pi + vec2(1.0, 1.0)), pf - vec2(1.0, 1.0));
    
    // Bilinear interpolation with quintic smoothing
    float c0 = mix(c00, c01, w.y);
    float c1 = mix(c10, c11, w.y);
    
    return mix(c0, c1, w.x);
}

// Main Perlin Noise function with all parameters
// pos: position (vec2 or vec3)
// scale: overall scale of the noise
// octaves: number of noise layers
// persistence: amplitude multiplier for each octave
// lacunarity: frequency multiplier for each octave
// time: time parameter for animation
float perlinNoise(vec3 pos, float scale, int octaves, float persistence, float lacunarity, float time) {
    vec3 p = pos * scale;
    p.z += time; // Add time to Z dimension for animation
    
    float amplitude = 1.0;
    float frequency = 1.0;
    float value = 0.0;
    float maxValue = 0.0; // For normalization
    
    for (int i = 0; i < octaves; i++) {
        value += perlin3d(p * frequency) * amplitude;
        maxValue += amplitude;
        amplitude *= persistence;
        frequency *= lacunarity;
    }
    
    return value / maxValue; // Normalize to [-1, 1] range
}

// Overload for 2D positions
float perlinNoise(vec2 pos, float scale, int octaves, float persistence, float lacunarity, float time) {
    vec2 p = pos * scale;
    
    float amplitude = 1.0;
    float frequency = 1.0;
    float value = 0.0;
    float maxValue = 0.0;
    
    for (int i = 0; i < octaves; i++) {
        // Add time as an offset to create animation
        vec2 animatedPos = p * frequency + vec2(time * 0.1, time * 0.05);
        value += perlin2d(animatedPos) * amplitude;
        maxValue += amplitude;
        amplitude *= persistence;
        frequency *= lacunarity;
    }
    
    return value / maxValue;
}

layout(local_size_x = 8, local_size_y = 8) in;

layout(std430, binding = 0) buffer vert_buffer {
    float verts[];
};

layout(std430, binding = 1) buffer norm_buffer {
    float norms[];
};

layout(std430, binding = 2) buffer tex_buffer {
    float tex_coords[];
};

// uniform int width;
// uniform int height;
uniform float time;
uniform int lod; // Level of detail
uniform int lod_size;
uniform float offset_x;
uniform float offset_z;

vec3 get_vert_pos(float x, float z) {
    // Use uniform offsets for controllable noise positioning
    float noise1 = perlinNoise(vec2(x + offset_x, z + offset_z), 0.005, 2, 0.5, 2.0, time);
    float noise2 = perlinNoise(vec2(x + offset_x, z + offset_z), 0.005, 7, 1, 2.0, time);

    noise1 = (noise1 / 5.0) * (0.681 * (pow(46.416, noise1)));
    float height = (noise1 + (max(0.0, noise1) * noise2));

    // return vec4(1.0, 1.0, 1.0, 0.0);
    return vec3(x, height * 1000.0, z);
}

void write_vert(int index, vec3 vert) {
    verts[index * 3 + 0] = vert.x;
    verts[index * 3 + 1] = vert.y;
    verts[index * 3 + 2] = vert.z;
}

void write_norm(int index, vec3 norm) {
    norms[index * 3 + 0] = norm.x;
    norms[index * 3 + 1] = norm.y;
    norms[index * 3 + 2] = norm.z;
}

void write_tex(int index, vec2 tex) {
    tex_coords[index * 2 + 0] = tex.x;
    tex_coords[index * 2 + 1] = tex.y;
}

void main() {
    vec2 pos = gl_GlobalInvocationID.xy;
    // float noise = perlinNoise(pos, 100.0, 4, 0.5, 2.0, time);

    // Guard: extra threads from workgroup padding (when width/height not multiples of 16)
    // would otherwise write out-of-bounds causing undefined buffer data.
    if (pos.x >= lod_size || pos.y >= lod_size) return;
    int index = int((pos.x + pos.y * (lod_size)) * 6);

    int lod_add = 1 << lod; // safer and exact (2^lod)

    float x = pos.x * lod_add;
    float z = pos.y * lod_add;

    // 1st triangle
    write_vert(index + 0, get_vert_pos(x, z));
    write_vert(index + 1, get_vert_pos(x, z + lod_add));
    write_vert(index + 2, get_vert_pos(x + lod_add, z));
    write_norm(index + 0, vec3(0, 0, 1));
    write_norm(index + 1, vec3(0, 0, 1));
    write_norm(index + 2, vec3(0, 0, 1));
    write_tex(index + 0, vec2(0, 0));
    write_tex(index + 1, vec2(0, 1));
    write_tex(index + 2, vec2(1, 0));

    // 2nd triangle
    write_vert(index + 3, get_vert_pos(x + lod_add, z));
    write_vert(index + 4, get_vert_pos(x, z + lod_add));
    write_vert(index + 5, get_vert_pos(x + lod_add, z + lod_add));
    write_norm(index + 3, vec3(0, 0, 1));
    write_norm(index + 4, vec3(0, 0, 1));
    write_norm(index + 5, vec3(0, 0, 1));
    write_tex(index + 3, vec2(1.0, 0.0));
    write_tex(index + 4, vec2(0.0, 1.0));
    write_tex(index + 5, vec2(1.0, 1.0));
}