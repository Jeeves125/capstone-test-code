#version 430
layout(local_size_x = 16, local_size_y = 16) in;
layout(rgba32f, binding = 0) uniform image2D img;
// uniform vec4 fill_color;

float bresenhamLine(ivec2 pos, ivec2 p0, ivec2 p1) {
    ivec2 delta = abs(p1 - p0);
    ivec2 step = ivec2(p0.x < p1.x ? 1 : -1, p0.y < p1.y ? 1 : -1);
    int error = delta.x - delta.y;
    
    ivec2 current = p0;
    
    // Maximum iterations to prevent infinite loops
    int maxSteps = delta.x + delta.y + 1;
    
    for(int i = 0; i < maxSteps; i++) {
        // Check if current position matches the target pixel
        if(current == pos) {
            return 1.0;
        }
        
        // Check if we've reached the end point
        if(current == p1) {
            break;
        }
        
        int e2 = 2 * error;
        
        if(e2 > -delta.y) {
            error -= delta.y;
            current.x += step.x;
        }
        
        if(e2 < delta.x) {
            error += delta.x;
            current.y += step.y;
        }
    }
    
    return 0.0;
}

// Alternative version that returns distance to line (useful for anti-aliasing)
float bresenhamLineDistance(vec2 pos, vec2 p0, vec2 p1) {
    vec2 line = p1 - p0;
    vec2 toPoint = pos - p0;
    
    float lineLength = length(line);
    if(lineLength < 0.001) return length(toPoint);
    
    vec2 lineDir = line / lineLength;
    float projection = dot(toPoint, lineDir);
    
    // Clamp to line segment
    projection = clamp(projection, 0.0, lineLength);
    
    vec2 closestPoint = p0 + lineDir * projection;
    return distance(pos, closestPoint);
}



uniform vec2 mouse_pos;
uniform float dist_effect;
uniform float time;

void main() {
  ivec2 coord = ivec2(gl_GlobalInvocationID.xy);
  ivec2 size = imageSize(img);
  if (coord.x >= size.x || coord.y >= size.y) return;
  vec2 start = vec2(size.x / 2, size.y / 2) + vec2(cos(time), sin(time)) * 100;
  vec2 end = mouse_pos;

  float dist = max(0, 1 - (bresenhamLineDistance(coord, start, end) / dist_effect));

  imageStore(img, coord, vec4(dist, dist, dist, 1.0));
}