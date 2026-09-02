#version 330 core

in vec2 v_uv;
in vec3 v_normal;
in vec3 v_frag_pos;

out vec4 FragColor;

uniform sampler2D u_texture;
uniform int u_use_texture;
uniform vec4 u_base_color;
uniform vec3 u_light_direction;
uniform vec3 u_light_color;
uniform vec3 u_ambient_color;

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(-u_light_direction);
    float diff = max(dot(N, L), 0.0);

    vec3 ambient = u_ambient_color;
    vec3 diffuse = diff * u_light_color;

    vec4 tex_color = u_use_texture != 0 ? texture(u_texture, v_uv) : vec4(1.0);
    vec4 base = tex_color * u_base_color;
    FragColor = vec4((ambient + diffuse) * base.rgb, base.a);
}
