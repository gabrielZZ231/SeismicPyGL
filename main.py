"""
SeismicPyGL — Simulador 3D de Terremotos em Python com Pygame e PyOpenGL.
Pipeline programável moderno (GLSL 3.3 Core):
- Câmera em primeira pessoa com Trauma Screen Shake via Ruído de Perlin
- Deformação sísmica circular calculada diretamente na GPU (ground.vert)
- Colapso dinâmico de edifícios (afundamento Y, rotação e escombros)
- Sistema de partículas para fumaça/poeira com Billboarding e Alpha Blending
- Iluminação direcional (Phong / produto escalar) e texturas via VBO/VAO
- HUD 2D ortográfico isolado do Depth Test com Escala Richter e FPS estável a 60 FPS
"""

import os
import sys

# Garante compatibilidade do PyOpenGL no Linux / X11 / Windows / macOS
if sys.platform.startswith("linux") and "PYOPENGL_PLATFORM" not in os.environ:
    os.environ["PYOPENGL_PLATFORM"] = "glx"

import pygame
from pygame.locals import (
    DOUBLEBUF, OPENGL, QUIT, KEYDOWN, K_ESCAPE, K_SPACE,
    K_1, K_2, K_3, K_4, K_5, K_r, MOUSEWHEEL,
)
from OpenGL.GL import (
    glEnable, glClearColor, glClear, glBindTexture,
    GL_DEPTH_TEST, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_TEXTURE_2D,
)

from math_utils import perspective
from camera import FreeCamera
from earthquake import EarthquakeSimulator
from scene import (
    Ground, generate_village, Mountain, generate_forest,
    get_concrete_texture, Street
)
from particles import ParticleSystem
from hud import HUD
from shader import ShaderProgram, check_gl_error
from texture import cleanup_textures

WINDOW_SIZE = (1000, 700)
ASPECT_RATIO = WINDOW_SIZE[0] / WINDOW_SIZE[1]


def init_opengl():
    glEnable(GL_DEPTH_TEST)
    glClearColor(0.62, 0.78, 0.94, 1.0)  # Cor de céu aberto
    check_gl_error("init_opengl")


