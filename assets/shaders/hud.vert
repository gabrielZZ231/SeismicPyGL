#version 330 core

layout (location = 0) in vec3 a_position;
layout (location = 1) in vec2 a_uv;

uniform mat4 u_projection;
uniform mat4 u_model;

out vec2 v_uv;

void main() {
    v_uv = a_uv;
    gl_Position = u_projection * u_model * vec4(a_position, 1.0);
}
