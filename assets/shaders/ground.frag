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

uniform float u_crack_intensity;
uniform vec2 u_epicenter;
uniform float u_spatial_falloff;

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
    vec3 N = normalize(v_normal);
    vec3 L = normalize(-u_light_direction);
    float diff = max(dot(N, L), 0.0);

    vec3 ambient = u_ambient_color;
    vec3 diffuse = diff * u_light_color;

    vec4 tex_color = u_use_texture != 0 ? texture(u_texture, v_uv) : vec4(1.0);
    vec4 base = tex_color * u_base_color;

    if (u_crack_intensity > 0.0) {
        float dist = distance(v_frag_pos.xz, u_epicenter);
        float falloff = exp(-u_spatial_falloff * dist);
        float crack_noise = voronoi_edge(v_frag_pos.xz * 0.5);
        float crack_mask = smoothstep(0.05, 0.0, crack_noise) * falloff * u_crack_intensity;
        vec3 dark_crack = vec3(0.05, 0.04, 0.03);
        base.rgb = mix(base.rgb, dark_crack, crack_mask);
    }

    FragColor = vec4((ambient + diffuse) * base.rgb, base.a);
}
