#version 330 core

layout (location = 0) in vec3 a_position;
layout (location = 1) in vec2 a_uv;
layout (location = 2) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

uniform vec2 u_epicenter;
uniform float u_time;
uniform float u_wave_speed;
uniform float u_amplitude;
uniform float u_frequency;
uniform float u_damping;
uniform float u_spatial_falloff;
uniform int u_active;
uniform float u_crack_intensity;

out vec2 v_uv;
out vec3 v_normal;
out vec3 v_frag_pos;

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
    vec3 pos = a_position;
    vec3 norm = a_normal;

    if (u_active != 0 && u_amplitude > 0.001) {
        float dist = distance(a_position.xz, u_epicenter);
        float arrival = dist / max(u_wave_speed, 0.001);
        float local_t = u_time - arrival;

        if (local_t > 0.0) {
            float phase = 6.2831853 * u_frequency * local_t;
            float envelope = exp(-u_damping * local_t) * exp(-u_spatial_falloff * dist);
            float dy = u_amplitude * sin(phase) * envelope;
            pos.y += dy;

            if (dist > 0.0001) {
                float dphase_ddist = -6.2831853 * u_frequency / u_wave_speed;
                float dy_ddist = u_amplitude * (
                    cos(phase) * dphase_ddist * envelope -
                    sin(phase) * u_spatial_falloff * envelope
                );
                float nx = -dy_ddist * (a_position.x - u_epicenter.x) / dist;
                float nz = -dy_ddist * (a_position.z - u_epicenter.y) / dist;
                norm = normalize(vec3(nx, 1.0, nz));
            }
        }
    }

    if (u_crack_intensity > 0.0) {
        float dist = distance(a_position.xz, u_epicenter);
        float falloff = exp(-u_spatial_falloff * dist);
        float crack_noise = voronoi_edge(a_position.xz * 0.5);
        float crack_mask = smoothstep(0.05, 0.0, crack_noise) * falloff * u_crack_intensity;
        pos.y -= crack_mask * 0.15;
    }

    vec4 world_pos = u_model * vec4(pos, 1.0);
    v_frag_pos = world_pos.xyz;

    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_normal = normalize(normal_matrix * norm);
    v_uv = a_uv;

    gl_Position = u_projection * u_view * world_pos;
}
