#version 430
layout(local_size_x = 64) in;

layout(std430, binding = 0) buffer ModelMatrices {
    mat4 model[];
};

layout(std430, binding = 1) buffer UpdatedModelTransforms {
    float updatedModelTransforms[];
};

mat4 quatToMat4(vec4 q)
{
    float x = q.x, y = q.y, z = q.z, w = q.w;

    float xx = x * x;
    float yy = y * y;
    float zz = z * z;
    float xy = x * y;
    float xz = x * z;
    float yz = y * z;
    float wx = w * x;
    float wy = w * y;
    float wz = w * z;

    return mat4(
        1.0 - 2.0*(yy + zz),  2.0*(xy - wz),        2.0*(xz + wy),        0.0,
        2.0*(xy + wz),        1.0 - 2.0*(xx + zz),  2.0*(yz - wx),        0.0,
        2.0*(xz - wy),        2.0*(yz + wx),        1.0 - 2.0*(xx + yy),  0.0,
        0.0,                  0.0,                  0.0,                  1.0
    );
}

mat4 makeTranslation(vec3 pos)
{
    return mat4(
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        pos.x, pos.y, pos.z, 1.0
    );
}

mat4 makeScale(vec3 s)
{
    return mat4(
        s.x, 0.0, 0.0, 0.0,
        0.0, s.y, 0.0, 0.0,
        0.0, 0.0, s.z, 0.0,
        0.0, 0.0, 0.0, 1.0
    );
}

mat4 createModelMatrix(vec3 position, vec4 rotation, vec3 scale)
{
    mat4 T = makeTranslation(position);
    mat4 R = quatToMat4(rotation);
    mat4 S = makeScale(scale);
    return T * R * S;   // same order as pyrr
}

void main() {
    uint i = gl_GlobalInvocationID.x * 11;
    if (i >= updatedModelTransforms.length()) {
        return;
    }
    float model_index = updatedModelTransforms[i + 0];
    vec3 position = vec3(updatedModelTransforms[i + 1], updatedModelTransforms[i + 2], updatedModelTransforms[i + 3]);
    vec3 scale = vec3(updatedModelTransforms[i + 4], updatedModelTransforms[i + 5], updatedModelTransforms[i + 6]);
    vec4 rotation = vec4(updatedModelTransforms[i + 7], updatedModelTransforms[i + 8], updatedModelTransforms[i + 9], updatedModelTransforms[i + 10]);
    model[int(model_index)] = createModelMatrix(position, rotation, scale);
}