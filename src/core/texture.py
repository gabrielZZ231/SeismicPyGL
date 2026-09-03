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
_pbr_set_cache = {}
_flat_normal_id = None
_default_roughness_id = None


def procedural_texture_size():
    """Materiais nítidos em 4K, sem alocar texturas 4K desnecessárias em 1080p."""
    preset = os.environ.get("SEISMICPYGL_RESOLUTION", "1080p").lower()
    return 1024 if preset in {"4k", "2160p", "3840x2160"} else 512


def get_flat_normal_texture() -> int:
    """Gera textura 2x2 normal neutra (128, 128, 255) em tangent space."""
    global _flat_normal_id
    if _flat_normal_id is None:
        img = Image.new("RGBA", (2, 2), (128, 128, 255, 255))
        _flat_normal_id = create_texture_from_image(img)
    return _flat_normal_id


def get_default_roughness_texture(value: int = 180) -> int:
    """Gera textura 2x2 de rugosidade padrao."""
    global _default_roughness_id
    if _default_roughness_id is None:
        img = Image.new("RGBA", (2, 2), (value, value, value, 255))
        _default_roughness_id = create_texture_from_image(img)
    return _default_roughness_id


def create_texture_from_image(img: Image.Image, wrap=GL_REPEAT, max_size=2048) -> int:
    """Faz upload de um objeto PIL.Image para a GPU via glTexImage2D com redimensionamento inteligente."""
    if max_size and (img.width > max_size or img.height > max_size):
        img = img.resize((max_size, max_size), Image.Resampling.LANCZOS)

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
    Se o arquivo nao existir, gera textura procedural padrao correspondente.
    """
    if path and os.path.exists(path):
        img = Image.open(path)
        return create_texture_from_image(img, wrap)
    else:
        # Fallback procedural se nao encontrar
        if path:
            print(f"[Aviso] Textura '{path}' nao encontrada. Gerando procedural correspondente.")
            basename = os.path.basename(path).lower()
        else:
            basename = ""
        if "smoke" in basename or "particle" in basename:
            return create_smoke_particle_texture()
        elif "grass" in basename or "ground" in basename:
            return create_grass_texture()
        elif "asphalt" in basename or "road" in basename:
            return create_asphalt_texture()
        elif "nor" in basename or "normal" in basename:
            return get_flat_normal_texture()
        elif "rough" in basename:
            return get_default_roughness_texture()
        else:
            return create_concrete_texture()


def load_texture_set(material_dir: str, wrap=GL_REPEAT) -> dict:
    """
    Carrega albedo, normal e roughness de uma pasta de material PBR.
    Busca arquivos por sufixo (_diff_, _nor_gl_, _rough_) dentro de material_dir.
    Retorna dict com {'albedo': int, 'normal': int, 'roughness': int}.
    Usa cache e fallbacks procedurais se algum arquivo faltar.
    """
    # Resolve sempre a partir deste módulo; assim a execução fora da raiz do
    # repositório não troca silenciosamente materiais PBR por fallbacks.
    if not os.path.isabs(material_dir):
        material_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), material_dir)
    material_dir = os.path.normpath(material_dir)

    if material_dir in _pbr_set_cache:
        return _pbr_set_cache[material_dir]

    diff_path = None
    nor_path = None
    rough_path = None

    if os.path.exists(material_dir):
        for f in os.listdir(material_dir):
            fl = f.lower()
            full = os.path.join(material_dir, f)
            if "_diff_" in fl and fl.endswith((".jpg", ".png", ".jpeg", ".webp")):
                diff_path = full
            elif "_nor_gl_" in fl and fl.endswith((".png", ".jpg")):
                nor_path = full
            elif "_rough_" in fl and fl.endswith((".png", ".jpg")):
                rough_path = full

    # O repositório pode não incluir todos os pacotes PBR externos. Seleciona
    # um material procedural coerente em alta definição, em vez de concreto
    # genérico para asfalto e grama.
    material_name = os.path.basename(os.path.dirname(material_dir)).lower()
    if diff_path:
        albedo_id = load_texture(diff_path, wrap=wrap)
    elif "asphalt" in material_name:
        albedo_id = create_asphalt_texture(procedural_texture_size())
    elif "grass" in material_name:
        albedo_id = create_grass_texture(procedural_texture_size())
    else:
        albedo_id = create_concrete_texture(procedural_texture_size())
    normal_id = load_texture(nor_path, wrap=wrap) if nor_path else get_flat_normal_texture()
    rough_id = load_texture(rough_path, wrap=wrap) if rough_path else get_default_roughness_texture()

    res = {
        "albedo": albedo_id,
        "normal": normal_id,
        "roughness": rough_id
    }
    _pbr_set_cache[material_dir] = res
    return res


def create_concrete_texture(size=None) -> int:
    """Gera textura procedural de concreto com ruído fino."""
    size = size or procedural_texture_size()
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


def create_grass_texture(size=None) -> int:
    """Gera textura procedural de terreno/grama."""
    size = size or procedural_texture_size()
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


def create_asphalt_texture(size=None) -> int:
    """Gera textura procedural de asfalto com ruído e faixa central amarela."""
    size = size or procedural_texture_size()
    rng = np.random.default_rng(789)
    base = rng.integers(45, 65, (size, size), dtype=np.uint8)
    noise = rng.integers(-8, 9, (size, size), dtype=np.int16)
    asphalt = np.clip(base + noise, 0, 255).astype(np.uint8)
    
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[:, :, 0] = asphalt
    rgba[:, :, 1] = asphalt
    rgba[:, :, 2] = (asphalt * 0.92).astype(np.uint8)
    rgba[:, :, 3] = 255
    
    # Faixa central amarela tracejada
    center = size // 2
    stripe_width = max(2, size // 32)
    dash_length = size // 8
    for y in range(size):
        if (y // dash_length) % 2 == 0:
            for x in range(center - stripe_width, center + stripe_width):
                rgba[y, x, 0] = 210
                rgba[y, x, 1] = 190
                rgba[y, x, 2] = 50
    
    img = Image.fromarray(rgba, "RGBA")
    return create_texture_from_image(img)


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
