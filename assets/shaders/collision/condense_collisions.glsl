#version 430

layout (local_size_x = 64) in;

layout (std430, binding = 3) buffer in_collision_info {
    float collision_indexes[];
};

layout (std430, binding = 4) buffer out_condensed_info {
    uint condensed_indexes[];
};

layout (std430, binding = 5) buffer counter_buffer {
    uint current_index;
};

uniform int num_vertices;

void main() {
    uint idx = gl_GlobalInvocationID.x;
    if (idx >= num_vertices / 3) return;

    if (collision_indexes[idx] == 1.0) {
        uint write_index = atomicAdd(current_index, 1);
        condensed_indexes[write_index] = idx;
    }
}