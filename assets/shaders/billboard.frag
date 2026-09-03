#version 330 core

in vec2 v_uv;
in float v_particle_alpha;
in vec3 v_particle_color;
out vec4 FragColor;

uniform sampler2D u_texture;

void main() {
    vec4 tex_color = texture(u_texture, v_uv);
    FragColor = vec4(v_particle_color * tex_color.rgb, tex_color.a * v_particle_alpha);
}
