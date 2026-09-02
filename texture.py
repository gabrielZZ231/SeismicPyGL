"""
Carregamento de texturas com PIL e upload para o OpenGL (glTexImage2D).
Inclui geradores procedurais de textura (concreto, grama, partículas de fumaça, etc.)
para garantir autonomia e evitar falhas por arquivos ausentes.
"""

import os
import math
import numpy as np
from PIL import Image
from OpenGL.GL import (
    glGenTextures, glBindTexture, glTexParameteri, glTexImage2D,
    glGenerateMipmap, glDeleteTextures,
    GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_REPEAT, GL_CLAMP_TO_EDGE,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
    GL_LINEAR, GL_LINEAR_MIPMAP_LINEAR,
)

_loaded_textures = []


def create_texture_from_image(img: Image.Image, wrap=GL_REPEAT) -> int:
    """Faz upload de um objeto PIL.Image para a GPU via glTexImage2D."""
    img = img.transpose(Image.FLIP_TOP_BOTTOM).convert("RGBA")
    width, height = img.size
    data = img.tobytes()

    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)

    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, wrap)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, wrap)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, data)
    glGenerateMipmap(GL_TEXTURE_2D)

    glBindTexture(GL_TEXTURE_2D, 0)
    _loaded_textures.append(tex_id)
    return tex_id


def load_texture(path: str, wrap=GL_REPEAT) -> int:
    """
    Carrega textura do disco com PIL.
    Se o arquivo não existir, gera textura procedural padrão correspondente.
    """
    if os.path.exists(path):
        img = Image.open(path)
        return create_texture_from_image(img, wrap)
    else:
        # Fallback procedural se não encontrar
        print(f"[Aviso] Textura '{path}' não encontrada. Gerando procedural correspondente.")
        basename = os.path.basename(path).lower()
        if "smoke" in basename or "particle" in basename:
            return create_smoke_particle_texture()
        elif "grass" in basename or "ground" in basename:
            return create_grass_texture()
        else:
            return create_concrete_texture()


def create_concrete_texture(size=128) -> int:
    """Gera textura procedural de concreto com ruído fino."""
    rng = np.random.default_rng(123)
    base = rng.integers(130, 160, (size, size), dtype=np.uint8)
    noise = rng.integers(-15, 16, (size, size), dtype=np.int16)
    concrete = np.clip(base + noise, 0, 255).astype(np.uint8)

    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[:, :, 0] = concrete
    rgba[:, :, 1] = concrete
    rgba[:, :, 2] = (concrete * 0.95).astype(np.uint8)
    rgba[:, :, 3] = 255

    img = Image.fromarray(rgba, "RGBA")
    return create_texture_from_image(img)


def create_grass_texture(size=128) -> int:
    """Gera textura procedural de terreno/grama."""
    rng = np.random.default_rng(456)
    green = rng.integers(80, 120, (size, size), dtype=np.uint8)
    red = (green * 0.55).astype(np.uint8)
    blue = (green * 0.35).astype(np.uint8)

    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[:, :, 0] = red
    rgba[:, :, 1] = green
    rgba[:, :, 2] = blue
    rgba[:, :, 3] = 255

    img = Image.fromarray(rgba, "RGBA")
    return create_texture_from_image(img)


def create_smoke_particle_texture(size=64) -> int:
    """
    Gera textura circular suave (radial gradient) com canal alpha
    otimizada para partículas de poeira e fumaça com billboarding.
    """
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    center = (size - 1) / 2.0
    max_r = size / 2.0

    for y in range(size):
        for x in range(size):
            dx = x - center
            dy = y - center
            r = math.hypot(dx, dy)
            if r <= max_r:
                # Gradiente cosseno suave
                factor = (math.cos(r / max_r * math.pi) + 1.0) / 2.0
                alpha = int(255 * (factor ** 1.5))
                # Cor cinza-poeira levemente quente
                arr[y, x, 0] = 180
                arr[y, x, 1] = 175
                arr[y, x, 2] = 170
                arr[y, x, 3] = alpha
            else:
                arr[y, x, 3] = 0

    img = Image.fromarray(arr, "RGBA")
    return create_texture_from_image(img, wrap=GL_CLAMP_TO_EDGE)


def create_blank_white_texture() -> int:
    """Textura 1x1 branca opaca para renderização com cor sólida nos shaders."""
    img = Image.new("RGBA", (2, 2), (255, 255, 255, 255))
    return create_texture_from_image(img)


def cleanup_textures():
    """Libera todas as texturas alocadas na GPU."""
    global _loaded_textures
    for tex_id in _loaded_textures:
        glDeleteTextures([tex_id])
    _loaded_textures.clear()