def main():
    pygame.init()
    pygame.display.set_mode(WINDOW_SIZE, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("SeismicPyGL — Simulador 3D de Terremotos (GLSL)")

    # Captura o cursor do mouse para visão em primeira pessoa
    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)
    pygame.mouse.get_rel()

    init_opengl()

    clock = pygame.time.Clock()
    
    # Enquadra o centro da vila já no primeiro frame.
    camera = FreeCamera(position=(0.0, 5.0, 36.0), yaw=-90.0, pitch=-7.0,
                        mouse_sensitivity=0.028)

    # Entidades do mundo 3D
    earthquake = EarthquakeSimulator()
    ground = Ground(size=140.0, divisions=80)
    
    buildings, houses, streets = generate_village(center=(0.0, 0.0), building_count=9, house_count=24)
    all_buildings = buildings + houses

    mountain_center = (48.0, 48.0)
    mountain = Mountain(x=mountain_center[0], z=mountain_center[1], base_radius=14.0, height=26.0)
    forest = generate_forest(
        count=80,
        center=(0.0, 0.0),
        radius_range=(18.0, 55.0),
        avoid_zones=[(0.0, 0.0, 16.0), (48.0, 48.0, 16.0)]
    )

    # Shaders e Sistemas de Efeitos
    scene_shader = ShaderProgram.from_files(
        "assets/shaders/scene.vert",
        "assets/shaders/scene.frag"
    )
    concrete_tex = get_concrete_texture()
    particle_system = ParticleSystem(max_particles=6000)
    hud = HUD(WINDOW_SIZE[0], WINDOW_SIZE[1])

    # Mapeamento de magnitudes Richter e trauma para as teclas 1 a 5
    magnitudes = {K_1: 3.0, K_2: 4.5, K_3: 6.0, K_4: 7.2, K_5: 8.5}
    trauma_map = {K_1: 0.25, K_2: 0.45, K_3: 0.65, K_4: 0.95, K_5: 1.0}

    running = True
    elapsed_time = 0.0
    first_frame = True

    while running:
        dt = clock.tick(60) / 1000.0
        # Limita dt anômalo para estabilidade numérica
        dt = min(dt, 0.05)
        elapsed_time += dt

        # -------------------------------------------------------------------
        # Processamento de Eventos e Teclado
        # -------------------------------------------------------------------
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running = False

                elif event.key == K_SPACE:
                    # Terremoto aleatório com intensidade moderada
                    earthquake.trigger(current_time=elapsed_time, magnitude=5.5)
                    camera.add_trauma(0.70)

                elif event.key in magnitudes:
                    # Teclas 1 a 5: magnitudes da Escala Richter calibradas
                    mag = magnitudes[event.key]
                    t_amt = trauma_map[event.key]
                    earthquake.trigger(current_time=elapsed_time, magnitude=mag)
                    camera.add_trauma(t_amt)

                elif event.key == K_r:
                    # Reset geral do cenário
                    for b in all_buildings:
                        b.reset()
                    for tree in forest:
                        tree.reset()
                    mountain.debris.clear()
                    earthquake.stop()
                    camera.reset_view()

            elif event.type == MOUSEWHEEL:
                camera.zoom(event.y)

        # Atualização da Câmera (movimento e screen shake)
        rel_x, rel_y = pygame.mouse.get_rel()
        if first_frame:
            first_frame = False
        else:
            camera.process_mouse(rel_x, rel_y)
            
        camera.process_keyboard(dt)
        camera.update_trauma(dt)

        # Atualização física dos objetos
        for b in all_buildings:
            b.update(earthquake, elapsed_time, dt, particle_system=particle_system)
        for tree in forest:
            tree.update(earthquake, elapsed_time, dt)
        mountain.update(earthquake, elapsed_time, dt)
        particle_system.update(dt)

        # -------------------------------------------------------------------
        # Renderização 3D (Pipeline Programável)
        # -------------------------------------------------------------------
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        view_matrix = camera.get_view_matrix()
        proj_matrix = perspective(camera.fov, ASPECT_RATIO, 0.1, 1000.0)

        # 1. Chão deformável com onda sísmica na GPU
        ground.draw(earthquake, elapsed_time, view_matrix, proj_matrix)

        # 2. Objetos da Cena (Prédios, Casas, Montanha, Árvores) com Iluminação Phong
        scene_shader.use()
        scene_shader.set_uniform_mat4("u_view", view_matrix)
        scene_shader.set_uniform_mat4("u_projection", proj_matrix)
        scene_shader.set_uniform_vec3("u_light_direction", (-0.4, -1.0, -0.3))
        scene_shader.set_uniform_vec3("u_light_color", (1.0, 0.98, 0.92))
        scene_shader.set_uniform_vec3("u_ambient_color", (0.35, 0.38, 0.42))

        # Ruas (asfalto)
        scene_shader.set_uniform_int("u_use_texture", 1)
        scene_shader.set_uniform_int("u_building_facade", 0)
        scene_shader.set_uniform_int("u_texture", 0)
        for s in streets:
            s.draw(scene_shader)

        # Prédios e Casas (com textura de concreto para prédios, mas usaremos para ambos para simplificar a draw call base)
        scene_shader.set_uniform_int("u_use_texture", 1)
        scene_shader.set_uniform_int("u_building_facade", 1)
        scene_shader.set_uniform_int("u_texture", 0)
        glBindTexture(GL_TEXTURE_2D, concrete_tex)
        for b in all_buildings:
            b.draw(scene_shader, earthquake, elapsed_time)

        # Montanha e destroços
        scene_shader.set_uniform_int("u_use_texture", 0)
        scene_shader.set_uniform_int("u_building_facade", 0)
        scene_shader.set_uniform_int("u_mountain_stratum", 1)
        mountain.draw(scene_shader)
        scene_shader.set_uniform_int("u_mountain_stratum", 0)

        # Floresta / Árvores
        for tree in forest:
            tree.draw(scene_shader, earthquake, elapsed_time)

        scene_shader.stop()
        glBindTexture(GL_TEXTURE_2D, 0)

        # 3. Partículas de fumaça e poeira com Billboards e Alpha Blending
        particle_system.draw(view_matrix, proj_matrix)

        # 4. HUD 2D com isolamento de profundidade
        hud.draw(
            WINDOW_SIZE[0], WINDOW_SIZE[1],
            earthquake=earthquake,
            camera=camera,
            buildings=buildings,
            houses=houses,
            fps=clock.get_fps()
        )

        pygame.display.flip()

    # -----------------------------------------------------------------------
    # Finalização e Limpeza de Memória GPU
    # -----------------------------------------------------------------------
    ground.cleanup()
    # Limpeza dos prédios/casas, desnecessário para ruas
    for b in all_buildings:
        if hasattr(b, "cleanup"):
            b.cleanup()
    mountain.cleanup()
    particle_system.cleanup()
    hud.cleanup()
    scene_shader.cleanup()
    cleanup_textures()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
