"""
Objetos do cenário 3D do SeismicPyGL baseados em VBO/VAO e Shaders GLSL:
- Ground: Terreno com deformação da onda sísmica diretamente na GPU
- Building: Prédios com modelo físico de colapso, amortecimento, escombros e fumaça
- Mountain: Montanha com geometria pré-computada (sem vazamento de gluQuadric) e desmoronamento de rochas
- Tree: Árvores em VBO com balanço sísmico dinâmico e física de queda
- Suporte a reset completo do cenário (tecla R)
"""

import math
import random
import numpy as np
from OpenGL.GL import glBindTexture, GL_TEXTURE_2D
from mesh import Mesh
from shader import ShaderProgram
from math_utils import translate, rotate_x, rotate_y, rotate_z, scale, perlin2d
from texture import load_texture


# Recursos estáticos compartilhados para máxima performance de renderização
_shared_cube_mesh = None
_shared_cone_mesh = None
_shared_cylinder_mesh = None
_concrete_texture_id = None
_grass_texture_id = None

_shared_pyramid_mesh = None
_asphalt_texture_id = None

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


def get_shared_pyramid_mesh() -> Mesh:
    global _shared_pyramid_mesh
    if _shared_pyramid_mesh is None:
        _shared_pyramid_mesh = Mesh.create_cylinder(base_radius=1.0, top_radius=0.01, height=1.0, slices=4)
    return _shared_pyramid_mesh

