"""Prédios e Casas com modelo de colapso, fachadas residenciais e blocos de destroço."""

import math
import random
import numpy as np
from OpenGL.GL import (
    glBindTexture, glActiveTexture,
    GL_TEXTURE_2D, GL_TEXTURE0, GL_TEXTURE1, GL_TEXTURE2,
    GL_TEXTURE3, GL_TEXTURE4, GL_TEXTURE5
)
from ..core.shader import ShaderProgram
from ..core.math_utils import translate, rotate_x, rotate_y, rotate_z, scale
from .shared import (
    get_pbr_set, get_shared_cube_mesh, get_shared_gable_mesh
)


class Building:
    RESISTANCE_RANGE = (2.2, 5.5)
    COLLAPSE_DURATION = 2.0
    DAMAGE_MULTIPLIER = 3.2

    def __init__(self, x, z, width, depth, height, slices=6, is_house=False):
        self.initial_x = x
        self.initial_z = z
        self.x = x
        self.z = z
        self.width = width
        self.depth = depth
        self.height = height
        self.slices = slices
        self.is_house = is_house

        if self.is_house:
            self.height = min(max(self.height, 2.5), 4.0)
            self.intact_set = get_pbr_set("red_brick")
            self.color = (1.0, 0.96, 0.92, 1.0)
        else:
            self.intact_set = get_pbr_set("damaged_plaster")
            self.color = (0.95, 0.95, 0.97, 1.0)

        self.damaged_set = get_pbr_set("broken_brick_wall")
        self.collapse_set = get_pbr_set("cracked_concrete_02")
        self.rubble_color = (0.45, 0.42, 0.40, 1.0)

        self.resistance = random.uniform(*self.RESISTANCE_RANGE)
        self.damage = 0.0
        self.collapsing = False
        self.collapse_progress = 0.0
        self.y_collapse_offset = 0.0
        self.lean_angle_z = random.uniform(-35.0, 35.0)
        self.lean_angle_x = random.uniform(-25.0, 25.0)
        self.base_rotation = random.uniform(-3.0, 3.0)
        self.emitted_dust = False
        self.debris = []
        self.spawned_debris = False
        self.shake_offset = (0.0, 0.0, 0.0)

    def reset(self):
        self.damage = 0.0
        self.collapsing = False
        self.collapse_progress = 0.0
        self.y_collapse_offset = 0.0
        self.emitted_dust = False
        self.debris.clear()
        self.spawned_debris = False

    def _spawn_debris(self):
        for _ in range(random.randint(60, 90)):
            if random.random() < 0.25:
                s = random.uniform(0.5, 1.0)
                size = (s, random.uniform(0.15, 0.35), s)
            else:
                s = random.uniform(0.12, 0.32)
                size = (s, s, s)

            self.debris.append(BuildingDebris(
                x=self.x + random.uniform(-self.width * 0.45, self.width * 0.45),
                y=random.uniform(0.2, self.height * 0.85),
                z=self.z + random.uniform(-self.depth * 0.45, self.depth * 0.45),
                size=size,
                pbr_set=self.collapse_set
            ))

    def update(self, earthquake, current_time: float, dt: float, particle_system=None):
        self.shake_offset = earthquake.get_offset(self.x, self.z, current_time)
        dx, dy, dz = self.shake_offset
        amplitude = math.hypot(dx, dy, dz)

        if not self.collapsing:
            if amplitude > 0.15:
                self.damage += amplitude * dt * self.DAMAGE_MULTIPLIER

            if self.damage >= self.resistance:
                self.collapsing = True
                self.damage = self.resistance
        else:
            self.collapse_progress = min(
                1.0,
                self.collapse_progress + dt / self.COLLAPSE_DURATION
            )
            if self.collapse_progress > 0.80:
                self.y_collapse_offset = (self.collapse_progress - 0.80) / 0.20 * 0.60

            if not self.spawned_debris and self.collapse_progress > 0.12:
                self._spawn_debris()
                self.spawned_debris = True

            if particle_system and not self.emitted_dust:
                particle_system.emit(
                    (self.x, 1.0, self.z),
                    count=300,
                    spread=max(self.width, self.depth) * 1.5,
                    base_speed=2.5,
                )
                self.emitted_dust = True

            if particle_system and self.collapse_progress < 0.90:
                particle_system.emit(
                    (self.x, self.height * (1.0 - self.collapse_progress) * 0.5, self.z),
                    count=25,
                    spread=max(self.width, self.depth) * 1.1,
                    base_speed=1.5,
                )

        for debris in self.debris:
            debris.update(dt, self.collapse_progress)

    def draw(self, shader: ShaderProgram, earthquake, current_time: float):
        cube_mesh = get_shared_cube_mesh()
        shader.set_uniform_int("u_building_facade", 1)
        shader.set_uniform_int("u_is_house", 1 if self.is_house else 0)
        shader.set_uniform_int("u_is_street", 0)

        damage_ratio = min(1.0, self.damage / max(0.001, self.resistance)) if not self.collapsing else 1.0
        shader.set_uniform_float("u_damage_blend", damage_ratio)
        shader.set_uniform_int("u_has_damaged_set", 1)
        shader.set_uniform_int("u_use_pbr", 1)
        shader.set_uniform_int("u_use_texture", 1)
        shader.set_uniform_float("u_uv_scale", 1.0)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.intact_set["albedo"])
        shader.set_uniform_int("u_texture", 0)

        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.intact_set["normal"])
        shader.set_uniform_int("u_normal_map", 1)

        glActiveTexture(GL_TEXTURE2)
        glBindTexture(GL_TEXTURE_2D, self.intact_set["roughness"])
        shader.set_uniform_int("u_roughness_map", 2)

        curr_damaged_set = self.collapse_set if self.collapsing else self.damaged_set
        glActiveTexture(GL_TEXTURE3)
        glBindTexture(GL_TEXTURE_2D, curr_damaged_set["albedo"])
        shader.set_uniform_int("u_damaged_texture", 3)

        glActiveTexture(GL_TEXTURE4)
        glBindTexture(GL_TEXTURE_2D, curr_damaged_set["normal"])
        shader.set_uniform_int("u_damaged_normal_map", 4)

        glActiveTexture(GL_TEXTURE5)
        glBindTexture(GL_TEXTURE_2D, curr_damaged_set["roughness"])
        shader.set_uniform_int("u_damaged_roughness_map", 5)

        glActiveTexture(GL_TEXTURE0)

        height_factor = max(0.35, 1.0 - self.collapse_progress * 0.65)
        effective_height = self.height * height_factor

        dx, _, dz = self.shake_offset
        sway_scale = 1.0 - self.collapse_progress

        slice_height = effective_height / self.slices
        base_lean_z = self.lean_angle_z * self.collapse_progress
        base_lean_x = self.lean_angle_x * self.collapse_progress

        for i in range(self.slices):
            t = (i + 0.5) / self.slices
            piece_fall = max(0.0, min(1.0, (self.collapse_progress - (1.0 - t) * 0.32) / 0.68))
            y_base = i * slice_height * (1.0 - piece_fall * 0.72) - self.y_collapse_offset
            sway = t * 2.2 * sway_scale

            dx_out = math.sin(math.radians(self.lean_angle_z)) * piece_fall * self.width
            dz_out = math.sin(math.radians(self.lean_angle_x)) * piece_fall * self.depth

            m_trans = translate(self.x + dx * sway + dx_out, y_base, self.z + dz * sway + dz_out)
            m_rot = rotate_y(self.base_rotation) @ rotate_z(base_lean_z * t * piece_fall) @ rotate_x(base_lean_x * t * piece_fall)
            m_scale = scale(self.width, slice_height, self.depth)

            model = m_trans @ m_rot @ m_scale

            shader.set_uniform_mat4("u_model", model)
            shader.set_uniform_vec4("u_base_color", self.color)
            cube_mesh.draw()

            if self.is_house and not self.collapsing and i == self.slices - 1:
                gable_mesh = get_shared_gable_mesh()
                roof_y = y_base + slice_height
                m_roof_trans = translate(self.x + dx * sway, roof_y, self.z + dz * sway)
                roof_rot = self.base_rotation + (90.0 if self.width > self.depth else 0.0)
                roof_dims = (self.depth, self.width) if self.width > self.depth else (self.width, self.depth)
                m_roof_scale = scale(roof_dims[0] * 1.12, self.height * 0.30, roof_dims[1] * 1.12)
                m_roof_rot = rotate_y(roof_rot)
                model_roof = m_roof_trans @ m_roof_rot @ m_roof_scale

                shader.set_uniform_int("u_building_facade", 0)
                shader.set_uniform_mat4("u_model", model_roof)
                shader.set_uniform_vec4("u_base_color", (0.65, 0.30, 0.22, 1.0))
                gable_mesh.draw()

                chimney = translate(self.x, roof_y + self.height * 0.30, self.z) @ rotate_y(self.base_rotation) \
                    @ scale(self.width * 0.08, 0.40, self.depth * 0.08)
                shader.set_uniform_mat4("u_model", chimney)
                shader.set_uniform_vec4("u_base_color", (0.24, 0.15, 0.12, 1.0))
                cube_mesh.draw()

        shader.set_uniform_int("u_building_facade", 0)
        for debris in self.debris:
            debris.draw(shader)


