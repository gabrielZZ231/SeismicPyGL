"""Montanha pré-computada em VBO com PBR rocky_terrain_02, topo nevado e RockDebris."""

import math
import random
import numpy as np
from OpenGL.GL import (
    glBindTexture, glActiveTexture,
    GL_TEXTURE_2D, GL_TEXTURE0, GL_TEXTURE1, GL_TEXTURE2
)
from ..core.mesh import Mesh
from ..core.shader import ShaderProgram
from ..core.math_utils import translate, scale, perlin2d
from ..core.obj_loader import compute_tangents
from .shared import get_pbr_set, get_shared_cube_mesh


class RockDebris:
    GRAVITY = -11.0

    def __init__(self, x, y, z, vx, vy, vz, size=0.45, color=(0.48, 0.44, 0.40, 1.0), lifetime=6.0):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.size = size
        self.color = color
        self.lifetime = lifetime
        self.age = 0.0

    @property
    def alive(self) -> bool:
        return self.age < self.lifetime

    def update(self, dt: float):
        self.vy += self.GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.age += dt

        if self.y < self.size * 0.5:
            self.y = self.size * 0.5
            self.vy = -self.vy * 0.35
            self.vx *= 0.82
            self.vz *= 0.82

    def draw(self, shader: ShaderProgram):
        cube_mesh = get_shared_cube_mesh()
        shader.set_uniform_int("u_use_texture", 0)
        shader.set_uniform_int("u_use_pbr", 0)
        model = translate(self.x, self.y, self.z) @ scale(self.size, self.size, self.size)
        shader.set_uniform_mat4("u_model", model)
        shader.set_uniform_vec4("u_base_color", self.color)
        cube_mesh.draw()


