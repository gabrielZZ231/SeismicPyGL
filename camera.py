"""
Câmera livre estilo "jogo em primeira pessoa": WASD move, mouse olha
ao redor. Guarda posição (x, y, z) e dois ângulos (yaw = giro
horizontal, pitch = giro vertical) e monta a matriz de visualização
a partir disso.
"""
 
import math
import pygame
from OpenGL.GLU import gluLookAt
 
 
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
        self.fov_min = fov_min       # mais "zoom in" (visão mais fechada)
        self.fov_max = fov_max       # mais "zoom out" (visão mais aberta)
 
    def zoom(self, scroll_amount):
        """scroll_amount vem de event.y do MOUSEWHEEL: positivo = zoom in."""
        self.fov -= scroll_amount * self.zoom_speed
        self.fov = max(self.fov_min, min(self.fov_max, self.fov))
 
    def process_mouse(self, rel_x, rel_y):
        """rel_x/rel_y vêm de pygame.mouse.get_rel(), em pixels desde o último frame."""
        self.yaw += rel_x * self.mouse_sensitivity
        self.pitch -= rel_y * self.mouse_sensitivity
        self.pitch = max(-89.0, min(89.0, self.pitch))
 
    def _forward_vector(self):
        yaw_rad = math.radians(self.yaw)
        pitch_rad = math.radians(self.pitch)
        fx = math.cos(yaw_rad) * math.cos(pitch_rad)
        fy = math.sin(pitch_rad)
        fz = math.sin(yaw_rad) * math.cos(pitch_rad)
        return fx, fy, fz
 
    def process_keyboard(self, dt):
        """
        W = frente, A = esquerda, D = direita, S = desce.
        (Não há "trás" dedicado: gire com o mouse e use W para seguir
        em frente na nova direção. Shift acelera.)
        """
        keys = pygame.key.get_pressed()
        fx, fy, fz = self._forward_vector()
 
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
 
    def apply(self):
        fx, fy, fz = self._forward_vector()
        gluLookAt(
            self.x, self.y, self.z,
            self.x + fx, self.y + fy, self.z + fz,
            0.0, 1.0, 0.0
        )
 