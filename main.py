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

# Força o uso da placa de vídeo dedicada NVIDIA GeForce RTX 2050 via Mesa D3D12/WSL
if sys.platform.startswith("linux"):
    if "GALLIUM_DRIVER" not in os.environ:
        os.environ["GALLIUM_DRIVER"] = "d3d12"
    if "MESA_D3D12_DEFAULT_ADAPTER_NAME" not in os.environ:
        os.environ["MESA_D3D12_DEFAULT_ADAPTER_NAME"] = "NVIDIA"
    if "PYOPENGL_PLATFORM" not in os.environ:
        os.environ["PYOPENGL_PLATFORM"] = "glx"
    if "/usr/lib/wsl/lib" not in os.environ.get("LD_LIBRARY_PATH", ""):
        os.environ["LD_LIBRARY_PATH"] = "/usr/lib/wsl/lib:" + os.environ.get("LD_LIBRARY_PATH", "")

import pygame
from pygame.locals import (
    DOUBLEBUF, OPENGL, QUIT, KEYDOWN, K_ESCAPE, K_SPACE,
    K_1, K_2, K_3, K_4, K_5, K_r, MOUSEWHEEL,
)
from OpenGL.GL import (
    glEnable, glClearColor, glClear, glBindTexture, glActiveTexture, glGetString,
    GL_DEPTH_TEST, GL_MULTISAMPLE, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_TEXTURE_2D,
    GL_TEXTURE0, GL_TEXTURE1, GL_TEXTURE6, GL_RENDERER, GL_VENDOR, GL_VERSION,
)

from src.core import (
    perspective, look_at, ortho, FreeCamera,
    ShaderProgram, check_gl_error, cleanup_textures
)
from src.simulation import EarthquakeSimulator, ParticleSystem
from src.rendering import ShadowMap, Sky, HUD
from src.world import (
    Ground, generate_village, Mountain, generate_forest,
    get_concrete_texture, Street
)

# 4K é opcional para não sacrificar 60 FPS em monitores/GPUs menores.
# Ex.: SEISMICPYGL_RESOLUTION=4k python main.py
_resolution = os.environ.get("SEISMICPYGL_RESOLUTION", "1080p").lower()
WINDOW_SIZE = (3840, 2160) if _resolution in {"4k", "2160p", "3840x2160"} else (1920, 1080)
ASPECT_RATIO = WINDOW_SIZE[0] / WINDOW_SIZE[1]


def init_opengl():
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_MULTISAMPLE)
    glClearColor(0.62, 0.78, 0.94, 1.0)  # Cor de céu aberto
    check_gl_error("init_opengl")


