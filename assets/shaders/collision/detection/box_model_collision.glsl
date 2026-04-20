#version 430

layout (local_size_x = 64) in;

layout (std430, binding = 3) buffer vert_buffer {
    float verts[];
};

layout (std430, binding = 4) buffer out_collision_info {
    // For each triangle, store:
    // 0: collision detected (1.0 for yes, 0.0 for no)
    // 1: collision point x
    // 2: collision point y
    // 3: collision point z
    float data[];
};

uniform int num_vertices;
uniform vec3 box_center;
uniform vec3 box_halfsize;

int box_to_triangle_intersection(vec3 v1, vec3 v2, vec3 v3, vec3 box_center, vec3 box_halfsize) {
    vec3 p1 = vec3(v1);
    vec3 p2 = vec3(v2);
    vec3 p3 = vec3(v3);
    vec3 center = box_center;
    vec3 halfsize = box_halfsize;

    // 1. Test the triangle normal
    // Compute the triangle normal
    vec3 edge1 = p2 - p1;
    vec3 edge2 = p3 - p1;
    vec3 normal = cross(edge1, edge2);
    float normal_length = length(normal);
    if (normal_length < 1e-8) { 
        return 0;
    }
    normal = normal / normal_length;  // Normalize

    // Project the box onto the triangle normal
    float r = halfsize.x * abs(normal.x) + halfsize.y * abs(normal.y) + halfsize.z * abs(normal.z);
    
    // Project all triangle vertices onto the normal
    float s = dot(normal, p1);
    float dist = dot(normal, center) - s;

    // If the distance from the box center to the triangle plane exceeds the box's projection length,
    // then they cannot intersect
    if (abs(dist) > r) {
        return 0;
    }

    // 2. Test the 9 edge cross products
    // For all 3 box axes and all 3 triangle edges, we need to check 9 potential separating axes
    // formed by the cross product of a box axis and triangle edge
    vec3 box_axes[3] = {vec3(1, 0, 0), vec3(0, 1, 0), vec3(0, 0, 1)};
    vec3 triangle_edges[3] = {edge1, p3 - p2, p1 - p3};

    for (int i = 0; i < 3; i++) {  // Box axes
        for (int j = 0; j < 3; j++) {  // Triangle edges
            vec3 axis = cross(box_axes[i], triangle_edges[j]);
            float axis_length = length(axis);
            if (axis_length < 1e-8) {  // Skip near-parallel edges
                continue;
            }
            
            axis = axis / axis_length;  // Normalize

            // Project the box onto the axis
            float r = halfsize[0] * abs(dot(axis, box_axes[0])) +
                      halfsize[1] * abs(dot(axis, box_axes[1])) +
                      halfsize[2] * abs(dot(axis, box_axes[2]));

            // Project triangle onto axis
            float p0 = dot(p1, axis);
            float p1_proj = dot(p2, axis);
            float p2_proj = dot(p3, axis);
            float min_proj = min(min(p0, p1_proj), p2_proj);
            float max_proj = max(max(p0, p1_proj), p2_proj);

            // Project box center onto axis
            float center_proj = dot(center, axis);

            // No intersection if the projections don't overlap
            if (min_proj > center_proj + r || max_proj < center_proj - r) {
                return 0;
            }
        }
    }

    // 3. Test the box face normals (AABB vs triangle vertices)
    for (int i = 0; i < 3; i++) {
        // Project triangle vertices onto this axis
        float vmin = min(min(p1[i], p2[i]), p3[i]);
        float vmax = max(max(p1[i], p2[i]), p3[i]);

        // No intersection if the projections don't overlap
        if (vmax < center[i] - halfsize[i] || vmin > center[i] + halfsize[i]) {
            return 0;
        }
    }

    // All tests passed, there is an intersection
    return 1;
}

vec3 get_vert(int index) {
    return vec3(verts[index * 3 + 0], verts[index * 3 + 1], verts[index * 3 + 2]);
}

float get_slope(vec3 v0, vec3 v1, vec3 v2) {
    vec3 edge1 = v1 - v0;
    vec3 edge2 = v2 - v0;
    vec3 normal = cross(edge1, edge2);
    float normal_length = length(normal);
    if (normal_length < 1e-8) return 0.0;
    normal = normal / normal_length; // Normalize
    return abs(normal.z); // Slope is related to the z-component of the normal
}

float max_slope = -1.0;

void main() {
  int idx = int(gl_GlobalInvocationID.x);
  if (idx >= num_vertices / 3) return; // Guard against out-of-bounds

  vec3 v0 = get_vert(idx * 3 + 0);
  vec3 v1 = get_vert(idx * 3 + 1);
  vec3 v2 = get_vert(idx * 3 + 2);

  int collision = box_to_triangle_intersection(v0, v1, v2, box_center, box_halfsize);
  // Write if a collision happened, and the 

  float slope = get_slope(v0, v1, v2); // Calculate slope of the triangle
  if (collision == 1 && slope > max_slope) {
    data[0] = float(collision); // Only write to first element if collision detected
    data[1] = v0.x; // First vertex x
    data[2] = v0.y; // First vertex y
    data[3] = v0.z; // First vertex z
    data[4] = v1.x; // Second vertex x
    data[5] = v1.y; // Second vertex y
    data[6] = v1.z; // Second vertex z
    data[7] = v2.x; // Third vertex x
    data[8] = v2.y; // Third vertex y
    data[9] = v2.z; // Third vertex z
    max_slope = slope;
  }
}