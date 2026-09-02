"""
Sistema de partículas para simulação de poeira e fumaça de desabamento.
Utiliza:
- Billboarding esférico (quads perenemente orientados para a câmera)
- Alpha blending configurável (GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
- ShaderProgram dedicado (billboard.vert / billboard.frag)
- Textura com gradiente radial suave
"""

import math
import random
import numpy as np
from OpenGL.GL import (
    glEnable, glDisable, glBlendFunc, glDepthMask,
    glBindTexture, GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    GL_TEXTURE_2D,
)
from mesh import Mesh
from shader import ShaderProgram
from texture import load_texture


class Particle:
    __slots__ = ("x", "y", "z", "vx", "vy", "vz", "size", "initial_size",
                 "max_size", "alpha", "life", "lifetime", "color")

    def __init__(self, pos, vel, size_range=(0.6, 1.8), lifetime_range=(1.5, 3.2), color=None):
        self.x, self.y, self.z = pos
        self.vx, self.vy, self.vz = vel
        self.initial_size = random.uniform(*size_range)
        self.size = self.initial_size
        self.max_size = self.initial_size * random.uniform(2.0, 3.5)
        self.lifetime = random.uniform(*lifetime_range)
        self.life = 0.0
        self.alpha = 1.0

        # Variação de tons de poeira/concreto
        gray = random.uniform(0.70, 0.85)
        self.color = color or (gray, gray * 0.95, gray * 0.90)

    @property
    def alive(self) -> bool:
        return self.life < self.lifetime

    def update(self, dt: float):
        self.life += dt
        t = self.life / self.lifetime
        if t >= 1.0:
            self.alpha = 0.0
            return

        # Movimento e amortecimento
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        # Fricção do ar e leve subida térmica
        self.vx *= (0.95 ** (dt * 60.0))
        self.vz *= (0.95 ** (dt * 60.0))
        self.vy = self.vy * (0.95 ** (dt * 60.0)) + 0.35 * dt

        # Expansão da nuvem de poeira e desvanecimento do alpha
        self.size = self.initial_size + (self.max_size - self.initial_size) * (t ** 0.7)
        # Fade out suave no final
        self.alpha = max(0.0, (1.0 - t) ** 1.3)


class ParticleSystem:
    def __init__(self, max_particles=600):
        self.max_particles = max_particles
        self.particles = []

        # Recursos GPU
        self.mesh = Mesh.create_quad(size=1.0)
        self.texture_id = load_texture("assets/textures/smoke.png")
        self.shader = ShaderProgram.from_files(
            "assets/shaders/billboard.vert",
            "assets/shaders/billboard.frag"
        )

    def emit(self, position, count=35, spread=1.2, base_speed=1.8):
        """Dispara uma rajada de partículas em torno de position."""
        px, py, pz = position
        for _ in range(count):
            if len(self.particles) >= self.max_particles:
                break

            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.4, base_speed)
            vx = math.cos(angle) * speed + random.uniform(-0.2, 0.2)
            vy = random.uniform(0.5, base_speed * 1.5)
            vz = math.sin(angle) * speed + random.uniform(-0.2, 0.2)

            # Posição inicial ligeiramente espalhada na base
            offset_r = random.uniform(0.0, spread)
            offset_a = random.uniform(0, 2 * math.pi)
            pos = (
                px + math.cos(offset_a) * offset_r,
                py + random.uniform(0.0, 0.4),
                pz + math.sin(offset_a) * offset_r,
            )

            p = Particle(pos, (vx, vy, vz))
            self.particles.append(p)

    def update(self, dt: float):
        """Atualiza a simulação das partículas e descarta as expiradas."""
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

    def draw(self, view_matrix: np.ndarray, projection_matrix: np.ndarray):
        """
        Renderiza todas as partículas com billboarding esférico e alpha blending.
        """
        if not self.particles:
            return

        # Extrai os vetores Right e Up da View Matrix para orientar os quads
        # Linha 0 = Right, Linha 1 = Up
        cam_right = view_matrix[0, 0:3]
        cam_up = view_matrix[1, 0:3]
        cam_dir = view_matrix[2, 0:3]

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthMask(False)  # Desabilita escrita no depth buffer para transparência perfeita

        self.shader.use()
        self.shader.set_uniform_mat4("u_view", view_matrix)
        self.shader.set_uniform_mat4("u_projection", projection_matrix)
        self.shader.set_uniform_int("u_texture", 0)

        glBindTexture(GL_TEXTURE_2D, self.texture_id)

        # Matriz de modelo do billboard:
        # Coluna 0: Right * size
        # Coluna 1: Up * size
        # Coluna 2: Dir * size
        # Coluna 3: Pos
        model = np.eye(4, dtype=np.float32)

        for p in self.particles:
            s = p.size
            model[0:3, 0] = cam_right * s
            model[0:3, 1] = cam_up * s
            model[0:3, 2] = cam_dir * s
            model[0, 3] = p.x
            model[1, 3] = p.y
            model[2, 3] = p.z

            self.shader.set_uniform_mat4("u_model", model)
            self.shader.set_uniform_float("u_particle_alpha", p.alpha)
            self.shader.set_uniform_vec3("u_particle_color", p.color)

            self.mesh.draw()

        self.shader.stop()
        glDepthMask(True)
        glBindTexture(GL_TEXTURE_2D, 0)

    def cleanup(self):
        """Libera malha e shader do sistema de partículas."""
        if self.mesh:
            self.mesh.cleanup()
            self.mesh = None
        if self.shader:
            self.shader.cleanup()
            self.shader = None
