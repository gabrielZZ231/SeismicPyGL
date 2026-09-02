"""
Carregador de modelos 3D (.obj) e gerador de malhas procedurais.
Gera buffers entrelaçados (interleaved vertex buffer) com layout contíguo:
[x, y, z,   u, v,   nx, ny, nz] -> stride = 32 bytes (8 floats de 4 bytes)
Atributos:
- Posição: 3 floats (offset 0)
- UV: 2 floats (offset 12)
- Normal: 3 floats (offset 20)
"""

import os
import math
import numpy as np

VERTEX_STRIDE = 32  # 8 * 4 bytes


def parse_obj(file_path: str):
    """
    Parser iterativo linha-a-linha de arquivos Wavefront .obj.
    Suporta faces poligonais (com triangulação automática em leque),
    e formatos 'v/vt/vn', 'v//vn', 'v/vt' e 'v'.
    Retorna (vertex_data, vertex_count, stride).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Arquivo OBJ não encontrado: {file_path}")

    positions = []
    tex_coords = []
    normals = []
    interleaved_vertices = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            cmd = parts[0]

            if cmd == "v":
                positions.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif cmd == "vt":
                tex_coords.append([float(parts[1]), float(parts[2])])
            elif cmd == "vn":
                normals.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif cmd == "f":
                # Processa cada vértice da face
                face_vertices = []
                for p in parts[1:]:
                    subparts = p.split("/")
                    # v_idx, vt_idx, vn_idx (1-based index)
                    v_idx = int(subparts[0]) - 1
                    vt_idx = int(subparts[1]) - 1 if len(subparts) > 1 and subparts[1] else None
                    vn_idx = int(subparts[2]) - 1 if len(subparts) > 2 and subparts[2] else None

                    pos = positions[v_idx]
                    uv = tex_coords[vt_idx] if vt_idx is not None and vt_idx < len(tex_coords) else [0.0, 0.0]
                    norm = normals[vn_idx] if vn_idx is not None and vn_idx < len(normals) else [0.0, 1.0, 0.0]

                    face_vertices.append(pos + uv + norm)

                # Triangulação em leque (fan triangulation) para polígonos com >3 vértices
                for i in range(1, len(face_vertices) - 1):
                    interleaved_vertices.extend(face_vertices[0])
                    interleaved_vertices.extend(face_vertices[i])
                    interleaved_vertices.extend(face_vertices[i + 1])

    vertex_data = np.array(interleaved_vertices, dtype=np.float32)
    vertex_count = len(vertex_data) // 8
    return vertex_data, vertex_count, VERTEX_STRIDE


# ---------------------------------------------------------------------------
# Geradores Procedurais de Malha (Mesmo layout contíguo de 32 bytes)
# ---------------------------------------------------------------------------

def create_cube_mesh(width=1.0, height=1.0, depth=1.0, y_offset=0.0):
    """Cria um cubo centrado em X/Z com altura a partir de y_offset."""
    hw = width / 2.0
    hd = depth / 2.0
    y0 = y_offset
    y1 = y_offset + height

    # 6 faces x 2 triângulos x 3 vértices = 36 vértices
    # [x, y, z,  u, v,  nx, ny, nz]
    verts = [
        # Frente (Z+) normal (0, 0, 1)
        -hw, y0,  hd,  0.0, 0.0,  0.0, 0.0, 1.0,
         hw, y0,  hd,  1.0, 0.0,  0.0, 0.0, 1.0,
         hw, y1,  hd,  1.0, 1.0,  0.0, 0.0, 1.0,
        -hw, y0,  hd,  0.0, 0.0,  0.0, 0.0, 1.0,
         hw, y1,  hd,  1.0, 1.0,  0.0, 0.0, 1.0,
        -hw, y1,  hd,  0.0, 1.0,  0.0, 0.0, 1.0,

        # Trás (Z-) normal (0, 0, -1)
         hw, y0, -hd,  0.0, 0.0,  0.0, 0.0, -1.0,
        -hw, y0, -hd,  1.0, 0.0,  0.0, 0.0, -1.0,
        -hw, y1, -hd,  1.0, 1.0,  0.0, 0.0, -1.0,
         hw, y0, -hd,  0.0, 0.0,  0.0, 0.0, -1.0,
        -hw, y1, -hd,  1.0, 1.0,  0.0, 0.0, -1.0,
         hw, y1, -hd,  0.0, 1.0,  0.0, 0.0, -1.0,

        # Esquerda (X-) normal (-1, 0, 0)
        -hw, y0, -hd,  0.0, 0.0, -1.0, 0.0, 0.0,
        -hw, y0,  hd,  1.0, 0.0, -1.0, 0.0, 0.0,
        -hw, y1,  hd,  1.0, 1.0, -1.0, 0.0, 0.0,
        -hw, y0, -hd,  0.0, 0.0, -1.0, 0.0, 0.0,
        -hw, y1,  hd,  1.0, 1.0, -1.0, 0.0, 0.0,
        -hw, y1, -hd,  0.0, 1.0, -1.0, 0.0, 0.0,

        # Direita (X+) normal (1, 0, 0)
         hw, y0,  hd,  0.0, 0.0,  1.0, 0.0, 0.0,
         hw, y0, -hd,  1.0, 0.0,  1.0, 0.0, 0.0,
         hw, y1, -hd,  1.0, 1.0,  1.0, 0.0, 0.0,
         hw, y0,  hd,  0.0, 0.0,  1.0, 0.0, 0.0,
         hw, y1, -hd,  1.0, 1.0,  1.0, 0.0, 0.0,
         hw, y1,  hd,  0.0, 1.0,  1.0, 0.0, 0.0,

        # Topo (Y+) normal (0, 1, 0)
        -hw, y1,  hd,  0.0, 0.0,  0.0, 1.0, 0.0,
         hw, y1,  hd,  1.0, 0.0,  0.0, 1.0, 0.0,
         hw, y1, -hd,  1.0, 1.0,  0.0, 1.0, 0.0,
        -hw, y1,  hd,  0.0, 0.0,  0.0, 1.0, 0.0,
         hw, y1, -hd,  1.0, 1.0,  0.0, 1.0, 0.0,
        -hw, y1, -hd,  0.0, 1.0,  0.0, 1.0, 0.0,

        # Base (Y-) normal (0, -1, 0)
        -hw, y0, -hd,  0.0, 0.0,  0.0, -1.0, 0.0,
         hw, y0, -hd,  1.0, 0.0,  0.0, -1.0, 0.0,
         hw, y0,  hd,  1.0, 1.0,  0.0, -1.0, 0.0,
        -hw, y0, -hd,  0.0, 0.0,  0.0, -1.0, 0.0,
         hw, y0,  hd,  1.0, 1.0,  0.0, -1.0, 0.0,
        -hw, y0,  hd,  0.0, 1.0,  0.0, -1.0, 0.0,
    ]

    arr = np.array(verts, dtype=np.float32)
    return arr, len(arr) // 8, VERTEX_STRIDE


def create_plane_mesh(size=100.0, divisions=50):
    """
    Cria uma grade retangular contínua no plano XZ em Y=0.
    Gera triângulos triangulados para simulação da onda sísmica.
    """
    step = size / divisions
    half = size / 2.0
    verts = []

    for i in range(divisions):
        for j in range(divisions):
            x0 = -half + i * step
            x1 = x0 + step
            z0 = -half + j * step
            z1 = z0 + step

            u0 = i / divisions * 10.0  # Tiling da textura
            u1 = (i + 1) / divisions * 10.0
            v0 = j / divisions * 10.0
            v1 = (j + 1) / divisions * 10.0

            # Triângulo 1 (x0,z0), (x1,z0), (x1,z1)
            verts.extend([
                x0, 0.0, z0,  u0, v0,  0.0, 1.0, 0.0,
                x1, 0.0, z0,  u1, v0,  0.0, 1.0, 0.0,
                x1, 0.0, z1,  u1, v1,  0.0, 1.0, 0.0,
            ])
            # Triângulo 2 (x0,z0), (x1,z1), (x0,z1)
            verts.extend([
                x0, 0.0, z0,  u0, v0,  0.0, 1.0, 0.0,
                x1, 0.0, z1,  u1, v1,  0.0, 1.0, 0.0,
                x0, 0.0, z1,  u0, v1,  0.0, 1.0, 0.0,
            ])

    arr = np.array(verts, dtype=np.float32)
    return arr, len(arr) // 8, VERTEX_STRIDE


def create_quad_mesh(size=1.0):
    """Cria um quad 2D centrado no plano XY em [-size/2, size/2] com Z=0 (para Billboards e HUD)."""
    h = size / 2.0
    verts = [
        -h, -h, 0.0,  0.0, 0.0,  0.0, 0.0, 1.0,
         h, -h, 0.0,  1.0, 0.0,  0.0, 0.0, 1.0,
         h,  h, 0.0,  1.0, 1.0,  0.0, 0.0, 1.0,

        -h, -h, 0.0,  0.0, 0.0,  0.0, 0.0, 1.0,
         h,  h, 0.0,  1.0, 1.0,  0.0, 0.0, 1.0,
        -h,  h, 0.0,  0.0, 1.0,  0.0, 0.0, 1.0,
    ]
    arr = np.array(verts, dtype=np.float32)
    return arr, len(arr) // 8, VERTEX_STRIDE


def create_cylinder_mesh(base_radius=1.0, top_radius=1.0, height=1.0, slices=16):
    """Cria um cone ou cilindro orientado ao longo do eixo Y positivo [0, height]."""
    verts = []
    angle_step = 2.0 * math.pi / slices

    for i in range(slices):
        a0 = i * angle_step
        a1 = (i + 1) * angle_step

        c0, s0 = math.cos(a0), math.sin(a0)
        c1, s1 = math.cos(a1), math.sin(a1)

        # Pontos na base (Y=0)
        x0_b, z0_b = c0 * base_radius, s0 * base_radius
        x1_b, z1_b = c1 * base_radius, s1 * base_radius

        # Pontos no topo (Y=height)
        x0_t, z0_t = c0 * top_radius, s0 * top_radius
        x1_t, z1_t = c1 * top_radius, s1 * top_radius

        u0 = i / slices
        u1 = (i + 1) / slices

        # Normal lateral estimada
        n0 = [c0, 0.0, s0]
        n1 = [c1, 0.0, s1]

        # Triângulo lateral 1: base0 -> base1 -> top1
        verts.extend([
            x0_b, 0.0, z0_b,  u0, 0.0,  n0[0], n0[1], n0[2],
            x1_b, 0.0, z1_b,  u1, 0.0,  n1[0], n1[1], n1[2],
            x1_t, height, z1_t, u1, 1.0, n1[0], n1[1], n1[2],
        ])

        # Triângulo lateral 2: base0 -> top1 -> top0
        verts.extend([
            x0_b, 0.0, z0_b,  u0, 0.0,  n0[0], n0[1], n0[2],
            x1_t, height, z1_t, u1, 1.0, n1[0], n1[1], n1[2],
            x0_t, height, z0_t, u0, 1.0, n0[0], n0[1], n0[2],
        ])

    arr = np.array(verts, dtype=np.float32)
    return arr, len(arr) // 8, VERTEX_STRIDE
