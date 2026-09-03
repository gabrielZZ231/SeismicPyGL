#version 330 core

layout (location = 0) in vec3 a_position;
layout (location = 1) in vec2 a_uv;
layout (location = 2) in vec3 a_normal;
layout (location = 3) in vec3 a_instance_position;
layout (location = 4) in float a_instance_size;
layout (location = 5) in float a_instance_alpha;
layout (location = 6) in vec3 a_instance_color;

uniform mat4 u_view;
uniform mat4 u_projection;
uniform vec3 u_camera_right;
uniform vec3 u_camera_up;

out vec2 v_uv;
out float v_particle_alpha;
out vec3 v_particle_color;

void main() {
    v_uv = a_uv;
    v_particle_alpha = a_instance_alpha;
    v_particle_color = a_instance_color;
    vec3 world_position = a_instance_position
        + u_camera_right * (a_position.x * a_instance_size)
        + u_camera_up * (a_position.y * a_instance_size);
    gl_Position = u_projection * u_view * vec4(world_position, 1.0);
}
