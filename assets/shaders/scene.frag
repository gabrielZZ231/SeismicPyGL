#version 330 core

in vec2 v_uv;
in vec3 v_normal;
in vec3 v_tangent;
in vec3 v_frag_pos;
in vec4 v_light_space_pos;

out vec4 FragColor;

// Texture Units PBR
uniform sampler2D u_texture;               // Unit 0: Albedo / Diffuse intacto
uniform sampler2D u_normal_map;            // Unit 1: Normal map intacto
uniform sampler2D u_roughness_map;         // Unit 2: Roughness map intacto
uniform sampler2D u_damaged_texture;       // Unit 3: Albedo danificado
uniform sampler2D u_damaged_normal_map;    // Unit 4: Normal map danificado
uniform sampler2D u_damaged_roughness_map; // Unit 5: Roughness map danificado
uniform sampler2D u_shadow_map;            // Unit 6: Shadow depth map

// Modos e parâmetros
uniform int u_use_texture;
uniform int u_use_pbr;
uniform int u_has_damaged_set;
uniform float u_damage_blend;
uniform float u_uv_scale;
uniform vec3 u_view_pos;

uniform vec4 u_base_color;
uniform vec3 u_light_direction;
uniform vec3 u_light_color;
uniform vec3 u_ambient_color;

uniform int u_building_facade;
uniform int u_mountain_stratum;
uniform int u_is_house;
uniform int u_is_street;
uniform int u_is_foliage;
uniform float u_crack_intensity;
uniform vec2 u_epicenter;
uniform float u_spatial_falloff;

vec2 random2_scene(vec2 p) {
    return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453);
}

float voronoi_edge_scene(vec2 x) {
    vec2 n = floor(x);
    vec2 f = fract(x);

    vec2 mg, mr;
    float md = 8.0;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 o = random2_scene(n + g);
            vec2 r = g + o - f;
            float d = dot(r, r);
            if (d < md) {
                md = d;
                mr = r;
                mg = g;
            }
        }
    }

    md = 8.0;
    for (int j = -2; j <= 2; j++) {
        for (int i = -2; i <= 2; i++) {
            vec2 g = mg + vec2(float(i), float(j));
            vec2 o = random2_scene(n + g);
            vec2 r = g + o - f;
            if (dot(mr - r, mr - r) > 0.00001) {
                md = min(md, dot(0.5 * (mr + r), normalize(r - mr)));
            }
        }
    }
    return md;
}

float shadow_visibility() {
    vec3 projected = v_light_space_pos.xyz / max(v_light_space_pos.w, 0.0001);
    projected = projected * 0.5 + 0.5;
    if (projected.z <= 0.0 || projected.z >= 1.0 || projected.x <= 0.0 || projected.x >= 1.0 || projected.y <= 0.0 || projected.y >= 1.0) return 1.0;
    float bias = max(0.0012 * (1.0 - dot(normalize(v_normal), normalize(-u_light_direction))), 0.00035);
    vec2 texel = 1.0 / vec2(textureSize(u_shadow_map, 0));
    float lit = 0.0;
    for (int y = -1; y <= 1; ++y)
        for (int x = -1; x <= 1; ++x)
            lit += projected.z - bias <= texture(u_shadow_map, projected.xy + vec2(x, y) * texel).r ? 1.0 : 0.0;
    return mix(0.38, 1.0, lit / 9.0);
}

