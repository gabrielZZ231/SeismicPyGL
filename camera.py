"""
Câmera livre 3D estilo primeira pessoa com suporte a:
- Movimentação livre corrigida (WASD, Shift sprint, S navega para trás, A esquerda, D direita)
- Rotação via mouse suave com interpolação exponencial (Euler angles: Pitch e Yaw)
- Centralização inicial mirando no centro da vila (0, 0)
- Zoom via FOV dinâmico (Mouse Wheel)
- Sistema de Trauma & Screen Shake com Ruído de Perlin (Pitch, Yaw, Roll e Translação)
- Matriz de visualização 4x4 (get_view_matrix) para Shaders GLSL modernos
- Compatibilidade com gluLookAt (apply)
"""

import os
import sys
if sys.platform.startswith("linux") and "PYOPENGL_PLATFORM" not in os.environ:
    os.environ["PYOPENGL_PLATFORM"] = "glx"

import math
import numpy as np
import pygame
from OpenGL.GLU import gluLookAt
from math_utils import look_at, perlin1d


class FreeCamera:
    def __init__(self, position=(0.0, 5.0, 36.0), yaw=-90.0, pitch=-7.0,
                 move_speed=15.0, sprint_multiplier=3.0, mouse_sensitivity=0.10,
                 fov=55.0, zoom_speed=3.0, fov_min=20.0, fov_max=90.0):
        self.x, self.y, self.z = position
        self.yaw = yaw       # graus; -90 aponta para -Z (olhando para o centro da vila em 0,0)
        self.pitch = pitch   # graus; ligeiramente inclinado para baixo
        self._initial_pose = (0.0, 5.0, 36.0, -90.0, -7.0)
        self.move_speed = move_speed
        self.sprint_multiplier = sprint_multiplier
        self.mouse_sensitivity = mouse_sensitivity
        self.eye_height = 2.5
        self.world_bounds = 68.0

        # Suavização (smoothing) do mouse para eliminar tremores de delta bruto
        self._smooth_yaw_vel = 0.0
        self._smooth_pitch_vel = 0.0
        self.smooth_alpha = 0.40

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

    def reset_view(self):
        """Volta a câmera para o enquadramento inicial centralizado e remove o tremor."""
        self.x, self.y, self.z, self.yaw, self.pitch = self._initial_pose
        self.trauma = 0.0
        self._shake_yaw = self._shake_pitch = self._shake_roll = 0.0
        self._shake_pos = (0.0, 0.0, 0.0)
        self._smooth_yaw_vel = 0.0
        self._smooth_pitch_vel = 0.0

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
        """
        Atualiza ângulos da câmera a partir do delta do mouse.
        Aplica filtro leve anti-jitter sem introduzir inércia.
        """
        # Ignora deltas anômalos ao capturar/soltar foco da janela
        if abs(rel_x) > 250 or abs(rel_y) > 250:
            return

        # Aplica o delta diretamente — sem acúmulo de velocidade/inércia
        dx = rel_x * self.mouse_sensitivity
        dy = rel_y * self.mouse_sensitivity

        self.yaw += dx
        self.pitch -= dy
        self.pitch = max(-84.0, min(84.0, self.pitch))

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
        W = frente, S = trás, A = esquerda, D = direita.
        (Shift acelera.)
        Vetor lateral corrigido para que D vá para a direita e A para a esquerda.
        """
        keys = pygame.key.get_pressed()
        yaw_rad = math.radians(self.yaw)
        fx, fz = math.cos(yaw_rad), math.sin(yaw_rad)

        # Vetor "direita" matematicamente correto: perpendicular ao vetor forward e ao UP (0,1,0)
        # Se forward = (fx, 0, fz), direita = (-fz, 0, fx)
        right_x, right_z = -fz, fx
        length = math.hypot(right_x, right_z) or 1.0
        right_x, right_z = right_x / length, right_z / length

        speed = self.move_speed
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            speed *= self.sprint_multiplier
        step = speed * dt

        move_x = move_z = 0.0
        if keys[pygame.K_w]:
            move_x += fx
            move_z += fz
        if keys[pygame.K_s]:
            move_x -= fx
            move_z -= fz
        if keys[pygame.K_d]:
            move_x += right_x
            move_z += right_z
        if keys[pygame.K_a]:
            move_x -= right_x
            move_z -= right_z

        move_len = math.hypot(move_x, move_z)
        if move_len > 0.0:
            move_x /= move_len
            move_z /= move_len
            self.x += move_x * step
            self.z += move_z * step

        # Mantém a câmera dentro da área do mapa e acima do nível do solo
        self.x = max(-self.world_bounds, min(self.world_bounds, self.x))
        self.z = max(-self.world_bounds, min(self.world_bounds, self.z))
        self.y = max(self.eye_height, self.y)

    def _get_camera_vectors(self):
        """Calcula eye, target e up com offsets de shake aplicados."""
        eff_yaw = self.yaw + self._shake_yaw
        eff_pitch = max(-84.0, min(84.0, self.pitch + self._shake_pitch))

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
            max(self.eye_height, self.y + self._shake_pos[1]),
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
