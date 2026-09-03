"""
Céu HDRI 360 panorâmico baseado nas texturas Poly Haven (meadow_2 / nowhere_road).
Acompanha a rotação da câmera (Yaw/Pitch/Roll) em tempo real.
"""
import os
import numpy as np
from OpenGL.GL import (
    glDisable, glEnable, glDepthMask, glBindTexture, glActiveTexture,
    GL_DEPTH_TEST, GL_TEXTURE_2D, GL_TEXTURE0, GL_REPEAT
)
try:
    from ..core.mesh import Mesh
    from ..core.shader import ShaderProgram
    from ..core.texture import load_texture
except ImportError:
    from mesh import Mesh
    from shader import ShaderProgram
    from texture import load_texture


class Sky:
    def __init__(self, hdri_name="meadow_2"):
        self.mesh = Mesh.create_quad(2.0)
        curr = os.path.dirname(os.path.abspath(__file__))
        while curr and not os.path.exists(os.path.join(curr, "assets")):
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent
        base_dir = curr

        vert_path = os.path.join(base_dir, "assets", "shaders", "sky.vert")
        frag_path = os.path.join(base_dir, "assets", "shaders", "sky.frag")
        self.shader = ShaderProgram.from_files(vert_path, frag_path)

        path = os.path.join(base_dir, "assets", "textures", f"{hdri_name}_sky.jpg")
        if not os.path.exists(path):
            path = os.path.join(base_dir, "assets", "textures", "meadow_2_sky.jpg")
        self.texture_id = load_texture(path, wrap=GL_REPEAT)

    def draw(self, view_matrix: np.ndarray, proj_matrix: np.ndarray, elapsed_time: float = 0.0):
        glDisable(GL_DEPTH_TEST)
        glDepthMask(False)
        self.shader.use()

        # Isola a rotação da câmera (remove translação X, Y, Z para o céu ser infinito)
        view_rot = view_matrix.copy()
        view_rot[3, 0] = 0.0
        view_rot[3, 1] = 0.0
        view_rot[3, 2] = 0.0
        view_rot[0, 3] = 0.0
        view_rot[1, 3] = 0.0
        view_rot[2, 3] = 0.0
        view_rot[3, 3] = 1.0

        view_proj = proj_matrix @ view_rot
        inv_view_proj = np.linalg.inv(view_proj).astype(np.float32)

        self.shader.set_uniform_mat4("u_inv_view_proj", inv_view_proj)
        self.shader.set_uniform_float("u_time", elapsed_time)
        self.shader.set_uniform_int("u_sky_texture", 0)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)

        self.mesh.draw()

        self.shader.stop()
        glDepthMask(True)
        glEnable(GL_DEPTH_TEST)

    def cleanup(self):
        if self.mesh:
            self.mesh.cleanup()
        if self.shader:
            self.shader.cleanup()

