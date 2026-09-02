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
uniform int u_building_facade;
uniform int u_mountain_stratum;

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(-u_light_direction);
    float diff = max(dot(N, L), 0.0);

    vec3 ambient = u_ambient_color;
    vec3 diffuse = diff * u_light_color;

    vec4 tex_color = u_use_texture != 0 ? texture(u_texture, v_uv) : vec4(1.0);
    vec4 base = tex_color * u_base_color;

    if (u_mountain_stratum != 0 && u_building_facade == 0) {
        float y = v_frag_pos.y;
        float noise = 0.5 * sin(v_frag_pos.x * 3.7 + v_frag_pos.z * 2.9);
        y += noise;
        
        vec3 color_low = vec3(0.52, 0.45, 0.38);
        vec3 color_mid = vec3(0.58, 0.55, 0.50);
        vec3 color_high = vec3(0.70, 0.68, 0.65);
        vec3 color_snow = vec3(0.92, 0.94, 0.96);

        float w1 = smoothstep(4.0, 6.0, y);
        float w2 = smoothstep(11.0, 13.0, y);
        float w3 = smoothstep(17.0, 19.0, y);

        vec3 rock_color = mix(color_low, color_mid, w1);
        rock_color = mix(rock_color, color_high, w2);
        rock_color = mix(rock_color, color_snow, w3);

        base.rgb *= rock_color;
    }

    vec3 lit_color = (ambient + diffuse) * base.rgb;

    if (u_building_facade != 0 && abs(N.y) < 0.45) {
        float horizontal = abs(N.x) > abs(N.z) ? v_frag_pos.z : v_frag_pos.x;
        float floor_index = floor(v_frag_pos.y * 0.72);
        float column = fract(horizontal * 0.82 + floor_index * 0.13);
        float row = fract(v_frag_pos.y * 0.72);
        float inside_window = step(0.16, column) * step(column, 0.84)
                            * step(0.18, row) * step(row, 0.82);
        vec3 concrete = lit_color * vec3(0.92, 0.94, 0.97);
        vec3 glass = vec3(0.035, 0.10, 0.16) * (0.45 + 0.55 * diff)
                   + vec3(0.07, 0.12, 0.16) * (0.5 + 0.5 * sin(floor_index * 7.0));
        lit_color = mix(concrete, glass, inside_window);
    }

    FragColor = vec4(lit_color, base.a);
}