def get_asphalt_texture() -> int:
    global _asphalt_texture_id
    if _asphalt_texture_id is None:
        _asphalt_texture_id = load_texture("assets/textures/asphalt.png")
    return _asphalt_texture_id


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
    COLLAPSE_DURATION = 2.0
    DAMAGE_MULTIPLIER = 3.2

    def __init__(self, x, z, width, depth, height, slices=6, is_house=False):
        self.initial_x = x
        self.initial_z = z
        self.x = x
        self.z = z
        self.width = width
        self.depth = depth
        self.height = height
        self.slices = slices
        self.is_house = is_house

        if self.is_house:
            self.height = min(max(self.height, 2.5), 4.0)
            colors = [(0.95,0.90,0.82,1.0), (0.88,0.82,0.72,1.0), (0.92,0.78,0.62,1.0)]
            self.color = random.choice(colors)
        else:
            gray = random.uniform(0.65, 0.92)
            self.color = (gray, gray * random.uniform(0.95, 1.0), gray * random.uniform(0.92, 0.98), 1.0)
            
        self.rubble_color = (0.38, 0.35, 0.33, 1.0)

        # Estado físico e de colapso
        self.resistance = random.uniform(*self.RESISTANCE_RANGE)
        self.damage = 0.0
        self.collapsing = False
        self.collapse_progress = 0.0
        self.y_collapse_offset = 0.0
        self.lean_angle_z = random.uniform(-35.0, 35.0)
        self.lean_angle_x = random.uniform(-25.0, 25.0)
        self.emitted_dust = False
        self.debris = []
        self.spawned_debris = False

    def reset(self):
        """Restaura o prédio ao estado intacto."""
        self.damage = 0.0
        self.collapsing = False
        self.collapse_progress = 0.0
        self.y_collapse_offset = 0.0
        self.emitted_dust = False
        self.debris.clear()
        self.spawned_debris = False

    def _spawn_debris(self):
        """Cria blocos de concreto que se espalham pelo solo durante a queda."""
        for _ in range(random.randint(60, 90)):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(1.2, 4.5)
            
            if random.random() < 0.2:
                s = random.uniform(0.5, 1.0)
                size = (s, random.uniform(0.12, 0.35), s)
            else:
                s = random.uniform(0.1, 0.3)
                size = (s, s, s)
                
            self.debris.append(BuildingDebris(
                x=self.x + random.uniform(-self.width * 0.45, self.width * 0.45),
                y=random.uniform(0.2, self.height * 0.85),
                z=self.z + random.uniform(-self.depth * 0.45, self.depth * 0.45),
                vx=math.cos(angle) * speed,
                vy=random.uniform(1.5, 6.0),
                vz=math.sin(angle) * speed,
                size=size,
                release=random.uniform(0.02, 0.58),
            ))

    def update(self, earthquake, current_time: float, dt: float, particle_system=None):
        dx, dy, dz = earthquake.get_offset(self.x, self.z, current_time)
        amplitude = math.hypot(dx, dy, dz)

        if not self.collapsing:
            self.damage += amplitude * dt * self.DAMAGE_MULTIPLIER
            if self.damage >= self.resistance:
                self.collapsing = True
                self._spawn_debris()
                self.spawned_debris = True
        else:
            self.collapse_progress = min(1.0, self.collapse_progress + dt / self.COLLAPSE_DURATION)
            if self.collapse_progress > 0.80:
                self.y_collapse_offset = (self.collapse_progress - 0.80) / 0.20 * 0.6
            else:
                self.y_collapse_offset = 0.0

            # Disparo pontual de rajada de poeira e fumaça ao iniciar o colapso
            if particle_system and not self.emitted_dust:
                particle_system.emit((self.x, 0.25, self.z), count=300, spread=max(self.width, self.depth) * 1.35, base_speed=3.6)
                self.emitted_dust = True

            # Emissão contínua residual durante a queda
            if particle_system and self.collapse_progress < 0.90 and random.random() < 0.65:
                particle_system.emit((
                    self.x + random.uniform(-self.width * 0.5, self.width * 0.5),
                    0.3,
                    self.z + random.uniform(-self.depth * 0.5, self.depth * 0.5)
                ), count=25, spread=0.65, base_speed=1.8)

        for debris in self.debris:
            debris.update(dt, self.collapse_progress)

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
        shader.set_uniform_int("u_building_facade", 1)
        # Mantém volume durante a queda; a estrutura só some quando os destroços a substituem.
        height_factor = max(0.35, 1.0 - self.collapse_progress * 0.65)
        effective_height = self.height * height_factor
        color = self._current_color()

        dx, _, dz = earthquake.get_offset(self.x, self.z, current_time)
        sway_scale = 1.0 - self.collapse_progress

        slice_height = effective_height / self.slices
        base_lean_z = self.lean_angle_z * self.collapse_progress
        base_lean_x = self.lean_angle_x * self.collapse_progress

        for i in range(self.slices):
            t = (i + 0.5) / self.slices
            # As lajes superiores caem primeiro e giram ao redor de suas próprias bases.
            piece_fall = max(0.0, min(1.0, (self.collapse_progress - (1.0 - t) * 0.32) / 0.68))
            y_base = i * slice_height * (1.0 - piece_fall * 0.72) - self.y_collapse_offset
            sway = t * 2.2 * sway_scale
            
            dx_out = math.sin(math.radians(self.lean_angle_z)) * piece_fall * self.width
            dz_out = math.sin(math.radians(self.lean_angle_x)) * piece_fall * self.depth

            # Matriz de Modelo unificada: M = T @ R @ S
            m_trans = translate(self.x + dx * sway + dx_out, y_base, self.z + dz * sway + dz_out)
            m_rot = rotate_z(base_lean_z * t * piece_fall) @ rotate_x(base_lean_x * t * piece_fall)
            m_scale = scale(self.width, slice_height, self.depth)

            model = m_trans @ m_rot @ m_scale

            shader.set_uniform_mat4("u_model", model)
            shader.set_uniform_vec4("u_base_color", color)
            cube_mesh.draw()
            
            if self.is_house and not self.collapsing and i == self.slices - 1:
                pyramid_mesh = get_shared_pyramid_mesh()
                roof_y = y_base + slice_height
                m_roof_trans = translate(self.x + dx * sway, roof_y, self.z + dz * sway)
                m_roof_scale = scale(self.width / 2.0, self.height * 0.3, self.depth / 2.0)
                m_roof_rot = rotate_y(45)
                model_roof = m_roof_trans @ m_roof_rot @ m_roof_scale
                
                shader.set_uniform_int("u_building_facade", 0)
                shader.set_uniform_mat4("u_model", model_roof)
                shader.set_uniform_vec4("u_base_color", (0.55, 0.25, 0.2, 1.0))
                pyramid_mesh.draw()
                shader.set_uniform_int("u_building_facade", 1)

        # Destroços usam concreto opaco, sem o padrão de janelas da fachada.
        shader.set_uniform_int("u_building_facade", 0)
        for debris in self.debris:
            debris.draw(shader)


def create_house(x, z):
    w = random.uniform(1.8, 2.8)
    d = random.uniform(1.8, 2.8)
    h = random.uniform(2.5, 4.0)
    return Building(x, z, w, d, h, slices=3, is_house=True)


class BuildingDebris:
    """Fragmento físico simples de concreto liberado no decorrer do colapso."""
    GRAVITY = -13.0

    def __init__(self, x, y, z, vx, vy, vz, size, release):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.size = size
        self.release = release
        self.released = False
        self.rotation_x = random.uniform(0.0, 360.0)
        self.rotation_z = random.uniform(0.0, 360.0)
        self.spin_x = random.uniform(-280.0, 280.0)
        self.spin_z = random.uniform(-280.0, 280.0)

    def update(self, dt, collapse_progress):
        if not self.released:
            self.released = collapse_progress >= self.release
        if not self.released:
            return
        self.vy += self.GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.rotation_x += self.spin_x * dt
        self.rotation_z += self.spin_z * dt
        if self.y < 0.02:
            self.y = 0.02
            self.vy = -self.vy * 0.23
            self.vx *= 0.72
            self.vz *= 0.72
            self.spin_x *= 0.80
            self.spin_z *= 0.80

    def draw(self, shader: ShaderProgram):
        if not self.released:
            return
        model = (translate(self.x, self.y, self.z) @ rotate_z(self.rotation_z)
                 @ rotate_x(self.rotation_x) @ scale(*self.size))
        shader.set_uniform_mat4("u_model", model)
        shader.set_uniform_vec4("u_base_color", (0.37, 0.34, 0.31, 1.0))
        get_shared_cube_mesh().draw()


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

