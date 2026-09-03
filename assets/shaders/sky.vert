#version 330 core

layout (location = 0) in vec3 a_position;

uniform mat4 u_inv_view_proj;

out vec3 v_ray_dir;

void main() {
    vec4 unprojected = u_inv_view_proj * vec4(a_position.xy, 1.0, 1.0);
    v_ray_dir = unprojected.xyz / unprojected.w;
    gl_Position = vec4(a_position.xy, 1.0, 1.0);
}
