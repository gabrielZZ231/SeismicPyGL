"""
HUD 2D para exibição de métricas do simulador SeismicPyGL:
- Escala Richter e magnitude do terremoto
- Nível de Trauma da câmera e vibração
- Status da simulação (Repouso, Ativo, Colapso)
- Taxa de quadros por segundo (FPS)
- Prédios intactos e colapsados
- Guia de controles interativos na tela
Renderizado via projeção ortográfica 2D dedicada e isolamento de profundidade (Issue #18).
"""

import math
import numpy as np
import pygame
from OpenGL.GL import (
    glEnable, glDisable, glBlendFunc, glDepthMask,
    glGenTextures, glBindTexture, glTexImage2D, glTexParameteri,
    glDeleteTextures,
    GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER, GL_LINEAR,
    GL_BLEND, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    GL_DEPTH_TEST,
)
from shader import ShaderProgram
from math_utils import ortho, translate, scale
from mesh import Mesh


class TextTexture:
    """Gerencia a textura OpenGL de uma string renderizada pelo pygame.font."""
    def __init__(self, font: pygame.font.Font, text: str, color=(255, 255, 255, 255)):
        self.font = font
        self.text = text
        self.color = color
        self.tex_id = None
        self.width = 0
        self.height = 0
        self._update(text, color)

    def _update(self, text: str, color):
        self.text = text
        self.color = color
        surf = self.font.render(text, True, color[:3])
        self.width = surf.get_width()
        self.height = surf.get_height()

        # Converte superfície para formato RGBA do OpenGL
        data = pygame.image.tostring(surf, "RGBA", True)

        if self.tex_id is None:
            self.tex_id = glGenTextures(1)

        glBindTexture(GL_TEXTURE_2D, self.tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.width, self.height, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, data)
        glBindTexture(GL_TEXTURE_2D, 0)

    def set_text(self, text: str, color=None):
        if color is None:
            color = self.color
        if text != self.text or color != self.color:
            self._update(text, color)

    def cleanup(self):
        if self.tex_id is not None:
            glDeleteTextures([self.tex_id])
            self.tex_id = None