def generate_village(center=(0.0, 0.0), building_count=9, house_count=24, block_spacing=6.0, street_width=2.5):
    """Gera uma vila mista com núcleo de prédios, quarteirões de casas e ruas."""
    buildings = []
    houses = []
    streets = []
    cx, cz = center
    
    # Núcleo central: prédios em grade 3x3
    b_rows = int(math.sqrt(building_count)) or 3
    b_cols = (building_count + b_rows - 1) // b_rows
    b_offset_x = (b_rows - 1) * block_spacing / 2.0
    b_offset_z = (b_cols - 1) * block_spacing / 2.0
    for i in range(b_rows):
        for j in range(b_cols):
            if len(buildings) >= building_count:
                break
            x = cx + i * block_spacing - b_offset_x
            z = cz + j * block_spacing - b_offset_z
            w = random.uniform(1.4, 2.2)
            d = random.uniform(1.4, 2.2)
            h = random.uniform(4.5, 11.0)
            buildings.append(Building(x, z, w, d, h))
    
    # Quarteirões residenciais ao redor do centro
    house_positions = []
    ring_radius = (b_rows * block_spacing / 2.0) + block_spacing + street_width
    angles_per_ring = 8
    rings = (house_count + angles_per_ring - 1) // angles_per_ring
    for ring in range(rings):
        r = ring_radius + ring * (block_spacing + street_width)
        for a_idx in range(angles_per_ring):
            if len(house_positions) >= house_count:
                break
            angle = (a_idx / angles_per_ring) * 2.0 * math.pi + ring * 0.4
            hx = cx + math.cos(angle) * r + random.uniform(-1.0, 1.0)
            hz = cz + math.sin(angle) * r + random.uniform(-1.0, 1.0)
            house_positions.append((hx, hz))
    
    for hx, hz in house_positions:
        houses.append(create_house(hx, hz))
    
    # Ruas: grade principal
    village_extent = ring_radius + rings * (block_spacing + street_width) + 2.0
    street_len = village_extent * 2.0
    num_streets = int(village_extent / (block_spacing + street_width)) + 1
    for i in range(-num_streets, num_streets + 1):
        offset = i * (block_spacing + street_width)
        streets.append(Street(cx + offset, cz, street_width, street_len, direction='z'))
        streets.append(Street(cx, cz + offset, street_width, street_len, direction='x'))
    
    return buildings, houses, streets


