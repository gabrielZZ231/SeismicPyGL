#version 330 core

layout (location = 0) in vec3 a_position;
layout (location = 1) in vec2 a_uv;
layout (location = 2) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec2 v_uv;
out vec3 v_normal;
out vec3 v_frag_pos;

void main() {
    vec4 world_pos = u_model * vec4(a_position, 1.0);
    v_frag_pos = world_pos.xyz;

    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_normal = normalize(normal_matrix * a_normal);
    v_uv = a_uv;

    gl_Position = u_projection * u_view * world_pos;
}