def create_house(x, z):
    w = random.uniform(1.8, 2.8)
    d = random.uniform(1.8, 2.8)
    h = random.uniform(2.5, 4.0)
    return Building(x, z, w, d, h, slices=3, is_house=True)


class BuildingDebris:
    GRAVITY = -13.0

    def __init__(self, x, y, z, size=(0.3, 0.3, 0.3), pbr_set=None):
        self.x = x
        self.y = y
        self.z = z
        self.size = size
        self.pbr_set = pbr_set or get_pbr_set("cracked_concrete_02")

        speed = random.uniform(1.2, 4.0)
        angle = random.uniform(0, math.tau)
        self.vx = math.cos(angle) * speed
        self.vz = math.sin(angle) * speed
        self.vy = random.uniform(1.0, 4.0)

        self.rotation_z = random.uniform(0, 360)
        self.rotation_x = random.uniform(0, 360)
        self.spin_z = random.uniform(-140, 140)
        self.spin_x = random.uniform(-140, 140)
        self.released = False

    def update(self, dt: float, parent_progress: float):
        if not self.released:
            if parent_progress > 0.15:
                self.released = True
            return

        self.vy += self.GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        self.rotation_z += self.spin_z * dt
        self.rotation_x += self.spin_x * dt

        ground_y = self.size[1] * 0.5
        if self.y < ground_y:
            self.y = ground_y
            self.vy = -self.vy * 0.28
            self.vx *= 0.72
            self.vz *= 0.72
            self.spin_x *= 0.75
            self.spin_z *= 0.75

    def draw(self, shader: ShaderProgram):
        if not self.released:
            return

        shader.set_uniform_int("u_use_texture", 1)
        shader.set_uniform_int("u_use_pbr", 1)
        shader.set_uniform_int("u_has_damaged_set", 0)
        shader.set_uniform_float("u_damage_blend", 0.0)
        shader.set_uniform_float("u_uv_scale", 1.0)

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

        model = (translate(self.x, self.y, self.z) @ rotate_z(self.rotation_z)
                 @ rotate_x(self.rotation_x) @ scale(*self.size))
        shader.set_uniform_mat4("u_model", model)
        shader.set_uniform_vec4("u_base_color", (0.85, 0.85, 0.85, 1.0))
        get_shared_cube_mesh().draw()
