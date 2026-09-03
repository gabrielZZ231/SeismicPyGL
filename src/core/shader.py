"""
Gerenciamento e compilação de shaders GLSL modernos em PyOpenGL.
Inclui:
- ShaderProgram com compilação e validação de erros de compilação/linkagem
- Cache de Uniform Locations
- Métodos set_uniform para mat4, vec2, vec3, vec4, float e int
- Cleanup seguro de shaders e programas
"""

import os
import numpy as np
from OpenGL.GL import (
    glCreateShader, glShaderSource, glCompileShader, glGetShaderiv,
    glGetShaderInfoLog, glDeleteShader, glCreateProgram, glAttachShader,
    glLinkProgram, glGetProgramiv, glGetProgramInfoLog, glUseProgram,
    glDeleteProgram, glGetUniformLocation, glUniform1i, glUniform1f,
    glUniform2f, glUniform2fv, glUniform3f, glUniform4f, glUniformMatrix4fv,
    glGetError, GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
    GL_COMPILE_STATUS, GL_LINK_STATUS, GL_FALSE, GL_NO_ERROR,
)
try:
    from .math_utils import to_gl_matrix
except ImportError:
    from math_utils import to_gl_matrix


def check_gl_error(label: str = ""):
    """Verifica e imprime erros do OpenGL."""
    err = glGetError()
    if err != GL_NO_ERROR:
        print(f"[OpenGL Error] {label}: Code {err}")
    return err


class ShaderProgram:
    def __init__(self, vertex_source: str, fragment_source: str):
        self.program_id = None
        self._uniform_cache = {}
        self._build(vertex_source, fragment_source)

    @classmethod
    def from_files(cls, vertex_path: str, fragment_path: str):
        """Carrega e compila shaders a partir de arquivos de texto no disco."""
        if not os.path.exists(vertex_path):
            raise FileNotFoundError(f"Shader de vértice não encontrado: {vertex_path}")
        if not os.path.exists(fragment_path):
            raise FileNotFoundError(f"Shader de fragmento não encontrado: {fragment_path}")

        with open(vertex_path, "r", encoding="utf-8") as f:
            vert_src = f.read()
        with open(fragment_path, "r", encoding="utf-8") as f:
            frag_src = f.read()

        return cls(vert_src, frag_src)

    def _compile_shader(self, source: str, shader_type: int) -> int:
        shader_id = glCreateShader(shader_type)
        glShaderSource(shader_id, source)
        glCompileShader(shader_id)

        status = glGetShaderiv(shader_id, GL_COMPILE_STATUS)
        if not status:
            log = glGetShaderInfoLog(shader_id)
            if isinstance(log, bytes):
                log = log.decode("utf-8")
            stype = "VERTEX" if shader_type == GL_VERTEX_SHADER else "FRAGMENT"
            glDeleteShader(shader_id)
            raise RuntimeError(f"Erro na compilação do {stype} shader:\n{log}")

        return shader_id

    def _build(self, vertex_source: str, fragment_source: str):
        vert_id = self._compile_shader(vertex_source, GL_VERTEX_SHADER)
        frag_id = self._compile_shader(fragment_source, GL_FRAGMENT_SHADER)

        self.program_id = glCreateProgram()
        glAttachShader(self.program_id, vert_id)
        glAttachShader(self.program_id, frag_id)
        glLinkProgram(self.program_id)

        status = glGetProgramiv(self.program_id, GL_LINK_STATUS)
        if not status:
            log = glGetProgramInfoLog(self.program_id)
            if isinstance(log, bytes):
                log = log.decode("utf-8")
            glDeleteShader(vert_id)
            glDeleteShader(frag_id)
            glDeleteProgram(self.program_id)
            self.program_id = None
            raise RuntimeError(f"Erro na linkagem do Shader Program:\n{log}")

        # Shaders podem ser deletados após linkados com sucesso no programa
        glDeleteShader(vert_id)
        glDeleteShader(frag_id)

    def use(self):
        if self.program_id is not None:
            glUseProgram(self.program_id)

    def stop(self):
        glUseProgram(0)

    def get_uniform_location(self, name: str) -> int:
        if name in self._uniform_cache:
            return self._uniform_cache[name]
        loc = glGetUniformLocation(self.program_id, name)
        self._uniform_cache[name] = loc
        return loc

    def set_uniform_int(self, name: str, value: int):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform1i(loc, int(value))

    def set_uniform_float(self, name: str, value: float):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform1f(loc, float(value))

    def set_uniform_vec2(self, name: str, v):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform2f(loc, float(v[0]), float(v[1]))

    def set_uniform_vec2_array(self, name: str, values):
        """Envia uma pequena lista vec2 contígua (ex.: pontos de contato no chão)."""
        loc = self.get_uniform_location(name)
        if loc != -1 and len(values):
            data = np.ascontiguousarray(values, dtype=np.float32)
            glUniform2fv(loc, len(data), data)

    def set_uniform_vec3(self, name: str, v):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform3f(loc, float(v[0]), float(v[1]), float(v[2]))

    def set_uniform_vec4(self, name: str, v):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform4f(loc, float(v[0]), float(v[1]), float(v[2]), float(v[3]))

    def set_uniform_mat4(self, name: str, matrix: np.ndarray):
        loc = self.get_uniform_location(name)
        if loc != -1:
            gl_mat = to_gl_matrix(matrix)
            glUniformMatrix4fv(loc, 1, GL_FALSE, gl_mat)

    def cleanup(self):
        if self.program_id is not None:
            glDeleteProgram(self.program_id)
            self.program_id = None
            self._uniform_cache.clear()
