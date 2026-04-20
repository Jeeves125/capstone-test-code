#version 430

layout (local_size_x = 64) in;

layout (std430, binding = 3) buffer in_collision_info {
    float collision_indexes[];
};

layout (std430, binding = 4) buffer out_count_info {
    uint count;
};

uniform int num_vertices;

void main() {
    uint idx = gl_GlobalInvocationID.x;
    if (idx >= num_vertices / 3) return;
    
    if (collision_indexes[idx] == 1.0) {
        atomicAdd(count, 1);
    }
}