def main():
    pygame.init()
    # A GPU faz a suavização das bordas; é barato e melhora bastante a leitura
    # das silhuetas sem precisar aumentar a quantidade de objetos da cena.
    pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 4)
    pygame.display.set_mode(WINDOW_SIZE, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("SeismicPyGL — Simulador 3D de Terremotos (GLSL)")

    # Captura o cursor do mouse para visão em primeira pessoa
    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)
    pygame.mouse.get_rel()

    init_opengl()

    try:
        renderer = glGetString(GL_RENDERER).decode()
        vendor = glGetString(GL_VENDOR).decode()
        version = glGetString(GL_VERSION).decode()
        print(f"[Hardware 3D] GPU:    {renderer}")
        print(f"[Hardware 3D] Vendor: {vendor}")
        print(f"[Hardware 3D] Driver: {version}")
    except Exception as e:
        print(f"[Hardware 3D] Info GPU: {e}")

    clock = pygame.time.Clock()
    
    # Enquadra o centro da vila já no primeiro frame.
    camera = FreeCamera(position=(0.0, 5.0, 36.0), yaw=-90.0, pitch=-7.0)

    # Entidades do mundo 3D
    earthquake = EarthquakeSimulator()
    # Grade mais densa: a deformação continua inteiramente no vertex shader.
    ground = Ground(size=140.0, divisions=220)
    
    buildings, houses, streets, lamp_posts = generate_village(center=(0.0, 0.0), building_count=9, house_count=24)
    all_buildings = buildings + houses

    mountain_center = (48.0, 48.0)
    mountain = Mountain(
        x=mountain_center[0], z=mountain_center[1], base_radius=14.0,
        height=26.0, bands=20, slices=72,
    )
    forest = generate_forest(
        count=120,
        center=(0.0, 0.0),
        radius_range=(18.0, 55.0),
        avoid_zones=[(0.0, 0.0, 16.0), (48.0, 48.0, 16.0)],
        avoid_buildings=all_buildings,
        avoid_streets=streets,
    )

    # Shaders e Sistemas de Efeitos
    scene_shader = ShaderProgram.from_files(
        "assets/shaders/scene.vert",
        "assets/shaders/scene.frag"
    )
    particle_system = ParticleSystem(max_particles=6000)
    hud = HUD(WINDOW_SIZE[0], WINDOW_SIZE[1])
    shadow_map = ShadowMap(size=1024)
    sky = Sky()

    # Luz direcional estável para a depth map: uma única passagem extra por frame.
    light_view = look_at((42.0, 65.0, 36.0), (0.0, 0.0, 0.0))
    light_projection = ortho(-72.0, 72.0, -72.0, 72.0, 1.0, 150.0)
    light_space_matrix = light_projection @ light_view

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
                    for lp in lamp_posts:
                        lp.reset()
                    mountain.debris.clear()
                    earthquake.reset()
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
        for lp in lamp_posts:
            lp.update(earthquake, elapsed_time, dt, particle_system=particle_system)
        mountain.update(earthquake, elapsed_time, dt)
        particle_system.update(dt)
        if not earthquake.active:
            particle_system.emit_ambient((camera.x, camera.y, camera.z), forest, dt)

        # -------------------------------------------------------------------
        # Renderização 3D (Pipeline Programável)
        # -------------------------------------------------------------------
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        view_matrix = camera.get_view_matrix()
        proj_matrix = perspective(camera.fov, ASPECT_RATIO, 0.1, 1000.0)

        # Passagem de profundidade: objetos estáticos/dinâmicos projetam sombra.
        shadow_map.begin(light_space_matrix)
        for s in streets:
            s.draw(shadow_map.shader, earthquake, elapsed_time)
        for b in all_buildings:
            b.draw(shadow_map.shader, earthquake, elapsed_time)
        mountain.draw(shadow_map.shader)
        for tree in forest:
            tree.draw(shadow_map.shader, earthquake, elapsed_time)
        for lp in lamp_posts:
            lp.draw(shadow_map.shader, earthquake, elapsed_time)
        shadow_map.end(*WINDOW_SIZE)

        sky.draw(view_matrix, proj_matrix, elapsed_time)

        # 1. Chão deformável com onda sísmica na GPU e texturas PBR (sparse_grass + cracked_concrete_02)
        ground.draw(earthquake, elapsed_time, view_matrix, proj_matrix, light_space_matrix,
                    shadow_map.texture, all_buildings, camera=camera)

        # 2. Objetos da Cena (Prédios, Casas, Montanha, Árvores, Postes, Ruas) com PBR completo
        scene_shader.use()
        scene_shader.set_uniform_mat4("u_view", view_matrix)
        scene_shader.set_uniform_mat4("u_projection", proj_matrix)
        scene_shader.set_uniform_mat4("u_light_space_matrix", light_space_matrix)
        scene_shader.set_uniform_vec3("u_light_direction", (-0.4, -1.0, -0.3))
        scene_shader.set_uniform_vec3("u_light_color", (1.0, 0.98, 0.92))
        scene_shader.set_uniform_vec3("u_ambient_color", (0.35, 0.38, 0.42))
        scene_shader.set_uniform_vec3("u_view_pos", (camera.x, camera.y, camera.z))

        glActiveTexture(GL_TEXTURE6)
        glBindTexture(GL_TEXTURE_2D, shadow_map.texture)
        scene_shader.set_uniform_int("u_shadow_map", 6)
        glActiveTexture(GL_TEXTURE0)

        crack_intensity = earthquake.get_crack_intensity()
        scene_shader.set_uniform_float("u_crack_intensity", crack_intensity)
        scene_shader.set_uniform_vec2("u_epicenter", earthquake.epicenter)
        scene_shader.set_uniform_float("u_spatial_falloff", earthquake.spatial_falloff)

        # Ruas (asfalto PBR clean_asphalt com placas ondulantes)
        for s in streets:
            s.draw(scene_shader, earthquake, elapsed_time)
        scene_shader.set_uniform_int("u_is_street", 0)

        # Postes de iluminação pública (PBR metal_plate_02)
        for lp in lamp_posts:
            lp.draw(scene_shader, earthquake, elapsed_time)

        # Prédios e Casas (PBR red_brick / damaged_plaster com crossfade para broken_brick_wall / cracked_concrete_02)
        for b in all_buildings:
            b.draw(scene_shader, earthquake, elapsed_time)

        # Montanha e destroços de rocha (PBR rocky_terrain_02)
        scene_shader.set_uniform_int("u_mountain_stratum", 1)
        mountain.draw(scene_shader)
        scene_shader.set_uniform_int("u_mountain_stratum", 0)

        # Floresta / Árvores (tronco procedural + dry_river_pebbles sob raízes caídas)
        for tree in forest:
            tree.draw(scene_shader, earthquake, elapsed_time)

        scene_shader.stop()
        glActiveTexture(GL_TEXTURE0)
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
            fps=clock.get_fps(),
            lamp_posts=lamp_posts
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
    shadow_map.cleanup()
    sky.cleanup()
    scene_shader.cleanup()
    cleanup_textures()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
