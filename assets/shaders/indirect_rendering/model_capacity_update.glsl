#version 430
layout(local_size_x = 64) in;

/*
    The buffers that are used for rendering, that will have data 'added' to them, 
    for the new models that were added in the current frame.
*/

layout(std430, binding = 0) buffer IndirectCommandsBuffer {
    uint current_commands[];
};

layout(std430, binding = 1) buffer TextureUVData {
    vec4 current_uv_data[];
};

layout(std430, binding = 2) buffer VertexBuffer {
    float current_vertices[];
};

layout(std430, binding = 3) buffer TextureCoordsBuffer {
    float current_texCoords[];
};


/*
    Added data that will be, like the name suggests, added to the buffers used for rendering.
*/
layout(std430, binding = 4) buffer AddedIndirectCommandsBuffer {
    uint added_commands[];
};

layout(std430, binding = 5) buffer AddedTextureUVData {
    vec4 added_uv_data[];
};

layout(std430, binding = 6) buffer AddedVertexBuffer {
    float added_vertices[];
};

layout(std430, binding = 7) buffer AddedTextureCoordsBuffer {
    float added_texCoords[];
};

// Information about what is being added, and how much of each.
// uniform int newModelCount;
// uniform int modelDelta;
// uniform int newVertexCount;
// uniform int vertexDelta;

void main() {
  
}