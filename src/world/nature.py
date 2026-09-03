"""Árvores com casca PBR (bark_brown_02), copa bi-tonal e terra sob raízes (dry_river_pebbles)."""

import math
import random
from OpenGL.GL import (
    glBindTexture, glActiveTexture,
    GL_TEXTURE_2D, GL_TEXTURE0, GL_TEXTURE1, GL_TEXTURE2
)
from ..core.shader import ShaderProgram
from ..core.math_utils import translate, rotate_x, rotate_z, scale
from .shared import (
    get_pbr_set, get_shared_cube_mesh, get_shared_cone_mesh, get_shared_cylinder_mesh
)


class Tree:
    def __init__(self, x, z, trunk_height=1.6, trunk_radius=0.18, foliage_layers=3, foliage_height=2.8, foliage_radius=1.1):
        self.x = x
        self.z = z
        self.trunk_height = trunk_height
        self.trunk_radius = trunk_radius
        self.foliage_layers = foliage_layers
        self.foliage_height = foliage_height
        self.foliage_radius = foliage_radius
        self.total_height = trunk_height + foliage_height

        self.falling = False
        self.fall_progress = 0.0
        self.fall_direction = 0.0
        self.fall_speed = 1.0 / 1.5
        self.shake_offset = (0.0, 0.0, 0.0)
        self.bark_set = get_pbr_set("bark_brown_02")

    def reset(self):
        self.falling = False
        self.fall_progress = 0.0

    def update(self, earthquake, current_time, dt):
        if not self.falling:
            self.shake_offset = earthquake.get_offset(self.x, self.z, current_time)
            dx, dy, dz = self.shake_offset
            amplitude = math.hypot(dx, dy, dz)
            if amplitude > 0.35:
                prob = min(0.8, (amplitude - 0.35) * 4.0) * dt * 3.0
                if random.random() < prob:
                    self.falling = True
                    self.fall_direction = random.uniform(0, 360)

        if self.falling and self.fall_progress < 1.0:
            self.fall_progress = min(1.0, self.fall_progress + self.fall_speed * dt)

    def draw(self, shader: ShaderProgram, earthquake, current_time: float):
        cyl_mesh = get_shared_cylinder_mesh()
        cone_mesh = get_shared_cone_mesh()
        cube_mesh = get_shared_cube_mesh()

        dx_sway, _, dz_sway = self.shake_offset

        fall_angle = 0.0
        if self.falling:
            t = self.fall_progress
            fall_angle = 90.0 * (t * t)

        fall_rad = math.radians(self.fall_direction)
        rot_x_angle = fall_angle * math.cos(fall_rad)
        rot_z_angle = fall_angle * math.sin(fall_rad)

        m_fall_pivot = translate(self.x, 0.0, self.z)
        if fall_angle > 0.1:
            m_fall_pivot = m_fall_pivot @ rotate_x(rot_x_angle) @ rotate_z(rot_z_angle)
            dx_sway, dz_sway = 0.0, 0.0

        # 1. Tronco com albedo, normal e roughness PBR de casca real.
        shader.set_uniform_int("u_is_foliage", 0)
        shader.set_uniform_int("u_use_texture", 1)
        shader.set_uniform_int("u_use_pbr", 1)
        shader.set_uniform_int("u_has_damaged_set", 0)
        shader.set_uniform_float("u_uv_scale", 2.2)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.bark_set["albedo"])
        shader.set_uniform_int("u_texture", 0)
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.bark_set["normal"])
        shader.set_uniform_int("u_normal_map", 1)
        glActiveTexture(GL_TEXTURE2)
        glBindTexture(GL_TEXTURE_2D, self.bark_set["roughness"])
        shader.set_uniform_int("u_roughness_map", 2)
        glActiveTexture(GL_TEXTURE0)
        m_trunk = m_fall_pivot @ scale(self.trunk_radius, self.trunk_height, self.trunk_radius)
        shader.set_uniform_mat4("u_model", m_trunk)
        shader.set_uniform_vec4("u_base_color", (0.38, 0.24, 0.12, 1.0))
        cyl_mesh.draw()

        # 2. Copa em camadas
        shader.set_uniform_int("u_use_texture", 0)
        shader.set_uniform_int("u_use_pbr", 0)
        shader.set_uniform_int("u_is_foliage", 1)
        layer_h = self.foliage_height / self.foliage_layers
        for i in range(self.foliage_layers):
            t = i / self.foliage_layers
            y0 = self.trunk_height + t * self.foliage_height
            rad = self.foliage_radius * (1.0 - t * 0.55)
            sway = (y0 / self.total_height) * 1.8 if not self.falling else 0.0

            m_cone = m_fall_pivot @ translate(dx_sway * sway, y0, dz_sway * sway) @ scale(rad, layer_h * 1.3, rad)
            shader.set_uniform_mat4("u_model", m_cone)
            g = 0.38 + t * 0.12
            shader.set_uniform_vec4("u_base_color", (0.12, g, 0.16, 1.0))
            cone_mesh.draw()

        shader.set_uniform_int("u_is_foliage", 0)

        # 3. Terra revolvida (dry_river_pebbles) quando a árvore cai
        if self.falling and self.fall_progress >= 1.0:
            pebbles_pbr = get_pbr_set("dry_river_pebbles")
            shader.set_uniform_int("u_use_texture", 1)
            shader.set_uniform_int("u_use_pbr", 1)
            shader.set_uniform_int("u_has_damaged_set", 0)
            shader.set_uniform_float("u_damage_blend", 0.0)
            shader.set_uniform_float("u_uv_scale", 1.5)

            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, pebbles_pbr["albedo"])
            shader.set_uniform_int("u_texture", 0)

            glActiveTexture(GL_TEXTURE1)
            glBindTexture(GL_TEXTURE_2D, pebbles_pbr["normal"])
            shader.set_uniform_int("u_normal_map", 1)

            glActiveTexture(GL_TEXTURE2)
            glBindTexture(GL_TEXTURE_2D, pebbles_pbr["roughness"])
            shader.set_uniform_int("u_roughness_map", 2)

            glActiveTexture(GL_TEXTURE0)

            m_hole = translate(self.x, 0.02, self.z) @ scale(self.trunk_radius * 4.5, 0.04, self.trunk_radius * 4.5)
            shader.set_uniform_mat4("u_model", m_hole)
            shader.set_uniform_vec4("u_base_color", (0.85, 0.85, 0.85, 1.0))
            cube_mesh.draw()


def generate_forest(count=60, center=(0.0, 0.0), radius_range=(18.0, 55.0)):
    forest = []
    r_min, r_max = radius_range
    for _ in range(count):
        theta = random.uniform(0, 2.0 * math.pi)
        r = math.sqrt(random.uniform(r_min**2, r_max**2))
        x = center[0] + r * math.cos(theta)
        z = center[1] + r * math.sin(theta)

        scale_factor = random.uniform(0.75, 1.35)
        trunk_h = 1.6 * scale_factor
        trunk_r = 0.18 * scale_factor
        foliage_h = 2.8 * scale_factor
        foliage_r = 1.1 * scale_factor
        layers = random.choice([2, 3, 4])

        forest.append(Tree(
            x, z,
            trunk_height=trunk_h,
            trunk_radius=trunk_r,
            foliage_layers=layers,
            foliage_height=foliage_h,
            foliage_radius=foliage_r
        ))
    return forest
