#version 430

layout (local_size_x = 64) in;

layout (std430, binding = 3) buffer vert_buffer {
    float verts[];
};

layout (std430, binding = 4) buffer out_collision_info {
    float indexes[];
};

uniform int num_vertices;
uniform bool verbose;

uniform vec3 capsule_start;
uniform vec3 capsule_end;
uniform float capsule_radius;

uniform mat4 model_matrix;

vec3 get_vert(uint index) {
    uint base_idx = index * 3;
    return vec3(verts[base_idx], verts[base_idx + 1], verts[base_idx + 2]);
}

// Get closest point on line segment to a point
vec3 closest_point_on_segment(vec3 p, vec3 a, vec3 b) {
    vec3 ab = b - a;
    float t = dot(p - a, ab) / dot(ab, ab);
    t = clamp(t, 0.0, 1.0);
    return a + t * ab;
}

// Get closest point on triangle to a point
vec3 closest_point_on_triangle(vec3 p, vec3 a, vec3 b, vec3 c) {
    // Check if point projects inside triangle
    vec3 ab = b - a;
    vec3 ac = c - a;
    vec3 ap = p - a;
    
    float d1 = dot(ab, ap);
    float d2 = dot(ac, ap);
    if (d1 <= 0.0 && d2 <= 0.0) return a;
    
    vec3 bp = p - b;
    float d3 = dot(ab, bp);
    float d4 = dot(ac, bp);
    if (d3 >= 0.0 && d4 <= d3) return b;
    
    float vc = d1 * d4 - d3 * d2;
    if (vc <= 0.0 && d1 >= 0.0 && d3 <= 0.0) {
        float v = d1 / (d1 - d3);
        return a + v * ab;
    }
    
    vec3 cp = p - c;
    float d5 = dot(ab, cp);
    float d6 = dot(ac, cp);
    if (d6 >= 0.0 && d5 <= d6) return c;
    
    float vb = d5 * d2 - d1 * d6;
    if (vb <= 0.0 && d2 >= 0.0 && d6 <= 0.0) {
        float w = d2 / (d2 - d6);
        return a + w * ac;
    }
    
    float va = d3 * d6 - d5 * d4;
    if (va <= 0.0 && (d4 - d3) >= 0.0 && (d5 - d6) >= 0.0) {
        float w = (d4 - d3) / ((d4 - d3) + (d5 - d6));
        return b + w * (c - b);
    }
    
    float denom = 1.0 / (va + vb + vc);
    float v = vb * denom;
    float w = vc * denom;
    return a + ab * v + ac * w;
}

// Distance from point to line segment
float point_segment_distance(vec3 p, vec3 a, vec3 b) {
    vec3 closest = closest_point_on_segment(p, a, b);
    return length(p - closest);
}

// Capsule to triangle collision detection
bool capsule_to_triangle_intersection(vec3 v1, vec3 v2, vec3 v3, 
                                       vec3 cap_start, vec3 cap_end, 
                                       float cap_radius,
                                       out float dist,
                                       out vec3 collision_point) {
    
    // Find closest point on capsule segment to each triangle vertex
    float min_dist = 1e10;
    vec3 best_point = vec3(0.0);
    
    // Test capsule segment against triangle vertices
    for (int i = 0; i < 3; i++) {
        vec3 vert = (i == 0) ? v1 : ((i == 1) ? v2 : v3);
        vec3 closest_on_cap = closest_point_on_segment(vert, cap_start, cap_end);
        float d = length(vert - closest_on_cap);
        if (d < min_dist) {
            min_dist = d;
            best_point = closest_on_cap;
        }
    }
    
    // Test triangle edges against capsule endpoints
    vec3 edges[3] = vec3[3](v2 - v1, v3 - v2, v1 - v3);
    vec3 edge_starts[3] = vec3[3](v1, v2, v3);
    
    for (int i = 0; i < 3; i++) {
        vec3 edge_start = edge_starts[i];
        vec3 edge_end = edge_start + edges[i];
        
        // Distance from capsule start to edge
        float d1 = point_segment_distance(cap_start, edge_start, edge_end);
        if (d1 < min_dist) {
            min_dist = d1;
            best_point = cap_start;
        }
        
        // Distance from capsule end to edge
        float d2 = point_segment_distance(cap_end, edge_start, edge_end);
        if (d2 < min_dist) {
            min_dist = d2;
            best_point = cap_end;
        }
        
        // Closest points between two line segments (capsule and edge)
        vec3 capsule_dir = cap_end - cap_start;
        vec3 edge_dir = edges[i];
        vec3 r = cap_start - edge_start;
        
        float a = dot(capsule_dir, capsule_dir);
        float b = dot(capsule_dir, edge_dir);
        float c = dot(edge_dir, edge_dir);
        float d = dot(capsule_dir, r);
        float e = dot(edge_dir, r);
        
        float denom = a * c - b * b;
        float s = 0.0, t = 0.0;
        
        if (denom != 0.0) {
            s = clamp((b * e - c * d) / denom, 0.0, 1.0);
        }
        t = (b * s + e) / c;
        t = clamp(t, 0.0, 1.0);
        s = clamp((b * t - d) / a, 0.0, 1.0);
        
        vec3 c1 = cap_start + s * capsule_dir;
        vec3 c2 = edge_start + t * edge_dir;
        float d3 = length(c1 - c2);
        
        if (d3 < min_dist) {
            min_dist = d3;
            best_point = c1;
        }
    }
    
    dist = min_dist;
    collision_point = best_point;
    return min_dist <= cap_radius;
}

void main() {
    uint idx = gl_GlobalInvocationID.x;
    if (idx >= num_vertices / 3) return;
    
    vec3 v0 = get_vert(idx * 3 + 0);
    vec3 v1 = get_vert(idx * 3 + 1);
    vec3 v2 = get_vert(idx * 3 + 2);

    v0 = (model_matrix * vec4(v0, 1.0)).xyz;
    v1 = (model_matrix * vec4(v1, 1.0)).xyz;
    v2 = (model_matrix * vec4(v2, 1.0)).xyz;

    float dist;
    vec3 collision_point;
    bool collision = capsule_to_triangle_intersection(
        v0, v1, v2, 
        capsule_start, capsule_end, 
        capsule_radius,
        dist, collision_point
    );

    if (!verbose) {
        if (collision) {
            indexes[0] = 1;
        }
    } else {
        if (collision) {
            indexes[idx] = 1;
        } else {
            indexes[idx] = 0;
        }
    }
}