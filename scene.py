"""
Objetos do cenário 3D do SeismicPyGL baseados em VBO/VAO e Shaders GLSL:
- Ground: Terreno com deformação da onda sísmica diretamente na GPU
- Building: Prédios com modelo físico de colapso, amortecimento, escombros e fumaça
- Mountain: Montanha com geometria pré-computada (sem vazamento de gluQuadric) e desmoronamento de rochas
- Tree: Árvores em VBO com balanço sísmico dinâmico
- Suporte a reset completo do cenário (tecla R)
"""

import math
import random
import numpy as np
from OpenGL.GL import glBindTexture, GL_TEXTURE_2D
from mesh import Mesh
from shader import ShaderProgram
from math_utils import translate, rotate_x, rotate_y, rotate_z, scale
from texture import load_texture


# Recursos estáticos compartilhados para máxima performance de renderização
_shared_cube_mesh = None
_shared_cone_mesh = None
_shared_cylinder_mesh = None
_concrete_texture_id = None
_grass_texture_id = None


def get_shared_cube_mesh() -> Mesh:
    global _shared_cube_mesh
    if _shared_cube_mesh is None:
        # Cubo unitário centrado em [0, 1] no eixo Y e [-0.5, 0.5] em X/Z
        _shared_cube_mesh = Mesh.create_cube(width=1.0, height=1.0, depth=1.0, y_offset=0.0)
    return _shared_cube_mesh


def get_shared_cone_mesh() -> Mesh:
    global _shared_cone_mesh
    if _shared_cone_mesh is None:
        # Cone unitário (raio base 1.0, topo 0.05, altura 1.0)
        _shared_cone_mesh = Mesh.create_cylinder(base_radius=1.0, top_radius=0.08, height=1.0, slices=14)
    return _shared_cone_mesh


def get_shared_cylinder_mesh() -> Mesh:
    global _shared_cylinder_mesh
    if _shared_cylinder_mesh is None:
        # Cilindro unitário (raio base 1.0, topo 0.8, altura 1.0)
        _shared_cylinder_mesh = Mesh.create_cylinder(base_radius=1.0, top_radius=0.8, height=1.0, slices=10)
    return _shared_cylinder_mesh


def get_concrete_texture() -> int:
    global _concrete_texture_id
    if _concrete_texture_id is None:
        _concrete_texture_id = load_texture("assets/textures/concrete.png")
    return _concrete_texture_id


def get_grass_texture() -> int:
    global _grass_texture_id
    if _grass_texture_id is None:
        _grass_texture_id = load_texture("assets/textures/grass.png")
    return _grass_texture_id


# ---------------------------------------------------------------------------
# Terreno Deformável na GPU
# ---------------------------------------------------------------------------

class Ground:
    """
    Chão em grade triangular cujos vértices são deformados pela equação
    da onda sísmica diretamente nos núcleos da GPU (ground.vert).
    """

    def __init__(self, size=140.0, divisions=80):
        self.size = size
        self.divisions = divisions
        self.mesh = Mesh.create_plane(size=size, divisions=divisions)
        self.shader = ShaderProgram.from_files(
            "assets/shaders/ground.vert",
            "assets/shaders/ground.frag"
        )
        self.texture_id = get_grass_texture()

    def draw(self, earthquake, current_time: float, view_matrix: np.ndarray, proj_matrix: np.ndarray):
        self.shader.use()

        # Matrizes MVP
        model = np.eye(4, dtype=np.float32)
        self.shader.set_uniform_mat4("u_model", model)
        self.shader.set_uniform_mat4("u_view", view_matrix)
        self.shader.set_uniform_mat4("u_projection", proj_matrix)

        # Uniforms da equação da onda sísmica repassados à GPU
        is_active = 1 if earthquake.active else 0
        self.shader.set_uniform_int("u_active", is_active)
        self.shader.set_uniform_vec2("u_epicenter", earthquake.epicenter)
        self.shader.set_uniform_float("u_time", current_time - earthquake.start_time if earthquake.active else 0.0)
        self.shader.set_uniform_float("u_wave_speed", earthquake.wave_speed)
        self.shader.set_uniform_float("u_amplitude", earthquake.magnitude if earthquake.active else 0.0)
        self.shader.set_uniform_float("u_frequency", earthquake.frequency)
        self.shader.set_uniform_float("u_damping", earthquake.damping)
        self.shader.set_uniform_float("u_spatial_falloff", earthquake.spatial_falloff)

        # Iluminação Phong / Direcional
        self.shader.set_uniform_vec3("u_light_direction", (-0.4, -1.0, -0.3))
        self.shader.set_uniform_vec3("u_light_color", (1.0, 0.98, 0.92))
        self.shader.set_uniform_vec3("u_ambient_color", (0.35, 0.38, 0.42))
        self.shader.set_uniform_vec4("u_base_color", (0.55, 0.78, 0.55, 1.0))

        # Textura
        self.shader.set_uniform_int("u_use_texture", 1)
        self.shader.set_uniform_int("u_texture", 0)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)

        self.mesh.draw()

        self.shader.stop()
        glBindTexture(GL_TEXTURE_2D, 0)

    def cleanup(self):
        if self.mesh:
            self.mesh.cleanup()
            self.mesh = None
        if self.shader:
            self.shader.cleanup()
            self.shader = None