class Mountain:
    def __init__(self, x=34.0, z=34.0, base_radius=14.0, height=26.0, snow_start=0.62, bands=8, slices=28):
        self.x = x
        self.z = z
        self.base_radius = base_radius
        self.height = height
        self.snow_start = snow_start
        self.bands = bands
        self.pbr_set = get_pbr_set("rocky_terrain_02")

        self.shake_threshold = 0.22
        self.spawn_rate = 9.0
        self.debris = []

        verts = []
        angle_step = 2.0 * math.pi / slices

        for b in range(bands):
            t0 = b / bands
            t1 = (b + 1) / bands
            r0 = self.base_radius * ((1.0 - t0) ** 1.25)
            r1 = self.base_radius * ((1.0 - t1) ** 1.25)
            y0 = t0 * self.height
            y1 = t1 * self.height

            for s in range(slices):
                a0 = s * angle_step
                a1 = (s + 1) * angle_step

                noise_scale = 2.5
                noise_amount = 0.25

                n00 = perlin2d(math.cos(a0) * noise_scale, math.sin(a0) * noise_scale + b * 1.7)
                n10 = perlin2d(math.cos(a1) * noise_scale, math.sin(a1) * noise_scale + b * 1.7)
                n01 = perlin2d(math.cos(a0) * noise_scale, math.sin(a0) * noise_scale + (b + 1) * 1.7)
                n11 = perlin2d(math.cos(a1) * noise_scale, math.sin(a1) * noise_scale + (b + 1) * 1.7)

                r0_perturbed_a0 = r0 * (1.0 + n00 * noise_amount)
                r0_perturbed_a1 = r0 * (1.0 + n10 * noise_amount)
                r1_perturbed_a0 = r1 * (1.0 + n01 * noise_amount)
                r1_perturbed_a1 = r1 * (1.0 + n11 * noise_amount)

                c0, s0 = math.cos(a0), math.sin(a0)
                c1, s1 = math.cos(a1), math.sin(a1)

                p00 = [c0 * r0_perturbed_a0, y0, s0 * r0_perturbed_a0]
                p10 = [c1 * r0_perturbed_a1, y0, s1 * r0_perturbed_a1]
                p11 = [c1 * r1_perturbed_a1, y1, s1 * r1_perturbed_a1]
                p01 = [c0 * r1_perturbed_a0, y1, s0 * r1_perturbed_a0]

                n0 = [c0, 0.35, s0]
                n1 = [c1, 0.35, s1]

                verts.extend([
                    p00[0], p00[1], p00[2],  s / slices * 4.0, t0 * 4.0,  n0[0], n0[1], n0[2],
                    p10[0], p10[1], p10[2],  (s + 1) / slices * 4.0, t0 * 4.0,  n1[0], n1[1], n1[2],
                    p11[0], p11[1], p11[2],  (s + 1) / slices * 4.0, t1 * 4.0,  n1[0], n1[1], n1[2],

                    p00[0], p00[1], p00[2],  s / slices * 4.0, t0 * 4.0,  n0[0], n0[1], n0[2],
                    p11[0], p11[1], p11[2],  (s + 1) / slices * 4.0, t1 * 4.0,  n1[0], n1[1], n1[2],
                    p01[0], p01[1], p01[2],  s / slices * 4.0, t1 * 4.0,  n0[0], n0[1], n0[2],
                ])

        v_arr = np.array(verts, dtype=np.float32)
        tan_data, tan_count, stride = compute_tangents(v_arr)
        self.mesh = Mesh(tan_data, tan_count, stride=stride)

    def update(self, earthquake, current_time: float, dt: float):
        dx, dy, dz = earthquake.get_offset(self.x, self.z, current_time)
        amplitude = math.hypot(dx, dy, dz)

        if amplitude > self.shake_threshold:
            excess = amplitude - self.shake_threshold
            prob = min(0.95, excess * self.spawn_rate) * dt * 10.0
            if random.random() < prob:
                self._spawn_rock()

        for rock in self.debris:
            rock.update(dt)
        self.debris = [r for r in self.debris if r.alive]

    def _spawn_rock(self):
        t = random.uniform(0.25, 0.92)
        radius = self.base_radius * ((1.0 - t) ** 1.25)
        angle = random.uniform(0, 2 * math.pi)

        rx = self.x + math.cos(angle) * radius
        rz = self.z + math.sin(angle) * radius
        ry = t * self.height

        outward_speed = random.uniform(1.2, 3.5)
        vx = math.cos(angle) * outward_speed
        vz = math.sin(angle) * outward_speed
        vy = random.uniform(-0.5, 0.8)

        color = (0.95, 0.96, 0.98, 1.0) if t >= self.snow_start else (0.42, 0.38, 0.34, 1.0)
        self.debris.append(RockDebris(rx, ry, rz, vx, vy, vz, size=random.uniform(0.35, 0.75), color=color))

    def draw(self, shader: ShaderProgram):
        shader.set_uniform_int("u_use_texture", 1)
        shader.set_uniform_int("u_use_pbr", 1)
        shader.set_uniform_int("u_has_damaged_set", 0)
        shader.set_uniform_float("u_damage_blend", 0.0)
        shader.set_uniform_float("u_uv_scale", 4.0)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.pbr_set["albedo"])
        shader.set_uniform_int("u_texture", 0)

        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.pbr_set["normal"])
        shader.set_uniform_int("u_normal_map", 1)

        glActiveTexture(GL_TEXTURE2)
        glBindTexture(GL_TEXTURE_2D, self.pbr_set["roughness"])
        shader.set_uniform_int("u_roughness_map", 2)

        glActiveTexture(GL_TEXTURE0)

        model = translate(self.x, 0.0, self.z)
        shader.set_uniform_mat4("u_model", model)
        shader.set_uniform_vec4("u_base_color", (0.92, 0.90, 0.88, 1.0))
        self.mesh.draw()

        for rock in self.debris:
            rock.draw(shader)

    def cleanup(self):
        if self.mesh:
            self.mesh.cleanup()
            self.mesh = None