class Street:
    def __init__(self, x, z, width, length, direction='x'):
        self.x = x
        self.z = z
        self.width = width
        self.length = length
        self.direction = direction
    
    def draw(self, shader: ShaderProgram):
        plane_mesh = get_shared_cube_mesh()
        shader.set_uniform_int("u_building_facade", 0)
        glBindTexture(GL_TEXTURE_2D, get_asphalt_texture())
        
        if self.direction == 'x':
            m = translate(self.x, 0.015, self.z) @ scale(self.length, 0.03, self.width)
        else:
            m = translate(self.x, 0.015, self.z) @ scale(self.width, 0.03, self.length)
        
        shader.set_uniform_mat4("u_model", m)
        shader.set_uniform_vec4("u_base_color", (0.22, 0.22, 0.24, 1.0))
        plane_mesh.draw()
        glBindTexture(GL_TEXTURE_2D, 0)


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
                
                noise_scale = 2.5
                noise_amount = 0.25
                
                n00 = perlin2d(math.cos(a0) * noise_scale, math.sin(a0) * noise_scale + b * 1.7)
                n10 = perlin2d(math.cos(a1) * noise_scale, math.sin(a1) * noise_scale + b * 1.7)
                n01 = perlin2d(math.cos(a0) * noise_scale, math.sin(a0) * noise_scale + (b + 1) * 1.7)
                n11 = perlin2d(math.cos(a1) * noise_scale, math.sin(a1) * noise_scale + (b + 1) * 1.7)
                
                r0_perturbed_a0 = r0 * (1.0 + n00 * noise_amount)
                r0_perturbed_a1 = r0 * (1.0 + n10 * noise_amount)
                r1_perturbed_a0 = r1 * (1.0 + n01 * noise_amount)
                r1_perturbed_a1 = r1 * (1.0 + n11 * noise_amount)

                c0, s0 = math.cos(a0), math.sin(a0)
                c1, s1 = math.cos(a1), math.sin(a1)

                p00 = [c0 * r0_perturbed_a0, y0, s0 * r0_perturbed_a0]
                p10 = [c1 * r0_perturbed_a1, y0, s1 * r0_perturbed_a1]
                p11 = [c1 * r1_perturbed_a1, y1, s1 * r1_perturbed_a1]
                p01 = [c0 * r1_perturbed_a0, y1, s0 * r1_perturbed_a0]

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
        
        self.falling = False
        self.fall_progress = 0.0
        self.fall_direction = 0.0  # graus
        self.fall_speed = 1.0 / 1.5  # completa em ~1.5s
        self._initial_falling = False

    def reset(self):
        self.falling = False
        self.fall_progress = 0.0
        self._initial_falling = False
    
    def update(self, earthquake, current_time, dt):
        """Verifica amplitude sísmica e atualiza queda."""
        if not self.falling:
            dx, dy, dz = earthquake.get_offset(self.x, self.z, current_time)
            amplitude = math.hypot(dx, dy, dz)
            if amplitude > 0.35:
                prob = min(0.8, (amplitude - 0.35) * 4.0) * dt * 3.0
                if random.random() < prob:
                    self.falling = True
                    self.fall_direction = random.uniform(0, 360)
        
        if self.falling and self.fall_progress < 1.0:
            self.fall_progress = min(1.0, self.fall_progress + self.fall_speed * dt)

    def draw(self, shader: ShaderProgram, earthquake, current_time: float):
        cyl_mesh = get_shared_cylinder_mesh()
        cone_mesh = get_shared_cone_mesh()
        
        dx_sway, _, dz_sway = earthquake.get_offset(self.x, self.z, current_time)
        
        # Ângulo de tombamento
        fall_angle = 0.0
        if self.falling:
            # Ease-in acelerado para simular gravidade
            t = self.fall_progress
            fall_angle = 90.0 * (t * t)  # quadrático
        
        # Direção de queda convertida em rotações X e Z
        fall_rad = math.radians(self.fall_direction)
        rot_x_angle = fall_angle * math.cos(fall_rad)
        rot_z_angle = fall_angle * math.sin(fall_rad)
        
        # Matriz de rotação de queda (pivô na base do tronco)
        m_fall_pivot = translate(self.x, 0.0, self.z)
        if fall_angle > 0.1:
            m_fall_pivot = m_fall_pivot @ rotate_x(rot_x_angle) @ rotate_z(rot_z_angle)
            # Desabilita sway quando caindo
            dx_sway, dz_sway = 0.0, 0.0
        
        # 1. Tronco
        m_trunk = m_fall_pivot @ scale(self.trunk_radius, self.trunk_height, self.trunk_radius)
        shader.set_uniform_mat4("u_model", m_trunk)
        shader.set_uniform_vec4("u_base_color", (0.38, 0.24, 0.12, 1.0))
        cyl_mesh.draw()
        
        # 2. Copa em camadas
        layer_h = self.foliage_height / self.foliage_layers
        for i in range(self.foliage_layers):
            t = i / self.foliage_layers
            y0 = self.trunk_height + t * self.foliage_height
            rad = self.foliage_radius * (1.0 - t * 0.55)
            sway = (y0 / self.total_height) * 1.8 if not self.falling else 0.0
            
            m_cone = m_fall_pivot @ translate(dx_sway * sway, y0, dz_sway * sway) @ scale(rad, layer_h * 1.3, rad)
            shader.set_uniform_mat4("u_model", m_cone)
            g = 0.38 + t * 0.12
            shader.set_uniform_vec4("u_base_color", (0.12, g, 0.16, 1.0))
            cone_mesh.draw()


def generate_forest(count, center, radius_range, avoid_zones=None, avoid_center=None, avoid_radius=0.0):
    trees = []
    cx, cz = center
    r_min, r_max = radius_range
    attempts = 0
    max_attempts = count * 12
    
    # Retrocompatibilidade com avoid_center/avoid_radius
    if avoid_zones is None:
        avoid_zones = []
    if avoid_center is not None and avoid_radius > 0:
        avoid_zones.append((avoid_center[0], avoid_center[1], avoid_radius))
    
    while len(trees) < count and attempts < max_attempts:
        attempts += 1
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(r_min, r_max)
        x = cx + math.cos(angle) * r
        z = cz + math.sin(angle) * r
        
        blocked = False
        if avoid_zones:
            for ax, az, ar in avoid_zones:
                if math.hypot(x - ax, z - az) < ar:
                    blocked = True
                    break
        if blocked:
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