# ---------------------------------------------------------------------------
# Prédios com Modelo de Colapso e Emissão de Poeira
# ---------------------------------------------------------------------------

class Building:
    RESISTANCE_RANGE = (2.2, 5.5)
    COLLAPSE_DURATION = 2.4
    DAMAGE_MULTIPLIER = 3.2

    def __init__(self, x, z, width, depth, height, slices=6):
        self.initial_x = x
        self.initial_z = z
        self.x = x
        self.z = z
        self.width = width
        self.depth = depth
        self.height = height
        self.slices = slices

        # Cor base do concreto
        gray = random.uniform(0.65, 0.92)
        self.color = (gray, gray * random.uniform(0.95, 1.0), gray * random.uniform(0.92, 0.98), 1.0)
        self.rubble_color = (0.38, 0.35, 0.33, 1.0)

        # Estado físico e de colapso
        self.resistance = random.uniform(*self.RESISTANCE_RANGE)
        self.damage = 0.0
        self.collapsing = False
        self.collapse_progress = 0.0
        self.y_collapse_offset = 0.0
        self.lean_angle_z = random.uniform(-22.0, 22.0)
        self.lean_angle_x = random.uniform(-15.0, 15.0)
        self.emitted_dust = False

    def reset(self):
        """Restaura o prédio ao estado intacto."""
        self.damage = 0.0
        self.collapsing = False
        self.collapse_progress = 0.0
        self.y_collapse_offset = 0.0
        self.emitted_dust = False

    def update(self, earthquake, current_time: float, dt: float, particle_system=None):
        if self.collapse_progress >= 1.0:
            return

        dx, dy, dz = earthquake.get_offset(self.x, self.z, current_time)
        amplitude = math.hypot(dx, dy, dz)

        if not self.collapsing:
            self.damage += amplitude * dt * self.DAMAGE_MULTIPLIER
            if self.damage >= self.resistance:
                self.collapsing = True
        else:
            self.collapse_progress = min(1.0, self.collapse_progress + dt / self.COLLAPSE_DURATION)
            # Translação Y: a base afunda parcialmente no solo
            self.y_collapse_offset = self.collapse_progress * (self.height * 0.45)

            # Disparo pontual de rajada de poeira e fumaça ao iniciar o colapso
            if particle_system and not self.emitted_dust:
                particle_system.emit((self.x, 0.2, self.z), count=45, spread=self.width * 0.9, base_speed=2.4)
                self.emitted_dust = True

            # Emissão contínua residual durante a queda
            if particle_system and self.collapse_progress < 0.90 and random.random() < 0.35:
                particle_system.emit((
                    self.x + random.uniform(-self.width * 0.5, self.width * 0.5),
                    0.3,
                    self.z + random.uniform(-self.depth * 0.5, self.depth * 0.5)
                ), count=4, spread=0.4, base_speed=1.0)

    def _current_color(self):
        if self.collapse_progress <= 0.0:
            return self.color
        t = self.collapse_progress
        return tuple(
            self.color[i] * (1.0 - t) + self.rubble_color[i] * t
            for i in range(4)
        )

    def draw(self, shader: ShaderProgram, earthquake, current_time: float):
        cube_mesh = get_shared_cube_mesh()
        height_factor = max(0.12, 1.0 - self.collapse_progress * 0.85)
        effective_height = self.height * height_factor
        color = self._current_color()

        dx, _, dz = earthquake.get_offset(self.x, self.z, current_time)
        sway_scale = 1.0 - self.collapse_progress

        slice_height = effective_height / self.slices
        base_lean_z = self.lean_angle_z * self.collapse_progress
        base_lean_x = self.lean_angle_x * self.collapse_progress

        for i in range(self.slices):
            t = (i + 0.5) / self.slices
            y_base = i * slice_height - self.y_collapse_offset
            sway = t * 2.2 * sway_scale

            # Matriz de Modelo unificada: M = T @ R @ S
            m_trans = translate(self.x + dx * sway, y_base, self.z + dz * sway)
            m_rot = rotate_z(base_lean_z * t) @ rotate_x(base_lean_x * t)
            m_scale = scale(self.width, slice_height, self.depth)

            model = m_trans @ m_rot @ m_scale

            shader.set_uniform_mat4("u_model", model)
            shader.set_uniform_vec4("u_base_color", color)
            cube_mesh.draw()


