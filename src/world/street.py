"""Ruas com asfalto PBR (clean_asphalt) contínuo."""

from OpenGL.GL import (
    glBindTexture, glActiveTexture,
    GL_TEXTURE_2D, GL_TEXTURE0, GL_TEXTURE1, GL_TEXTURE2
)
from ..core.shader import ShaderProgram
from ..core.math_utils import translate, scale
from .shared import get_pbr_set, get_shared_cube_mesh


class Street:
    def __init__(self, x, z, width, length, direction="x"):
        self.x = x
        self.z = z
        self.width = width
        self.length = length
        self.direction = direction
        self.pbr_set = get_pbr_set("clean_asphalt")

    def draw(self, shader: ShaderProgram, earthquake=None, current_time=0.0):
        plane_mesh = get_shared_cube_mesh()
        shader.set_uniform_int("u_building_facade", 0)
        shader.set_uniform_int("u_is_street", 1)
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

        if self.direction == "x":
            m = translate(self.x, 0.018, self.z) @ scale(self.length, 0.035, self.width)
        else:
            m = translate(self.x, 0.018, self.z) @ scale(self.width, 0.035, self.length)
        shader.set_uniform_mat4("u_model", m)
        shader.set_uniform_vec4("u_base_color", (0.90, 0.90, 0.92, 1.0))
        plane_mesh.draw()
