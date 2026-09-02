#version 330 core

in vec2 v_uv;
out vec4 FragColor;

uniform sampler2D u_texture;
uniform float u_particle_alpha;
uniform vec3 u_particle_color;

void main() {
    vec4 tex_color = texture(u_texture, v_uv);
    FragColor = vec4(u_particle_color * tex_color.rgb, tex_color.a * u_particle_alpha);
}
