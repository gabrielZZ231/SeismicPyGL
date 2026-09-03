"""
Sistema de partículas para simulação de poeira e fumaça de desabamento.
Utiliza:
- Billboarding esférico (quads perenemente orientados para a câmera)
- Alpha blending configurável (GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
- ShaderProgram dedicado (billboard.vert / billboard.frag)
- Textura com gradiente radial suave
"""

import ctypes
import math
import random
import numpy as np
from OpenGL.GL import (
    glEnable, glDisable, glBlendFunc, glDepthMask,
    glBindTexture, glBindVertexArray, glGenBuffers, glBindBuffer, glBufferData, glBufferSubData,
    glDeleteBuffers, glVertexAttribPointer, glEnableVertexAttribArray,
    glVertexAttribDivisor, glDrawArraysInstanced,
    GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_TEXTURE_2D,
    GL_ARRAY_BUFFER, GL_DYNAMIC_DRAW, GL_FLOAT, GL_FALSE, GL_TRIANGLES,
)
try:
    from ..core.mesh import Mesh
    from ..core.shader import ShaderProgram
    from ..core.texture import load_texture
except ImportError:
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
    def __init__(self, max_particles=6000):
        self.max_particles = max_particles
        self.particles = []
        self._ambient_dust_budget = 0.0
        self._leaf_budget = 0.0

        # Recursos GPU
        self.mesh = Mesh.create_quad(size=1.0)
        self.instance_vbo = glGenBuffers(1)
        self.instance_stride = 8 * 4  # posição, tamanho, alpha e cor RGB

        # Os dados que mudam por partícula ficam num VBO dinâmico. O quad é
        # compartilhado pela GPU e glDrawArraysInstanced o replica em uma só
        # draw call, inclusive quando há milhares de partículas no colapso.
        glBindVertexArray(self.mesh.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.instance_vbo)
        glBufferData(GL_ARRAY_BUFFER, self.max_particles * self.instance_stride, None, GL_DYNAMIC_DRAW)

        glVertexAttribPointer(3, 3, GL_FLOAT, GL_FALSE, self.instance_stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(3)
        glVertexAttribDivisor(3, 1)
        glVertexAttribPointer(4, 1, GL_FLOAT, GL_FALSE, self.instance_stride, ctypes.c_void_p(12))
        glEnableVertexAttribArray(4)
        glVertexAttribDivisor(4, 1)
        glVertexAttribPointer(5, 1, GL_FLOAT, GL_FALSE, self.instance_stride, ctypes.c_void_p(16))
        glEnableVertexAttribArray(5)
        glVertexAttribDivisor(5, 1)
        glVertexAttribPointer(6, 3, GL_FLOAT, GL_FALSE, self.instance_stride, ctypes.c_void_p(20))
        glEnableVertexAttribArray(6)
        glVertexAttribDivisor(6, 1)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
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

    def emit_ambient(self, camera_position, forest, dt: float):
        """Pólen e folhas discretos em repouso; continuam no VBO instanciado."""
        self._ambient_dust_budget += dt * 3.0
        self._leaf_budget += dt * 0.9
        cx, cy, cz = camera_position

        while self._ambient_dust_budget >= 1.0 and len(self.particles) < self.max_particles:
            self._ambient_dust_budget -= 1.0
            angle = random.uniform(0.0, math.tau)
            radius = random.uniform(4.0, 20.0)
            p = Particle(
                (cx + math.cos(angle) * radius, random.uniform(0.35, 3.5), cz + math.sin(angle) * radius),
                (random.uniform(-0.18, 0.18), random.uniform(0.08, 0.30), random.uniform(-0.18, 0.18)),
                size_range=(0.05, 0.13), lifetime_range=(4.0, 7.0), color=(0.90, 0.82, 0.62),
            )
            p.max_size = p.initial_size * 1.25
            self.particles.append(p)

        while self._leaf_budget >= 1.0 and len(self.particles) < self.max_particles:
            self._leaf_budget -= 1.0
            nearby = [t for t in forest if math.hypot(t.x - cx, t.z - cz) < 30.0]
            if not nearby:
                continue
            tree = random.choice(nearby)
            color = random.choice(((0.21, 0.38, 0.12), (0.38, 0.29, 0.10), (0.48, 0.36, 0.12)))
            p = Particle(
                (tree.x + random.uniform(-tree.foliage_radius, tree.foliage_radius),
                 tree.trunk_height + tree.foliage_height * random.uniform(0.45, 0.95),
                 tree.z + random.uniform(-tree.foliage_radius, tree.foliage_radius)),
                (random.uniform(-0.45, 0.45), random.uniform(-0.55, -0.18), random.uniform(-0.45, 0.45)),
                size_range=(0.07, 0.15), lifetime_range=(2.5, 4.5), color=color,
            )
            p.max_size = p.initial_size
            self.particles.append(p)

    def draw(self, view_matrix: np.ndarray, projection_matrix: np.ndarray):
        """
        Renderiza todas as partículas com billboarding esférico e alpha blending.
        """
        if not self.particles:
            return

        # Extrai Right e Up em espaço de mundo para orientar os quads.
        cam_right = view_matrix[0, 0:3]
        cam_up = view_matrix[1, 0:3]

        instance_data = np.empty((len(self.particles), 8), dtype=np.float32)
        for i, p in enumerate(self.particles):
            instance_data[i] = (p.x, p.y, p.z, p.size, p.alpha, *p.color)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthMask(False)  # Desabilita escrita no depth buffer para transparência perfeita

        self.shader.use()
        self.shader.set_uniform_mat4("u_view", view_matrix)
        self.shader.set_uniform_mat4("u_projection", projection_matrix)
        self.shader.set_uniform_vec3("u_camera_right", cam_right)
        self.shader.set_uniform_vec3("u_camera_up", cam_up)
        self.shader.set_uniform_int("u_texture", 0)

        glBindTexture(GL_TEXTURE_2D, self.texture_id)

        glBindBuffer(GL_ARRAY_BUFFER, self.instance_vbo)
        glBufferSubData(GL_ARRAY_BUFFER, 0, instance_data.nbytes, instance_data)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(self.mesh.vao)
        glDrawArraysInstanced(GL_TRIANGLES, 0, self.mesh.vertex_count, len(self.particles))
        glBindVertexArray(0)

        self.shader.stop()
        glDepthMask(True)
        glBindTexture(GL_TEXTURE_2D, 0)

    def cleanup(self):
        """Libera malha e shader do sistema de partículas."""
        if self.mesh:
            self.mesh.cleanup()
            self.mesh = None
        if self.instance_vbo is not None:
            glDeleteBuffers(1, [self.instance_vbo])
            self.instance_vbo = None
        if self.shader:
            self.shader.cleanup()
            self.shader = None
