"""
Câmera livre 3D estilo primeira pessoa com suporte a:
- Movimentação livre (WASD, Shift sprint, descida S)
- Rotação via mouse (Euler angles: Pitch e Yaw)
- Zoom via FOV dinâmico (Mouse Wheel)
- Sistema de Trauma & Screen Shake com Ruído de Perlin (Pitch, Yaw, Roll e Translação)
- Matriz de visualização 4x4 (get_view_matrix) para Shaders GLSL modernos
- Compatibilidade com gluLookAt (apply)
"""

import math
import numpy as np
import pygame
from OpenGL.GLU import gluLookAt
from math_utils import look_at, perlin1d


class FreeCamera:
    def __init__(self, position=(0.0, 8.0, 30.0), yaw=-90.0, pitch=-15.0,
                 move_speed=15.0, sprint_multiplier=3.0, mouse_sensitivity=0.12,
                 fov=55.0, zoom_speed=3.0, fov_min=20.0, fov_max=90.0):
        self.x, self.y, self.z = position
        self.yaw = yaw       # graus; -90 aponta para -Z (padrão OpenGL)
        self.pitch = pitch   # graus; limitado para não "virar de cabeça pra baixo"
        self.move_speed = move_speed
        self.sprint_multiplier = sprint_multiplier
        self.mouse_sensitivity = mouse_sensitivity

        self.fov = fov               # campo de visão atual (graus)
        self.zoom_speed = zoom_speed
        self.fov_min = fov_min       # zoom in
        self.fov_max = fov_max       # zoom out

        # --- Variáveis de Estado de Trauma & Screen Shake ---
        self.trauma = 0.0
        self.trauma_decay = 1.2      # Decaimento linear do trauma por segundo
        self.shake_time = 0.0
        self.shake_frequency = 28.0  # Frequência de vibração

        # Limites máximos de shake quando trauma = 1.0
        self.max_yaw_shake = 6.0     # graus
        self.max_pitch_shake = 5.0   # graus
        self.max_roll_shake = 4.0    # graus
        self.max_trans_shake = 0.6   # unidades de mundo

        # Offsets calculados a cada frame
        self._shake_yaw = 0.0
        self._shake_pitch = 0.0
        self._shake_roll = 0.0
        self._shake_pos = (0.0, 0.0, 0.0)

    def add_trauma(self, amount: float):
        """Injeta trauma no intervalo [0.0, 1.0]."""
        self.trauma = min(1.0, max(0.0, self.trauma + amount))

    def update_trauma(self, dt: float):
        """Atualiza decaimento do trauma e calcula vibração com Perlin Noise."""
        self.trauma = max(0.0, self.trauma - self.trauma_decay * dt)
        self.shake_time += dt

        if self.trauma > 0.0001:
            shake = self.trauma ** 3  # Queda não-linear cúbica mais dramática
            t = self.shake_time * self.shake_frequency

            # Amostra ruído de Perlin em seeds/offsets diferentes para dessincronizar eixos
            self._shake_yaw = self.max_yaw_shake * shake * perlin1d(t + 0.0)
            self._shake_pitch = self.max_pitch_shake * shake * perlin1d(t + 113.7)
            self._shake_roll = self.max_roll_shake * shake * perlin1d(t + 227.4)

            dx = self.max_trans_shake * shake * perlin1d(t + 341.1)
            dy = self.max_trans_shake * shake * perlin1d(t + 454.8)
            dz = self.max_trans_shake * shake * perlin1d(t + 568.5)
            self._shake_pos = (dx, dy, dz)
        else:
            self._shake_yaw = 0.0
            self._shake_pitch = 0.0
            self._shake_roll = 0.0
            self._shake_pos = (0.0, 0.0, 0.0)

    def zoom(self, scroll_amount):
        """scroll_amount vem de event.y do MOUSEWHEEL: positivo = zoom in."""
        self.fov -= scroll_amount * self.zoom_speed
        self.fov = max(self.fov_min, min(self.fov_max, self.fov))

    def process_mouse(self, rel_x, rel_y):
        """rel_x/rel_y vêm de pygame.mouse.get_rel(), em pixels desde o último frame."""
        self.yaw += rel_x * self.mouse_sensitivity
        self.pitch -= rel_y * self.mouse_sensitivity
        self.pitch = max(-89.0, min(89.0, self.pitch))

    def _base_forward_vector(self):
        """Vetor de direção puro (sem shake) para movimentação do jogador no plano."""
        yaw_rad = math.radians(self.yaw)
        pitch_rad = math.radians(self.pitch)
        fx = math.cos(yaw_rad) * math.cos(pitch_rad)
        fy = math.sin(pitch_rad)
        fz = math.sin(yaw_rad) * math.cos(pitch_rad)
        return fx, fy, fz

    def process_keyboard(self, dt):
        """
        W = frente, A = esquerda, D = direita, S = desce.
        (Shift acelera.)
        """
        keys = pygame.key.get_pressed()
        fx, fy, fz = self._base_forward_vector()

        # vetor "direita", perpendicular ao forward e ao "up" mundial (0,1,0)
        right_x, right_z = fz, -fx
        length = math.hypot(right_x, right_z) or 1.0
        right_x, right_z = right_x / length, right_z / length

        speed = self.move_speed
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            speed *= self.sprint_multiplier
        step = speed * dt

        if keys[pygame.K_w]:
            self.x += fx * step
            self.y += fy * step
            self.z += fz * step
        if keys[pygame.K_d]:
            self.x += right_x * step
            self.z += right_z * step
        if keys[pygame.K_a]:
            self.x -= right_x * step
            self.z -= right_z * step
        if keys[pygame.K_s]:
            self.y -= step

    def _get_camera_vectors(self):
        """Calcula eye, target e up com offsets de shake aplicados."""
        eff_yaw = self.yaw + self._shake_yaw
        eff_pitch = max(-89.0, min(89.0, self.pitch + self._shake_pitch))

        yaw_rad = math.radians(eff_yaw)
        pitch_rad = math.radians(eff_pitch)
        fx = math.cos(yaw_rad) * math.cos(pitch_rad)
        fy = math.sin(pitch_rad)
        fz = math.sin(yaw_rad) * math.cos(pitch_rad)
        forward = np.array([fx, fy, fz], dtype=np.float32)
        norm = np.linalg.norm(forward)
        if norm > 0:
            forward /= norm

        eye = np.array([
            self.x + self._shake_pos[0],
            self.y + self._shake_pos[1],
            self.z + self._shake_pos[2],
        ], dtype=np.float32)

        target = eye + forward

        # Vetores de orientação com Roll do tremor
        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        side = np.cross(forward, world_up)
        norm_s = np.linalg.norm(side)
        if norm_s > 0:
            side /= norm_s
        else:
            side = np.array([1.0, 0.0, 0.0], dtype=np.float32)

        base_up = np.cross(side, forward)
        norm_u = np.linalg.norm(base_up)
        if norm_u > 0:
            base_up /= norm_u

        if abs(self._shake_roll) > 0.001:
            roll_rad = math.radians(self._shake_roll)
            cr, sr = math.cos(roll_rad), math.sin(roll_rad)
            up = base_up * cr + side * sr
        else:
            up = base_up

        return eye, target, up

    def get_view_matrix(self) -> np.ndarray:
        """Retorna matriz de visualização 4x4 para Shaders GLSL."""
        eye, target, up = self._get_camera_vectors()
        return look_at(eye, target, up)

    def apply(self):
        """Aplica gluLookAt diretamente no pipeline fixo (modo de compatibilidade)."""
        eye, target, up = self._get_camera_vectors()
        gluLookAt(
            eye[0], eye[1], eye[2],
            target[0], target[1], target[2],
            up[0], up[1], up[2]
        )
