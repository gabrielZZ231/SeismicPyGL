#version 330 core

in vec2 v_uv;
out vec4 FragColor;

uniform sampler2D u_texture;
uniform vec4 u_color;

void main() {
    vec4 tex = texture(u_texture, v_uv);
    FragColor = tex * u_color;
}
