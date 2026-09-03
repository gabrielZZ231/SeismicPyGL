"""Terreno deformável na GPU com texturas PBR (sparse_grass e cracked_concrete_02)."""

import os
import numpy as np
from OpenGL.GL import (
    glBindTexture, glActiveTexture,
    GL_TEXTURE_2D, GL_TEXTURE0, GL_TEXTURE1, GL_TEXTURE2,
    GL_TEXTURE3, GL_TEXTURE4, GL_TEXTURE5
)
from ..core.mesh import Mesh
from ..core.shader import ShaderProgram
from .shared import get_pbr_set


class Ground:
    def __init__(self, size=140.0, divisions=80):
        self.size = size
        self.divisions = divisions
        self.mesh = Mesh.create_plane(size=size, divisions=divisions)

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        vert_path = os.path.join(base_dir, "assets", "shaders", "ground.vert")
        frag_path = os.path.join(base_dir, "assets", "shaders", "ground.frag")
        self.shader = ShaderProgram.from_files(vert_path, frag_path)

        self.grass_pbr = get_pbr_set("sparse_grass")
        self.crack_pbr = get_pbr_set("cracked_concrete_02")

    def draw(self, earthquake, current_time: float, view_matrix: np.ndarray, proj_matrix: np.ndarray,
             light_space_matrix=None, shadow_texture=None, contact_objects=None, camera=None):
        self.shader.use()

        model = np.eye(4, dtype=np.float32)
        self.shader.set_uniform_mat4("u_model", model)
        self.shader.set_uniform_mat4("u_view", view_matrix)
        self.shader.set_uniform_mat4("u_projection", proj_matrix)
        if light_space_matrix is not None:
            self.shader.set_uniform_mat4("u_light_space_matrix", light_space_matrix)

        is_active = 1 if earthquake.active else 0
        self.shader.set_uniform_int("u_active", is_active)
        self.shader.set_uniform_vec2("u_epicenter", earthquake.epicenter)
        self.shader.set_uniform_float("u_time", current_time - earthquake.start_time if earthquake.active else 0.0)
        self.shader.set_uniform_float("u_wave_speed", earthquake.wave_speed)
        self.shader.set_uniform_float("u_amplitude", earthquake.magnitude if earthquake.active else 0.0)
        self.shader.set_uniform_float("u_frequency", earthquake.frequency)
        self.shader.set_uniform_float("u_damping", earthquake.damping)
        self.shader.set_uniform_float("u_spatial_falloff", earthquake.spatial_falloff)
        self.shader.set_uniform_float("u_crack_intensity", earthquake.get_crack_intensity())

        self.shader.set_uniform_vec3("u_light_direction", (-0.4, -1.0, -0.3))
        self.shader.set_uniform_vec3("u_light_color", (1.0, 0.98, 0.92))
        self.shader.set_uniform_vec3("u_ambient_color", (0.35, 0.38, 0.42))
        self.shader.set_uniform_vec4("u_base_color", (0.90, 0.95, 0.88, 1.0))

        if camera:
            self.shader.set_uniform_vec3("u_view_pos", (camera.x, camera.y, camera.z))
        else:
            self.shader.set_uniform_vec3("u_view_pos", (0.0, 5.0, 36.0))

        points = [(obj.x, obj.z) for obj in (contact_objects or [])[:40]]
        self.shader.set_uniform_int("u_contact_count", len(points))
        if points:
            self.shader.set_uniform_vec2_array("u_contact_points[0]", points)

        self.shader.set_uniform_int("u_use_texture", 1)
        self.shader.set_uniform_int("u_use_pbr", 1)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.grass_pbr["albedo"])
        self.shader.set_uniform_int("u_texture", 0)

        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.grass_pbr["normal"])
        self.shader.set_uniform_int("u_normal_map", 1)

        glActiveTexture(GL_TEXTURE2)
        glBindTexture(GL_TEXTURE_2D, self.grass_pbr["roughness"])
        self.shader.set_uniform_int("u_roughness_map", 2)

        glActiveTexture(GL_TEXTURE3)
        glBindTexture(GL_TEXTURE_2D, self.crack_pbr["albedo"])
        self.shader.set_uniform_int("u_crack_texture", 3)

        glActiveTexture(GL_TEXTURE4)
        glBindTexture(GL_TEXTURE_2D, self.crack_pbr["normal"])
        self.shader.set_uniform_int("u_crack_normal_map", 4)

        if shadow_texture is not None:
            glActiveTexture(GL_TEXTURE5)
            glBindTexture(GL_TEXTURE_2D, shadow_texture)
            self.shader.set_uniform_int("u_shadow_map", 5)

        self.mesh.draw()

        self.shader.stop()
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, 0)

    def cleanup(self):
        if self.mesh:
            self.mesh.cleanup()
            self.mesh = None
        if self.shader:
            self.shader.cleanup()
            self.shader = None