class HUD:
    def __init__(self, width=1000, height=700):
        self.screen_width = width
        self.screen_height = height

        if not pygame.font.get_init():
            pygame.font.init()

        # Fontes
        self.title_font = pygame.font.SysFont("Consolas", 20, bold=True)
        self.body_font = pygame.font.SysFont("Consolas", 15, bold=False)
        self.controls_font = pygame.font.SysFont("Consolas", 13, bold=False)

        # Shader ortográfico 2D
        self.shader = ShaderProgram.from_files(
            "assets/shaders/hud.vert",
            "assets/shaders/hud.frag"
        )

        # Malha unitária 2D [0, 1] x [0, 1] para renderizar retângulos/textos
        verts = np.array([
            0.0, 0.0, 0.0,  0.0, 1.0,  0.0, 0.0, 1.0,
            1.0, 0.0, 0.0,  1.0, 1.0,  0.0, 0.0, 1.0,
            1.0, 1.0, 0.0,  1.0, 0.0,  0.0, 0.0, 1.0,

            0.0, 0.0, 0.0,  0.0, 1.0,  0.0, 0.0, 1.0,
            1.0, 1.0, 0.0,  1.0, 0.0,  0.0, 0.0, 1.0,
            0.0, 1.0, 0.0,  0.0, 0.0,  0.0, 0.0, 1.0,
        ], dtype=np.float32)
        self.unit_quad = Mesh(verts, 6, stride=32)

        # Textura 1x1 branca para fundos/barras sólidas
        self.white_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.white_tex)
        white_data = b"\xff\xff\xff\xff"
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 1, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, white_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glBindTexture(GL_TEXTURE_2D, 0)

        # Cache de rótulos de texto
        self._labels = {}

    def _get_label(self, key: str, font: pygame.font.Font, initial_text: str, color=(255, 255, 255, 255)) -> TextTexture:
        if key not in self._labels:
            self._labels[key] = TextTexture(font, initial_text, color)
        return self._labels[key]

    def _draw_quad(self, x: float, y: float, w: float, h: float, tex_id: int, color=(1.0, 1.0, 1.0, 1.0)):
        """Desenha um retângulo texturizado na tela em pixels."""
        model = translate(x, y, 0.0) @ scale(w, h, 1.0)
        self.shader.set_uniform_mat4("u_model", model)
        self.shader.set_uniform_vec4("u_color", color)

        glBindTexture(GL_TEXTURE_2D, tex_id)
        self.unit_quad.draw()

    def draw(self, screen_width: int, screen_height: int, earthquake, camera, buildings, houses, fps: float):
        """
        Renderiza o HUD 2D completo com isolamento de profundidade.
        """
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Issue #18: Isolamento do teste de profundidade para o HUD não ser engolido pelo 3D
        glDisable(GL_DEPTH_TEST)
        glDepthMask(False)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self.shader.use()
        # Matriz ortográfica: (0,0) no canto superior esquerdo, (W, H) no canto inferior direito
        proj = ortho(0.0, float(screen_width), float(screen_height), 0.0, -1.0, 1.0)
        self.shader.set_uniform_mat4("u_projection", proj)
        self.shader.set_uniform_int("u_texture", 0)

        # 1. Painel Superior Esquerdo: Informações Sísmicas e Métricas
        panel_w = 340
        panel_h = 195
        self._draw_quad(15, 15, panel_w, panel_h, self.white_tex, (0.05, 0.08, 0.12, 0.78))

        # Borda sutil do painel
        self._draw_quad(15, 15, panel_w, 2, self.white_tex, (0.2, 0.5, 0.9, 0.8))

        # Título
        lbl_title = self._get_label("title", self.title_font, "SeismicPyGL — Simulador 3D", (100, 210, 255))
        self._draw_quad(25, 22, lbl_title.width, lbl_title.height, lbl_title.tex_id)

        # Status do Terremoto
        if earthquake.active:
            status_text = f"● TERREMOTO ATIVO (Mag {earthquake.richter_magnitude:.1f} Richter)"
            status_color = (255, 75, 75)
        else:
            status_text = "○ EM REPOUSO (Sem atividade sísmica)"
            status_color = (120, 230, 140)
        lbl_status = self._get_label("status", self.body_font, status_text, status_color)
        lbl_status.set_text(status_text, status_color)
        self._draw_quad(25, 50, lbl_status.width, lbl_status.height, lbl_status.tex_id)

        # Barra de Trauma da Câmera
        trauma_val = camera.trauma
        trauma_text = f"Trauma Câmera: {trauma_val:.2f} (Shake: {trauma_val**3:.2f})"
        lbl_trauma = self._get_label("trauma", self.body_font, trauma_text, (240, 240, 240))
        lbl_trauma.set_text(trauma_text)
        self._draw_quad(25, 72, lbl_trauma.width, lbl_trauma.height, lbl_trauma.tex_id)

        # Fundo da barra de trauma
        bar_x = 25
        bar_y = 93
        bar_w = 310
        bar_h = 10
        self._draw_quad(bar_x, bar_y, bar_w, bar_h, self.white_tex, (0.2, 0.2, 0.2, 0.8))
        # Preenchimento da barra (verde -> amarelo -> vermelho conforme sobe)
        fill_w = max(0.0, min(bar_w, bar_w * trauma_val))
        if trauma_val > 0.005:
            bar_col = (
                min(1.0, trauma_val * 1.5),
                max(0.0, 1.0 - trauma_val * 0.8),
                0.1,
                0.95
            )
            self._draw_quad(bar_x, bar_y, fill_w, bar_h, self.white_tex, bar_col)

        # Contagem de Prédios
        total_b = len(buildings)
        collapsed_b = sum(1 for b in buildings if b.collapse_progress >= 0.95)
        intact_b = total_b - collapsed_b
        
        total_h = len(houses)
        collapsed_h = sum(1 for h in houses if h.collapse_progress >= 0.95)
        intact_h = total_h - collapsed_h
        
        b_text = f"Prédios: {intact_b}/{total_b} | Casas: {intact_h}/{total_h}"
        lbl_b = self._get_label("buildings", self.body_font, b_text, (200, 220, 240))
        lbl_b.set_text(b_text)
        self._draw_quad(25, 110, lbl_b.width, lbl_b.height, lbl_b.tex_id)

        # FPS e Motor
        fps_text = f"FPS: {fps:.0f}  |  Pipeline: GLSL 3.3 Core (VBO/VAO)"
        lbl_fps = self._get_label("fps", self.body_font, fps_text, (255, 215, 0) if fps < 55 else (140, 255, 140))
        lbl_fps.set_text(fps_text)
        self._draw_quad(25, 132, lbl_fps.width, lbl_fps.height, lbl_fps.tex_id)

        # 2. Painel Inferior: Guia de Controles
        ctrl_h = 44
        ctrl_w = 780
        ctrl_x = 15
        ctrl_y = screen_height - ctrl_h - 15
        self._draw_quad(ctrl_x, ctrl_y, ctrl_w, ctrl_h, self.white_tex, (0.05, 0.08, 0.12, 0.78))
        self._draw_quad(ctrl_x, ctrl_y, ctrl_w, 2, self.white_tex, (0.2, 0.5, 0.9, 0.8))

        c1 = "[W/A/S/D] Mover  [SHIFT] Correr  [MOUSE] Olhar livre  [SCROLL] Zoom FOV"
        lbl_c1 = self._get_label("ctrl1", self.controls_font, c1, (220, 220, 220))
        self._draw_quad(ctrl_x + 12, ctrl_y + 6, lbl_c1.width, lbl_c1.height, lbl_c1.tex_id)

        c2 = "[ESPAÇO] Terremoto aleatório   [1 a 5] Intensidades Richter (3.0 .. 8.5)   [R] Reset geral"
        lbl_c2 = self._get_label("ctrl2", self.controls_font, c2, (100, 220, 255))
        self._draw_quad(ctrl_x + 12, ctrl_y + 24, lbl_c2.width, lbl_c2.height, lbl_c2.tex_id)

        self.shader.stop()
        glBindTexture(GL_TEXTURE_2D, 0)

        # Restaura máquina de estados de profundidade para o próximo frame 3D
        glDepthMask(True)
        glEnable(GL_DEPTH_TEST)

    def cleanup(self):
        """Libera texturas e shader do HUD."""
        for lbl in self._labels.values():
            lbl.cleanup()
        self._labels.clear()

        if self.white_tex:
            glDeleteTextures([self.white_tex])
            self.white_tex = None
        if self.unit_quad:
            self.unit_quad.cleanup()
            self.unit_quad = None
        if self.shader:
            self.shader.cleanup()
            self.shader = None