void main() {
    vec3 N_geom = normalize(v_normal);
    vec3 N = N_geom;
    float roughness = 0.70;

    vec2 uv_scaled = v_uv * (u_uv_scale > 0.001 ? u_uv_scale : 1.0);
    if (u_is_street != 0) uv_scaled = v_frag_pos.xz / 4.0;

    // 1. Normal Mapping com matriz TBN e amostragem PBR
    if (u_use_pbr != 0) {
        vec3 T = normalize(v_tangent - dot(v_tangent, N_geom) * N_geom);
        vec3 B = cross(N_geom, T);
        mat3 TBN = mat3(T, B, N_geom);

        vec3 n_intact = texture(u_normal_map, uv_scaled).rgb * 2.0 - 1.0;
        float rough_intact = texture(u_roughness_map, uv_scaled).r;

        vec3 n_tangent = n_intact;
        roughness = rough_intact;

        if (u_has_damaged_set != 0 && u_damage_blend > 0.001) {
            vec3 n_damaged = texture(u_damaged_normal_map, uv_scaled).rgb * 2.0 - 1.0;
            float rough_damaged = texture(u_damaged_roughness_map, uv_scaled).r;

            n_tangent = normalize(mix(n_intact, n_damaged, clamp(u_damage_blend, 0.0, 1.0)));
            roughness = mix(rough_intact, rough_damaged, clamp(u_damage_blend, 0.0, 1.0));
        }

        N = normalize(TBN * n_tangent);
    }

    // 2. Albedo PBR com crossfade de dano gradual
    vec4 tex_color = vec4(1.0);
    if (u_use_texture != 0) {
        vec4 intact_albedo = texture(u_texture, uv_scaled);
        if (u_has_damaged_set != 0 && u_damage_blend > 0.001) {
            vec4 damaged_albedo = texture(u_damaged_texture, uv_scaled);
            tex_color = mix(intact_albedo, damaged_albedo, clamp(u_damage_blend, 0.0, 1.0));
        } else {
            tex_color = intact_albedo;
        }
    }
    vec4 base = tex_color * u_base_color;

    // Copa: dois verdes, variação por altura/ruído e acabamento fosco.
    if (u_is_foliage != 0) {
        float height_mix = fract(v_frag_pos.y * 0.43);
        float needle_noise = fract(sin(dot(v_frag_pos.xz, vec2(17.13, 41.71))) * 15731.74);
        float facing = max(dot(N_geom, normalize(-u_light_direction)), 0.0);
        vec3 shadow_green = vec3(0.045, 0.16, 0.055);
        vec3 sun_green = vec3(0.16, 0.38, 0.10);
        base.rgb = mix(shadow_green, sun_green, clamp(0.25 + height_mix * 0.35 + needle_noise * 0.22 + facing * 0.18, 0.0, 1.0));
        roughness = 0.90;
    }

    // Voronoi é exclusivo das rachaduras sísmicas; em repouso não há células.
    if (u_is_street != 0 && u_crack_intensity > 0.05) {
        float dist = distance(v_frag_pos.xz, u_epicenter);
        float seismic = clamp(u_crack_intensity, 0.0, 1.0);
        float falloff = exp(-u_spatial_falloff * dist * 0.70);
        float crack_noise = voronoi_edge_scene(v_frag_pos.xz * 0.45);
        float crack_width = 0.065 * (1.0 + seismic * 0.90);
        float crack_mask = smoothstep(crack_width, 0.002, crack_noise) * falloff;
        float rubble_mask = smoothstep(crack_width * 2.2, crack_width, crack_noise) * falloff * seismic;

        vec3 rubble_color = vec3(0.38, 0.36, 0.33);
        vec3 dark_chasm = vec3(0.025, 0.02, 0.015);
        base.rgb = mix(base.rgb, rubble_color, rubble_mask * 0.60);
        base.rgb = mix(base.rgb, dark_chasm, crack_mask);
        roughness = mix(roughness, 0.95, crack_mask);
    }

    // 4. Montanha rochosa com topo nevado
    if (u_mountain_stratum != 0 && u_building_facade == 0) {
        float y = v_frag_pos.y;
        float noise = 0.5 * sin(v_frag_pos.x * 3.7 + v_frag_pos.z * 2.9);
        y += noise;

        float w_snow = smoothstep(16.0, 18.5, y);
        vec3 snow_color = vec3(0.95, 0.97, 1.0);
        base.rgb = mix(base.rgb, snow_color, w_snow);
        roughness = mix(roughness, 0.35, w_snow);
    }

    // 5. Iluminacao Blinn-Phong com Especular modulado pela Roughness PBR
    vec3 L = normalize(-u_light_direction);
    float diff = max(dot(N, L), 0.0);

    vec3 V = normalize(u_view_pos - v_frag_pos);
    vec3 H = normalize(L + V);
    float spec_power = mix(8.0, 128.0, 1.0 - clamp(roughness, 0.05, 0.95));
    float spec = pow(max(dot(N, H), 0.0), spec_power) * (1.0 - roughness * 0.75);

    float shadow = shadow_visibility();
    vec3 ambient = u_ambient_color;
    vec3 diffuse = diff * u_light_color * shadow;
    vec3 specular = spec * u_light_color * shadow * 0.40;

    vec3 lit_color = (ambient + diffuse) * base.rgb + specular;

    // AO analítico de contato na base
    float contact_ao = mix(0.78, 1.0, smoothstep(0.0, 0.70, v_frag_pos.y));
    lit_color *= contact_ao;

    // Fachada de predios (janelas e portas)
    if (u_building_facade != 0 && abs(N_geom.y) < 0.45) {
        float horizontal = abs(N_geom.x) > abs(N_geom.z) ? v_frag_pos.z : v_frag_pos.x;
        float floor_index = floor(v_frag_pos.y * 0.72);
        float column = fract(horizontal * 0.82 + floor_index * 0.13);
        float row = fract(v_frag_pos.y * 0.72);
        float inside_window = step(0.16, column) * step(column, 0.84)
                            * step(0.18, row) * step(row, 0.82);
        vec3 glass = vec3(0.035, 0.10, 0.16) * (0.45 + 0.55 * diff)
                   + vec3(0.07, 0.12, 0.16) * (0.5 + 0.5 * sin(floor_index * 7.0));
        lit_color = mix(lit_color, glass, inside_window * (1.0 - u_damage_blend * 0.8));

        float door = float(u_is_house != 0) * step(v_frag_pos.y, 1.15)
                   * step(0.34, column) * step(column, 0.66);
        lit_color = mix(lit_color, vec3(0.10, 0.055, 0.028) * (0.45 + 0.55 * diff), door);
    }

    FragColor = vec4(lit_color, base.a);
}
