"""
SeismicPyGL: Simulador 3D de terremotos em Python + PyOpenGL + GLSL 3.3 Core.
Arquitetura Modular:
- src.core: Câmera, shaders, malhas VBO/VAO, PBR loaders e matemática 3D
- src.rendering: Passes de sombra, céu panorâmico HDRI 360 e HUD 2D
- src.simulation: Ondas sísmicas mecânicas e sistema de partículas GPU
- src.world: Entidades do cenário (Terreno, Edifícios, Casas, Ruas, Postes, Árvores, Montanha)
"""

from . import core
from . import rendering
from . import simulation
from . import world

__version__ = "2.0.0"
__all__ = ["core", "rendering", "simulation", "world"]