def generate_city(rows=5, cols=5, spacing=5.5):
    """Gera grade urbana com alturas e resistências distribuídas."""
    buildings = []
    offset_x = (rows - 1) * spacing / 2.0
    offset_z = (cols - 1) * spacing / 2.0
    for i in range(rows):
        for j in range(cols):
            x = i * spacing - offset_x
            z = j * spacing - offset_z
            w = random.uniform(1.4, 2.2)
            d = random.uniform(1.4, 2.2)
            h = random.uniform(3.5, 11.0)
            buildings.append(Building(x, z, w, d, h))
    return buildings


# ---------------------------------------------------------------------------
# Destroços e Pedras da Montanha
# ---------------------------------------------------------------------------

class RockDebris:
    GRAVITY = -11.0

    def __init__(self, x, y, z, vx, vy, vz, size=0.45, color=(0.48, 0.44, 0.40, 1.0), lifetime=6.0):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.size = size
        self.color = color
        self.lifetime = lifetime
        self.age = 0.0

    @property
    def alive(self) -> bool:
        return self.age < self.lifetime

    def update(self, dt: float):
        self.vy += self.GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.age += dt

        if self.y < 0.1:
            self.y = 0.1
            self.vy = -self.vy * 0.35  # Quique
            self.vx *= 0.82
            self.vz *= 0.82

    def draw(self, shader: ShaderProgram):
        cube_mesh = get_shared_cube_mesh()
        model = translate(self.x, self.y, self.z) @ scale(self.size, self.size, self.size)
        shader.set_uniform_mat4("u_model", model)
        shader.set_uniform_vec4("u_base_color", self.color)
        cube_mesh.draw()


# ---------------------------------------------------------------------------
# Montanha Pré-computada em VBO (Zero Quadrics / Zero Memory Leaks)
# ---------------------------------------------------------------------------

