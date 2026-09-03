"""Módulo Core do SeismicPyGL: matemática 3D, câmera, shaders, malhas e texturas."""

from .math_utils import (
    perspective, look_at, ortho, translate, rotate_x, rotate_y, rotate_z, scale,
    to_gl_matrix, perlin1d, perlin2d
)
from .shader import ShaderProgram, check_gl_error
from .mesh import Mesh
from .obj_loader import (
    parse_obj, create_cube_mesh, create_plane_mesh, create_quad_mesh,
    create_cylinder_mesh, compute_tangents
)
from .texture import (
    create_texture_from_image, load_texture, load_texture_set,
    cleanup_textures, get_flat_normal_texture, get_default_roughness_texture
)
from .camera import FreeCamera

__all__ = [
    "perspective", "look_at", "ortho", "translate", "rotate_x", "rotate_y", "rotate_z", "scale",
    "to_gl_matrix", "perlin1d", "perlin2d",
    "ShaderProgram", "check_gl_error",
    "Mesh",
    "parse_obj", "create_cube_mesh", "create_plane_mesh", "create_quad_mesh",
    "create_cylinder_mesh", "compute_tangents",
    "create_texture_from_image", "load_texture", "load_texture_set",
    "cleanup_textures", "get_flat_normal_texture", "get_default_roughness_texture",
    "FreeCamera",
]
