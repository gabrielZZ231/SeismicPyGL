"""
Simulador simples de terremoto com PyOpenGL.
 
Controles:
  W       -> anda para frente
  A       -> anda para a esquerda
  D       -> anda para a direita
  S       -> desce
  SHIFT   -> acelera (sprint)
  MOUSE   -> olha ao redor
  SCROLL  -> zoom (aproxima/afasta a "lente")
  ESPACO  -> dispara um terremoto em um epicentro aleatório
  ESC     -> sai do programa
 
Como rodar:
  pip install pygame PyOpenGL PyOpenGL_accelerate
  python main.py
"""
 
import sys
import pygame
from pygame.locals import (
    DOUBLEBUF, OPENGL, QUIT, KEYDOWN, K_ESCAPE, K_SPACE, MOUSEWHEEL,
)
from OpenGL.GL import (
    glEnable, glClearColor, glMatrixMode, glLoadIdentity, glClear,
    GL_DEPTH_TEST, GL_PROJECTION, GL_MODELVIEW,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
)
from OpenGL.GLU import gluPerspective
 
from camera import FreeCamera
from scene import Ground, generate_city, Mountain, generate_forest
from earthquake import EarthquakeSimulator
 
WINDOW_SIZE = (1000, 700)
ASPECT_RATIO = WINDOW_SIZE[0] / WINDOW_SIZE[1]
 
 
def init_opengl():
    glEnable(GL_DEPTH_TEST)
    glClearColor(0.65, 0.80, 0.95, 1.0)  # cor do céu
    glMatrixMode(GL_MODELVIEW)
 
 
def apply_projection(fov):
    """Recalcula a projeção com o FOV atual (muda quando o usuário dá zoom)."""
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(fov, ASPECT_RATIO, 0.1, 1000.0)
    glMatrixMode(GL_MODELVIEW)
 
 
def main():
    pygame.init()
    pygame.display.set_mode(WINDOW_SIZE, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Simulador de Terremoto - PyOpenGL")
 
    # prende o mouse na janela e esconde o cursor, pro "mouse look" funcionar
    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)
    pygame.mouse.get_rel()  # descarta o primeiro delta (costuma vir "sujo")
 
    init_opengl()
 
    clock = pygame.time.Clock()
    camera = FreeCamera()
    ground = Ground(size=100, divisions=30)
    buildings = generate_city(rows=5, cols=5, spacing=5.0)
 
    # montanha posicionada num canto do cenário, longe da cidade
    mountain_center = (32.0, 32.0)
    mountain = Mountain(x=mountain_center[0], z=mountain_center[1],
                         base_radius=12.0, height=22.0)
 
    # floresta em anel ao redor da montanha, sem invadir a área da cidade
    forest = generate_forest(
        count=45,
        center=mountain_center,
        radius_range=(13.0, 28.0),
        avoid_center=(0.0, 0.0),
        avoid_radius=16.0,
    )
 
    earthquake = EarthquakeSimulator()
 
    running = True
    elapsed_time = 0.0
 
    while running:
        dt = clock.tick(60) / 1000.0
        elapsed_time += dt
 
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running = False
                elif event.key == K_SPACE:
                    earthquake.trigger(current_time=elapsed_time)
            elif event.type == MOUSEWHEEL:
                camera.zoom(event.y)
 
        rel_x, rel_y = pygame.mouse.get_rel()
        camera.process_mouse(rel_x, rel_y)
        camera.process_keyboard(dt)
 
        # atualiza dano/colapso dos prédios e desmoronamento da montanha
        for building in buildings:
            building.update(earthquake, elapsed_time, dt)
        mountain.update(earthquake, elapsed_time, dt)
 
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        apply_projection(camera.fov)
        camera.apply()
 
        ground.draw(earthquake, elapsed_time)
        mountain.draw()
        for tree in forest:
            tree.draw(earthquake, elapsed_time)
        for building in buildings:
            building.draw(earthquake, elapsed_time)
 
        pygame.display.flip()
 
    pygame.quit()
    sys.exit()
 
 
if __name__ == "__main__":
    main()
 
 