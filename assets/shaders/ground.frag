#version 330 core

in vec2 v_uv;
in vec3 v_normal;
in vec3 v_tangent;
in vec3 v_frag_pos;
in vec4 v_light_space_pos;

out vec4 FragColor;

// Texture Units PBR para o Chão
uniform sampler2D u_texture;            // Unit 0: Grama Albedo (sparse_grass)
uniform sampler2D u_normal_map;         // Unit 1: Grama Normal
uniform sampler2D u_roughness_map;      // Unit 2: Grama Roughness
uniform sampler2D u_crack_texture;      // Unit 3: Rachadura Albedo (cracked_concrete_02)
uniform sampler2D u_crack_normal_map;   // Unit 4: Rachadura Normal
uniform sampler2D u_shadow_map;         // Unit 5: Shadow Map

uniform int u_use_texture;
uniform int u_use_pbr;
uniform vec3 u_view_pos;
uniform vec4 u_base_color;
uniform vec3 u_light_direction;
uniform vec3 u_light_color;
uniform vec3 u_ambient_color;

uniform float u_crack_intensity;
uniform vec2 u_epicenter;
uniform float u_spatial_falloff;
uniform vec2 u_contact_points[40];
uniform int u_contact_count;

float shadow_visibility() {
    vec3 projected = v_light_space_pos.xyz / max(v_light_space_pos.w, 0.0001);
    projected = projected * 0.5 + 0.5;
    if (projected.z <= 0.0 || projected.z >= 1.0 || projected.x <= 0.0 || projected.x >= 1.0 || projected.y <= 0.0 || projected.y >= 1.0) return 1.0;
    vec2 texel = 1.0 / vec2(textureSize(u_shadow_map, 0));
    float lit = 0.0;
    for (int y = -1; y <= 1; ++y)
        for (int x = -1; x <= 1; ++x)
            lit += projected.z - 0.001 <= texture(u_shadow_map, projected.xy + vec2(x, y) * texel).r ? 1.0 : 0.0;
    return mix(0.42, 1.0, lit / 9.0);
}

float contact_ao() {
    float result = 1.0;
    for (int i = 0; i < 40; ++i) {
        if (i >= u_contact_count) break;
        float d = distance(v_frag_pos.xz, u_contact_points[i]);
        result = min(result, mix(0.80, 1.0, smoothstep(0.0, 1.15, d)));
    }
    return result;
}

vec2 random2(vec2 p) {
    return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453);
}

float voronoi_edge(vec2 x) {
    vec2 n = floor(x);
    vec2 f = fract(x);
    
    vec2 mg, mr;
    float md = 8.0;
    for (int j = -1; j <= 1; j++) {
        for (int i = -1; i <= 1; i++) {
            vec2 g = vec2(float(i), float(j));
            vec2 o = random2(n + g);
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
            vec2 o = random2(n + g);
            vec2 r = g + o - f;
            if (dot(mr - r, mr - r) > 0.00001) {
                md = min(md, dot(0.5 * (mr + r), normalize(r - mr)));
            }
        }
    }
    return md;
}

void main() {
    vec3 N_geom = normalize(v_normal);
    vec3 N = N_geom;
    float roughness = 0.85;
    // Mapeamento em espaço de mundo: elimina o ladrilhamento da grade.
    vec2 ground_uv = v_frag_pos.xz * 0.08;

    // Normal mapping PBR para o terreno
    if (u_use_pbr != 0) {
        vec3 T = normalize(v_tangent - dot(v_tangent, N_geom) * N_geom);
        vec3 B = cross(N_geom, T);
        mat3 TBN = mat3(T, B, N_geom);

        vec3 n_grass = texture(u_normal_map, ground_uv).rgb * 2.0 - 1.0;
        roughness = texture(u_roughness_map, ground_uv).r;
        N = normalize(TBN * n_grass);
    }

    vec4 tex_color = u_use_texture != 0 ? texture(u_texture, ground_uv) : vec4(1.0);
    vec4 base = tex_color * u_base_color;

    // Fissuras e rachaduras sísmicas usando a textura cracked_concrete_02
    if (u_crack_intensity > 0.0) {
        float dist = distance(v_frag_pos.xz, u_epicenter);
        float falloff = exp(-u_spatial_falloff * dist * 0.70);
        float crack_noise = voronoi_edge(v_frag_pos.xz * 0.45);
        float crack_width = 0.065 * (1.0 + u_crack_intensity * 0.85);
        float crack_mask = smoothstep(crack_width, 0.005, crack_noise) * falloff * u_crack_intensity;
        float soil_mask = smoothstep(crack_width * 2.3, crack_width, crack_noise) * falloff * u_crack_intensity;

        // Amostra a textura de concreto rachado / rocha quebrada dentro da fenda
        vec4 crack_tex = texture(u_crack_texture, v_frag_pos.xz * 0.35);
        vec3 exposed_soil = mix(vec3(0.26, 0.18, 0.10), crack_tex.rgb * 0.65, 0.50);
        vec3 deep_fissure = crack_tex.rgb * 0.18;

        base.rgb = mix(base.rgb, exposed_soil, soil_mask * 0.75);
        base.rgb = mix(base.rgb, deep_fissure, crack_mask);
        roughness = mix(roughness, 0.95, crack_mask);
    }

    vec3 L = normalize(-u_light_direction);
    float diff = max(dot(N, L), 0.0);

    vec3 V = normalize(u_view_pos - v_frag_pos);
    vec3 H = normalize(L + V);
    float spec_power = mix(8.0, 64.0, 1.0 - clamp(roughness, 0.1, 0.95));
    float spec = pow(max(dot(N, H), 0.0), spec_power) * (1.0 - roughness) * 0.25;

    float shadow = shadow_visibility();
    vec3 ambient = u_ambient_color;
    vec3 diffuse = diff * u_light_color * shadow;
    vec3 specular = spec * u_light_color * shadow;

    vec3 lit_color = (ambient + diffuse) * base.rgb * contact_ao() + specular;

    FragColor = vec4(lit_color, base.a);
}
