"""
Núcleo matemático puro em Python/NumPy para o SeismicPyGL.
Contém:
- Matrizes 4x4 (Perspective, LookAt, Ortho, Translate, Rotate, Scale)
- Multiplicação de matrizes e conversão para GLSL
- Gerador de Ruído de Perlin 1D e 2D puro (sem dependências C)
"""

import math
import numpy as np


# ---------------------------------------------------------------------------
# Matrizes 4x4 (Column-vector / OpenGL standard)
# ---------------------------------------------------------------------------

def identity() -> np.ndarray:
    return np.eye(4, dtype=np.float32)


def perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    """Gera matriz de projeção perspectiva compatível com OpenGL."""
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye, target, up=(0.0, 1.0, 0.0)) -> np.ndarray:
    """Gera matriz de visualização (View Matrix) Look-At."""
    eye = np.array(eye, dtype=np.float32)
    target = np.array(target, dtype=np.float32)
    up = np.array(up, dtype=np.float32)

    forward = target - eye
    norm_f = np.linalg.norm(forward)
    if norm_f == 0.0:
        forward = np.array([0.0, 0.0, -1.0], dtype=np.float32)
    else:
        forward = forward / norm_f

    side = np.cross(forward, up)
    norm_s = np.linalg.norm(side)
    if norm_s == 0.0:
        side = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    else:
        side = side / norm_s

    up_vec = np.cross(side, forward)

    m = np.eye(4, dtype=np.float32)
    m[0, 0:3] = side
    m[1, 0:3] = up_vec
    m[2, 0:3] = -forward
    m[0, 3] = -float(np.dot(side, eye))
    m[1, 3] = -float(np.dot(up_vec, eye))
    m[2, 3] = float(np.dot(forward, eye))
    return m


def ortho(left: float, right: float, bottom: float, top: float, near: float = -1.0, far: float = 1.0) -> np.ndarray:
    """Gera matriz de projeção ortográfica 4x4 (usada para HUD 2D)."""
    m = np.zeros((4, 4), dtype=np.float32)
    m[0, 0] = 2.0 / (right - left)
    m[1, 1] = 2.0 / (top - bottom)
    m[2, 2] = -2.0 / (far - near)
    m[0, 3] = -(right + left) / (right - left)
    m[1, 3] = -(top + bottom) / (top - bottom)
    m[2, 3] = -(far + near) / (far - near)
    m[3, 3] = 1.0
    return m


def translate(x: float, y: float, z: float) -> np.ndarray:
    m = np.eye(4, dtype=np.float32)
    m[0, 3] = x
    m[1, 3] = y
    m[2, 3] = z
    return m


def scale(sx: float, sy: float, sz: float) -> np.ndarray:
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = sx
    m[1, 1] = sy
    m[2, 2] = sz
    return m


def rotate_x(angle_deg: float) -> np.ndarray:
    rad = math.radians(angle_deg)
    c, s = math.cos(rad), math.sin(rad)
    m = np.eye(4, dtype=np.float32)
    m[1, 1] = c
    m[1, 2] = -s
    m[2, 1] = s
    m[2, 2] = c
    return m


def rotate_y(angle_deg: float) -> np.ndarray:
    rad = math.radians(angle_deg)
    c, s = math.cos(rad), math.sin(rad)
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = c
    m[0, 2] = s
    m[2, 0] = -s
    m[2, 2] = c
    return m


def rotate_z(angle_deg: float) -> np.ndarray:
    rad = math.radians(angle_deg)
    c, s = math.cos(rad), math.sin(rad)
    m = np.eye(4, dtype=np.float32)
    m[0, 0] = c
    m[0, 1] = -s
    m[1, 0] = s
    m[1, 1] = c
    return m


def to_gl_matrix(matrix: np.ndarray) -> np.ndarray:
    """
    Converte a matriz NumPy (armazenada linha a linha) para o formato
    column-major contíguo exigido pelo OpenGL com glUniformMatrix4fv(transpose=GL_FALSE).
    """
    return np.ascontiguousarray(matrix.T, dtype=np.float32)


# ---------------------------------------------------------------------------
# Ruído de Perlin puro em Python/NumPy (1D e 2D)
# ---------------------------------------------------------------------------

class PerlinNoise:
    """Implementação clássica de Ruído de Perlin (Improved Noise de Ken Perlin)."""

    def __init__(self, seed: int = 42):
        rng = np.random.default_rng(seed)
        p = np.arange(256, dtype=int)
        rng.shuffle(p)
        self.p = np.tile(p, 2)  # Duplica para evitar modulo nos lookups

    @staticmethod
    def _fade(t: float) -> float:
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)

    @staticmethod
    def _lerp(t: float, a: float, b: float) -> float:
        return a + t * (b - a)

    @staticmethod
    def _grad1d(hash_val: int, x: float) -> float:
        h = hash_val & 15
        grad = 1.0 + (h & 7)  # gradiente 1.0 .. 8.0
        if h & 8:
            grad = -grad
        return grad * x

    @staticmethod
    def _grad2d(hash_val: int, x: float, y: float) -> float:
        h = hash_val & 3
        u = x if (h & 1) == 0 else -x
        v = y if (h & 2) == 0 else -y
        return u + v

    def noise1d(self, x: float) -> float:
        """Gera ruído 1D contínuo e suave aproximadamente em [-1, 1]."""
        xi = int(math.floor(x)) & 255
        xf = x - math.floor(x)
        u = self._fade(xf)

        g0 = self._grad1d(self.p[xi], xf)
        g1 = self._grad1d(self.p[xi + 1], xf - 1.0)
        return self._lerp(u, g0, g1) * 0.25

    def noise2d(self, x: float, y: float) -> float:
        """Gera ruído 2D contínuo e suave aproximadamente em [-1, 1]."""
        xi = int(math.floor(x)) & 255
        yi = int(math.floor(y)) & 255
        xf = x - math.floor(x)
        yf = y - math.floor(y)

        u = self._fade(xf)
        v = self._fade(yf)

        aa = self.p[self.p[xi] + yi]
        ab = self.p[self.p[xi] + yi + 1]
        ba = self.p[self.p[xi + 1] + yi]
        bb = self.p[self.p[xi + 1] + yi + 1]

        x1 = self._lerp(u, self._grad2d(aa, xf, yf), self._grad2d(ba, xf - 1.0, yf))
        x2 = self._lerp(u, self._grad2d(ab, xf, yf - 1.0), self._grad2d(bb, xf - 1.0, yf - 1.0))
        return self._lerp(v, x1, x2)


# Instância global padrão para conveniência
_default_perlin = PerlinNoise(42)

def perlin1d(x: float, seed: int = None) -> float:
    if seed is not None:
        return PerlinNoise(seed).noise1d(x)
    return _default_perlin.noise1d(x)

def perlin2d(x: float, y: float, seed: int = None) -> float:
    if seed is not None:
        return PerlinNoise(seed).noise2d(x, y)
    return _default_perlin.noise2d(x, y)