class Mountain:
    def __init__(self, x=34.0, z=34.0, base_radius=14.0, height=26.0, snow_start=0.62, bands=8):
        self.x = x
        self.z = z
        self.base_radius = base_radius
        self.height = height
        self.snow_start = snow_start
        self.bands = bands

        self.shake_threshold = 0.22
        self.spawn_rate = 9.0
        self.debris = []

        # Pré-computa as camadas da montanha em um único VBO contíguo
        verts = []
        slices = 28
        angle_step = 2.0 * math.pi / slices

        for b in range(bands):
            t0 = b / bands
            t1 = (b + 1) / bands
            r0 = self.base_radius * ((1.0 - t0) ** 1.25)
            r1 = self.base_radius * ((1.0 - t1) ** 1.25)
            y0 = t0 * self.height
            y1 = t1 * self.height

            for s in range(slices):
                a0 = s * angle_step
                a1 = (s + 1) * angle_step
                c0, s0 = math.cos(a0), math.sin(a0)
                c1, s1 = math.cos(a1), math.sin(a1)

                p00 = [c0 * r0, y0, s0 * r0]
                p10 = [c1 * r0, y0, s1 * r0]
                p11 = [c1 * r1, y1, s1 * r1]
                p01 = [c0 * r1, y1, s0 * r1]

                # Normal estimada
                n0 = [c0, 0.35, s0]
                n1 = [c1, 0.35, s1]

                # Triângulo 1: p00 -> p10 -> p11
                verts.extend([
                    p00[0], p00[1], p00[2],  s / slices * 4.0, t0 * 4.0,  n0[0], n0[1], n0[2],
                    p10[0], p10[1], p10[2],  (s + 1) / slices * 4.0, t0 * 4.0,  n1[0], n1[1], n1[2],
                    p11[0], p11[1], p11[2],  (s + 1) / slices * 4.0, t1 * 4.0,  n1[0], n1[1], n1[2],
                ])
                # Triângulo 2: p00 -> p11 -> p01
                verts.extend([
                    p00[0], p00[1], p00[2],  s / slices * 4.0, t0 * 4.0,  n0[0], n0[1], n0[2],
                    p11[0], p11[1], p11[2],  (s + 1) / slices * 4.0, t1 * 4.0,  n1[0], n1[1], n1[2],
                    p01[0], p01[1], p01[2],  s / slices * 4.0, t1 * 4.0,  n0[0], n0[1], n0[2],
                ])

        v_arr = np.array(verts, dtype=np.float32)
        self.mesh = Mesh(v_arr, len(v_arr) // 8, stride=32)

    def update(self, earthquake, current_time: float, dt: float):
        dx, dy, dz = earthquake.get_offset(self.x, self.z, current_time)
        amplitude = math.hypot(dx, dy, dz)

        if amplitude > self.shake_threshold:
            excess = amplitude - self.shake_threshold
            prob = min(0.95, excess * self.spawn_rate) * dt * 10.0
            if random.random() < prob:
                self._spawn_rock()

        for rock in self.debris:
            rock.update(dt)
        self.debris = [r for r in self.debris if r.alive]

    def _spawn_rock(self):
        t = random.uniform(0.25, 0.92)
        radius = self.base_radius * ((1.0 - t) ** 1.25)
        angle = random.uniform(0, 2 * math.pi)

        rx = self.x + math.cos(angle) * radius
        rz = self.z + math.sin(angle) * radius
        ry = t * self.height

        outward_speed = random.uniform(1.2, 3.5)
        vx = math.cos(angle) * outward_speed
        vz = math.sin(angle) * outward_speed
        vy = random.uniform(-0.5, 0.8)

        color = (0.95, 0.96, 0.98, 1.0) if t >= self.snow_start else (0.42, 0.38, 0.34, 1.0)
        self.debris.append(RockDebris(rx, ry, rz, vx, vy, vz, size=random.uniform(0.35, 0.75), color=color))

    def draw(self, shader: ShaderProgram):
        model = translate(self.x, 0.0, self.z)
        shader.set_uniform_mat4("u_model", model)
        shader.set_uniform_vec4("u_base_color", (0.55, 0.52, 0.48, 1.0))
        self.mesh.draw()

        for rock in self.debris:
            rock.draw(shader)

    def cleanup(self):
        if self.mesh:
            self.mesh.cleanup()
            self.mesh = None


# ---------------------------------------------------------------------------
# Árvores em VBO Pré-computado
# ---------------------------------------------------------------------------

class Tree:
    def __init__(self, x, z, trunk_height=1.6, trunk_radius=0.18, foliage_layers=3, foliage_height=2.8, foliage_radius=1.1):
        self.x = x
        self.z = z
        self.trunk_height = trunk_height
        self.trunk_radius = trunk_radius
        self.foliage_layers = foliage_layers
        self.foliage_height = foliage_height
        self.foliage_radius = foliage_radius
        self.total_height = trunk_height + foliage_height

    def draw(self, shader: ShaderProgram, earthquake, current_time: float):
        cyl_mesh = get_shared_cylinder_mesh()
        cone_mesh = get_shared_cone_mesh()

        dx, _, dz = earthquake.get_offset(self.x, self.z, current_time)

        # 1. Tronco da árvore
        m_trunk = translate(self.x, 0.0, self.z) @ scale(self.trunk_radius, self.trunk_height, self.trunk_radius)
        shader.set_uniform_mat4("u_model", m_trunk)
        shader.set_uniform_vec4("u_base_color", (0.38, 0.24, 0.12, 1.0))
        cyl_mesh.draw()

        # 2. Copa em camadas
        layer_h = self.foliage_height / self.foliage_layers
        for i in range(self.foliage_layers):
            t = i / self.foliage_layers
            y0 = self.trunk_height + t * self.foliage_height
            rad = self.foliage_radius * (1.0 - t * 0.55)
            sway = (y0 / self.total_height) * 1.8

            m_cone = translate(self.x + dx * sway, y0, self.z + dz * sway) @ scale(rad, layer_h * 1.3, rad)
            shader.set_uniform_mat4("u_model", m_cone)
            # Variação sutil de verde por camada
            g = 0.38 + t * 0.12
            shader.set_uniform_vec4("u_base_color", (0.12, g, 0.16, 1.0))
            cone_mesh.draw()


def generate_forest(count, center, radius_range, avoid_center=None, avoid_radius=0.0):
    trees = []
    cx, cz = center
    r_min, r_max = radius_range
    attempts = 0
    max_attempts = count * 12

    while len(trees) < count and attempts < max_attempts:
        attempts += 1
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(r_min, r_max)
        x = cx + math.cos(angle) * r
        z = cz + math.sin(angle) * r

        if avoid_center is not None:
            ax, az = avoid_center
            if math.hypot(x - ax, z - az) < avoid_radius:
                continue

        trees.append(Tree(
            x, z,
            trunk_height=random.uniform(1.3, 1.9),
            trunk_radius=random.uniform(0.14, 0.22),
            foliage_layers=random.randint(2, 4),
            foliage_height=random.uniform(2.2, 3.2),
            foliage_radius=random.uniform(0.9, 1.4),
        ))

    return trees
