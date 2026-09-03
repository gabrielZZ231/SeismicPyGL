"""
Gerenciamento de geometria na GPU via VAO (Vertex Array Object)
e VBO (Vertex Buffer Object) no padrão moderno do OpenGL 3.3+.
Layout entrelaçado (stride = 32 bytes):
- Location 0: Posição (vec3, 3 floats, offset 0)
- Location 1: UV (vec2, 2 floats, offset 12)
- Location 2: Normal (vec3, 3 floats, offset 20)
"""

import os
import sys
if sys.platform.startswith("linux") and "PYOPENGL_PLATFORM" not in os.environ:
    os.environ["PYOPENGL_PLATFORM"] = "glx"

import ctypes
import numpy as np
from OpenGL.GL import (
    glGenVertexArrays, glBindVertexArray, glDeleteVertexArrays,
    glGenBuffers, glBindBuffer, glBufferData, glDeleteBuffers,
    glVertexAttribPointer, glEnableVertexAttribArray, glDrawArrays,
    GL_ARRAY_BUFFER, GL_STATIC_DRAW, GL_FLOAT, GL_FALSE, GL_TRIANGLES,
)
try:
    from .obj_loader import parse_obj, create_cube_mesh, create_plane_mesh, create_quad_mesh, create_cylinder_mesh
except ImportError:
    from obj_loader import parse_obj, create_cube_mesh, create_plane_mesh, create_quad_mesh, create_cylinder_mesh


class Mesh:
    def __init__(self, vertex_data: np.ndarray, vertex_count: int, stride: int = 32):
        self.vertex_count = vertex_count
        self.stride = stride
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)

        # Garante array contíguo em float32
        data = np.ascontiguousarray(vertex_data, dtype=np.float32)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)

        # Atributo 0: Posição (x, y, z)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, self.stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        # Atributo 1: Coordenadas UV (u, v)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, self.stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        # Atributo 2: Vetor Normal (nx, ny, nz)
        glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, self.stride, ctypes.c_void_p(20))
        glEnableVertexAttribArray(2)

        # Atributo 3: Vetor Tangente (tx, ty, tz) para Normal Mapping
        if self.stride >= 44:
            glVertexAttribPointer(3, 3, GL_FLOAT, GL_FALSE, self.stride, ctypes.c_void_p(32))
            glEnableVertexAttribArray(3)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    @classmethod
    def from_obj(cls, file_path: str):
        vdata, count, stride = parse_obj(file_path)
        return cls(vdata, count, stride)

    @classmethod
    def create_cube(cls, width=1.0, height=1.0, depth=1.0, y_offset=0.0):
        vdata, count, stride = create_cube_mesh(width, height, depth, y_offset)
        return cls(vdata, count, stride)

    @classmethod
    def create_plane(cls, size=100.0, divisions=50):
        vdata, count, stride = create_plane_mesh(size, divisions)
        return cls(vdata, count, stride)

    @classmethod
    def create_quad(cls, size=1.0):
        vdata, count, stride = create_quad_mesh(size)
        return cls(vdata, count, stride)

    @classmethod
    def create_cylinder(cls, base_radius=1.0, top_radius=1.0, height=1.0, slices=16):
        vdata, count, stride = create_cylinder_mesh(base_radius, top_radius, height, slices)
        return cls(vdata, count, stride)

    def draw(self):
        """Renderiza a geometria com glDrawArrays."""
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLES, 0, self.vertex_count)
        glBindVertexArray(0)

    def cleanup(self):
        """Libera o VAO e VBO da memória de vídeo."""
        if self.vbo is not None:
            glDeleteBuffers(1, [self.vbo])
            self.vbo = None
        if self.vao is not None:
            glDeleteVertexArrays(1, [self.vao])
            self.vao = None
