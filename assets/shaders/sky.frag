#version 330 core

in vec3 v_ray_dir;
out vec4 FragColor;

uniform sampler2D u_sky_texture;
uniform float u_time;

const float PI = 3.141592653589793;

void main() {
    vec3 dir = normalize(v_ray_dir);
    // Mapeamento equirretangular (panorama esférico 360 graus)
    float u = atan(dir.z, dir.x) / (2.0 * PI) + 0.5;
    float v = asin(clamp(dir.y, -1.0, 1.0)) / PI + 0.5;

    vec3 sky = texture(u_sky_texture, vec2(u, v)).rgb;

    // Névoa atmosférica suave no horizonte para mesclar perfeitamente com a cena
    float horizon_haze = smoothstep(-0.05, 0.12, dir.y);
    vec3 haze_color = vec3(0.68, 0.76, 0.84);
    sky = mix(haze_color, sky, horizon_haze * 0.45 + 0.55);

    FragColor = vec4(sky, 1.0);
}
