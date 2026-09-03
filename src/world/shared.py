"""Recursos compartilhados e instanciados para os objetos do mundo 3D."""

import os
import numpy as np
from ..core.mesh import Mesh
from ..core.texture import load_texture_set
from ..core.obj_loader import compute_tangents

_shared_cube_mesh = None
_shared_cone_mesh = None
_shared_cylinder_mesh = None
_shared_pyramid_mesh = None
_shared_gable_mesh = None

_pbr_materials = {}


def get_pbr_set(name: str) -> dict:
    """Carrega e armazena em cache os conjuntos PBR (albedo, normal, roughness)."""
    global _pbr_materials
    if name not in _pbr_materials:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base_dir, "assets", "textures", "pbr", name, "textures")
        _pbr_materials[name] = load_texture_set(path)
    return _pbr_materials[name]


def get_shared_cube_mesh() -> Mesh:
    global _shared_cube_mesh
    if _shared_cube_mesh is None:
        _shared_cube_mesh = Mesh.create_cube(width=1.0, height=1.0, depth=1.0, y_offset=0.0)
    return _shared_cube_mesh


def get_shared_cone_mesh() -> Mesh:
    global _shared_cone_mesh
    if _shared_cone_mesh is None:
        _shared_cone_mesh = Mesh.create_cylinder(base_radius=1.0, top_radius=0.06, height=1.0, slices=32)
    return _shared_cone_mesh


def get_shared_cylinder_mesh() -> Mesh:
    global _shared_cylinder_mesh
    if _shared_cylinder_mesh is None:
        _shared_cylinder_mesh = Mesh.create_cylinder(base_radius=1.0, top_radius=0.8, height=1.0, slices=24)
    return _shared_cylinder_mesh


def get_shared_pyramid_mesh() -> Mesh:
    global _shared_pyramid_mesh
    if _shared_pyramid_mesh is None:
        _shared_pyramid_mesh = Mesh.create_cylinder(base_radius=1.0, top_radius=0.01, height=1.0, slices=4)
    return _shared_pyramid_mesh


def get_shared_gable_mesh() -> Mesh:
    """Prisma triangular unitário para telhados residenciais de duas águas."""
    global _shared_gable_mesh
    if _shared_gable_mesh is None:
        verts = np.array([
            # Água esquerda e direita
            -0.5, 0, -0.5, 0, 0,  -0.82, 0.57, 0,   0, 1, -0.5, 1, 1,  -0.82, 0.57, 0,   0, 1, 0.5, 1, 0,  -0.82, 0.57, 0,
             0.5, 0, -0.5, 0, 0,   0.82, 0.57, 0,   0.5, 0, 0.5, 1, 0,   0.82, 0.57, 0,   0, 1, 0.5, 1, 1,   0.82, 0.57, 0,
            # Fachadas triangulares
            -0.5, 0, -0.5, 0, 0,   0, 0, -1,   0.5, 0, -0.5, 1, 0,   0, 0, -1,   0, 1, -0.5, 0.5, 1,  0, 0, -1,
            -0.5, 0, 0.5, 0, 0,    0, 0, 1,    0, 1, 0.5, 0.5, 1,  0, 0, 1,    0.5, 0, 0.5, 1, 0,  0, 0, 1,
        ], dtype=np.float32)
        data, count, stride = compute_tangents(verts)
        _shared_gable_mesh = Mesh(data, count, stride)
    return _shared_gable_mesh


def get_concrete_texture() -> int:
    return get_pbr_set("damaged_plaster")["albedo"]


def get_grass_texture() -> int:
    return get_pbr_set("sparse_grass")["albedo"]


def get_asphalt_texture() -> int:
    return get_pbr_set("clean_asphalt")["albedo"]
