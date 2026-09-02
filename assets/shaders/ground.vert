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

out vec2 v_uv;
out vec3 v_normal;
out vec3 v_frag_pos;

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

            // Derivada analítica para cálculo correto da normal
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

    vec4 world_pos = u_model * vec4(pos, 1.0);
    v_frag_pos = world_pos.xyz;

    mat3 normal_matrix = transpose(inverse(mat3(u_model)));
    v_normal = normalize(normal_matrix * norm);
    v_uv = a_uv;

    gl_Position = u_projection * u_view * world_pos;
}
