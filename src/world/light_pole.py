"""Postes de iluminação pública com metal PBR (metal_plate_02) e queda física angular."""

import math
import random
from OpenGL.GL import (
    glBindTexture, glActiveTexture,
    GL_TEXTURE_2D, GL_TEXTURE0, GL_TEXTURE1, GL_TEXTURE2
)
from ..core.shader import ShaderProgram
from ..core.math_utils import translate, rotate_x, rotate_z, scale
from .shared import (
    get_pbr_set, get_shared_cube_mesh, get_shared_cylinder_mesh
)


class LightPole:
    def __init__(self, x, z, street_direction="x", side=1.0):
        self.initial_x = x
        self.initial_z = z
        self.x = x
        self.z = z
        self.direction = street_direction
        self.height = 3.2
        self.arm_len = 0.75
        if street_direction == "x":
            self.arm_dx = 0.0
            self.arm_dz = -self.arm_len * side
        else:
            self.arm_dx = -self.arm_len * side
            self.arm_dz = 0.0

        self.pbr_set = get_pbr_set("metal_plate_02")
        self.falling = False
        self.fall_progress = 0.0
        self.fall_direction = random.uniform(0.0, 360.0)
        self.fall_speed = random.uniform(1.1, 1.6)
        self.target_tilt = random.uniform(62.0, 74.0)
        self.lamp_lit = True
        self.fallen = False
        self.emitted_impact = False

    def reset(self):
        self.x = self.initial_x
        self.z = self.initial_z
        self.falling = False
        self.fall_progress = 0.0
        self.lamp_lit = True
        self.fallen = False
        self.emitted_impact = False

    def update(self, earthquake, current_time: float, dt: float, particle_system=None):
        dx, dy, dz = earthquake.get_offset(self.x, self.z, current_time)
        amplitude = math.hypot(dx, dy, dz)

        if not self.falling:
            if amplitude > 0.20:
                excess = amplitude - 0.20
                prob = min(0.95, excess * 4.8) * dt * 3.2
                if random.random() < prob:
                    self.falling = True
                    angle = math.atan2(dz, dx) * 180.0 / math.pi
                    self.fall_direction = angle + random.uniform(-35.0, 35.0)
        else:
            if self.fall_progress < 1.0:
                self.fall_progress = min(1.0, self.fall_progress + dt * self.fall_speed)
                self.lamp_lit = random.random() > 0.45
                if self.fall_progress >= 1.0:
                    self.fallen = True
                    self.lamp_lit = False
                    if particle_system and not self.emitted_impact:
                        self.emitted_impact = True
                        rad = math.radians(self.fall_direction)
                        impact_x = self.x + math.cos(rad) * self.height * 0.7
                        impact_z = self.z + math.sin(rad) * self.height * 0.7
                        particle_system.emit((impact_x, 0.15, impact_z), count=25, spread=0.6, base_speed=1.6)

    def draw(self, shader: ShaderProgram, earthquake=None, current_time=0.0):
        cyl_mesh = get_shared_cylinder_mesh()
        cube_mesh = get_shared_cube_mesh()

        dx, dy, dz = earthquake.get_offset(self.x, self.z, current_time) if (earthquake and earthquake.active) else (0.0, 0.0, 0.0)

        base_x = self.x + dx
        base_y = max(0.015, dy)
        base_z = self.z + dz

        m_pivot = translate(base_x, base_y, base_z)

        if self.falling:
            t = self.fall_progress
            fall_angle = self.target_tilt * (t ** 1.6)
            rad = math.radians(self.fall_direction)
            rx = fall_angle * math.sin(rad)
            rz = -fall_angle * math.cos(rad)
            m_pivot = m_pivot @ rotate_x(rx) @ rotate_z(rz)
        elif earthquake and earthquake.active:
            amp = math.hypot(dx, dy, dz)
            sway_ang = amp * 18.0 * math.sin(current_time * 16.0 + self.x * 0.5)
            m_pivot = m_pivot @ rotate_x(sway_ang * 0.6) @ rotate_z(sway_ang)

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

        m_pole = m_pivot @ scale(0.065, self.height, 0.065)
        shader.set_uniform_mat4("u_model", m_pole)
        shader.set_uniform_vec4("u_base_color", (0.85, 0.88, 0.90, 1.0))
        cyl_mesh.draw()

        top_y = self.height
        m_arm = m_pivot @ translate(self.arm_dx * 0.5, top_y, self.arm_dz * 0.5) @ scale(
            abs(self.arm_dx) or 0.065, 0.065, abs(self.arm_dz) or 0.065
        )
        shader.set_uniform_mat4("u_model", m_arm)
        shader.set_uniform_vec4("u_base_color", (0.80, 0.82, 0.85, 1.0))
        cube_mesh.draw()

        m_head = m_pivot @ translate(self.arm_dx, top_y - 0.05, self.arm_dz) @ scale(0.24, 0.12, 0.24)
        shader.set_uniform_mat4("u_model", m_head)
        shader.set_uniform_vec4("u_base_color", (0.75, 0.78, 0.80, 1.0))
        cube_mesh.draw()

        shader.set_uniform_int("u_use_texture", 0)
        shader.set_uniform_int("u_use_pbr", 0)
        bulb_col = (1.0, 0.92, 0.45, 1.0) if self.lamp_lit else (0.12, 0.12, 0.12, 1.0)
        m_bulb = m_pivot @ translate(self.arm_dx, top_y - 0.14, self.arm_dz) @ scale(0.18, 0.06, 0.18)
        shader.set_uniform_mat4("u_model", m_bulb)
        shader.set_uniform_vec4("u_base_color", bulb_col)
        cube_mesh.draw()


LampPost = LightPole
