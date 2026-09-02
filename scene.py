"""
Objetos visuais da cena: o chão (uma grade que ondula), os prédios
(caixas empilhadas em fatias, pra simular o efeito de chicote), a
montanha (cone em camadas, nevada no topo) e as árvores (tronco +
copa, que também balançam levemente no terremoto).
"""
 
import math
import random
from OpenGL.GL import (
    glBegin, glEnd, glVertex3f, glColor3f, glPushMatrix, glPopMatrix,
    glTranslatef, glRotatef, GL_QUADS, GL_QUAD_STRIP,
)
from OpenGL.GLU import gluNewQuadric, gluCylinder
 
 
def _draw_box(width, height, depth, y_offset=0.0):
    """Desenha uma caixa (prédio ou fatia de prédio) centrada no eixo X/Z."""
    hw, hd = width / 2.0, depth / 2.0
    y0, y1 = y_offset, y_offset + height
 
    glBegin(GL_QUADS)
    # topo
    glVertex3f(-hw, y1, -hd); glVertex3f(hw, y1, -hd)
    glVertex3f(hw, y1, hd);   glVertex3f(-hw, y1, hd)
    # base
    glVertex3f(-hw, y0, -hd); glVertex3f(-hw, y0, hd)
    glVertex3f(hw, y0, hd);   glVertex3f(hw, y0, -hd)
    # frente
    glVertex3f(-hw, y0, hd); glVertex3f(hw, y0, hd)
    glVertex3f(hw, y1, hd);  glVertex3f(-hw, y1, hd)
    # trás
    glVertex3f(-hw, y0, -hd); glVertex3f(-hw, y1, -hd)
    glVertex3f(hw, y1, -hd);  glVertex3f(hw, y0, -hd)
    # esquerda
    glVertex3f(-hw, y0, -hd); glVertex3f(-hw, y0, hd)
    glVertex3f(-hw, y1, hd);  glVertex3f(-hw, y1, -hd)
    # direita
    glVertex3f(hw, y0, -hd); glVertex3f(hw, y1, -hd)
    glVertex3f(hw, y1, hd);  glVertex3f(hw, y0, hd)
    glEnd()
 
 
class Building:
    # dano acumulado necessário pra começar a desabar (varia por prédio)
    RESISTANCE_RANGE = (2.5, 6.0)
    COLLAPSE_DURATION = 2.5   # segundos que a animação de queda leva
    DAMAGE_MULTIPLIER = 3.0  # converte a amplitude do tremor em "dano por segundo"
 
    def __init__(self, x, z, width, depth, height, slices=6):
        self.x = x
        self.z = z
        self.width = width
        self.depth = depth
        self.height = height
        self.slices = slices  # nº de segmentos verticais p/ o efeito de chicote
        self.color = (
            random.uniform(0.55, 0.85),
            random.uniform(0.55, 0.85),
            random.uniform(0.60, 0.90),
        )
 
        # --- estado de dano / colapso ---
        self.resistance = random.uniform(*self.RESISTANCE_RANGE)
        self.damage = 0.0
        self.collapsing = False
        self.collapse_progress = 0.0  # 0 = intacto, 1 = totalmente desabado
        self.lean_angle = random.uniform(-25.0, 25.0)  # direção do tombamento
        self.rubble_color = (0.40, 0.38, 0.36)
 
    def update(self, earthquake, current_time, dt):
        """
        Acumula dano com base na intensidade do tremor no local do prédio.
        Chamar uma vez por frame, antes de desenhar.
        """
        if self.collapse_progress >= 1.0:
            return  # já virou escombro, não precisa mais calcular nada
 
        dx, dy, dz = earthquake.get_offset(self.x, self.z, current_time)
        amplitude = math.sqrt(dx * dx + dy * dy + dz * dz)
 
        if not self.collapsing:
            self.damage += amplitude * dt * self.DAMAGE_MULTIPLIER
            if self.damage >= self.resistance:
                self.collapsing = True
        else:
            self.collapse_progress = min(
                1.0, self.collapse_progress + dt / self.COLLAPSE_DURATION
            )
 
    def _current_color(self):
        if self.collapse_progress <= 0.0:
            return self.color
        t = self.collapse_progress
        return tuple(
            self.color[i] * (1 - t) + self.rubble_color[i] * t
            for i in range(3)
        )
 
    def draw(self, earthquake, current_time):
        # prédio intacto = altura cheia; escombro = ~12% da altura original
        height_factor = 1.0 - self.collapse_progress * 0.88
        effective_height = self.height * height_factor
        color = self._current_color()
 
        glPushMatrix()
        glTranslatef(self.x, 0.0, self.z)
        if self.collapse_progress > 0.0:
            glRotatef(self.lean_angle * self.collapse_progress, 0, 0, 1)
 
        dx, _, dz = earthquake.get_offset(self.x, self.z, current_time)
        # escombro já não balança mais com o tremor
        sway_scale = 1.0 - self.collapse_progress
 
        for i in range(self.slices):
            t0 = i / self.slices
            t1 = (i + 1) / self.slices
            y0 = t0 * effective_height
            slice_height = (t1 - t0) * effective_height
            sway = t1 * 2.0 * sway_scale
 
            glPushMatrix()
            glTranslatef(dx * sway, 0.0, dz * sway)
            glColor3f(*color)
            _draw_box(self.width, slice_height, self.depth, y_offset=y0)
            glPopMatrix()
 
        glPopMatrix()
 
 
class Ground:
    """Chão em grade que ondula fisicamente com a passagem da onda sísmica."""
 
    def __init__(self, size=40, divisions=24):
        self.size = size
        self.divisions = divisions
 
    def draw(self, earthquake, current_time):
        step = self.size / self.divisions
        half = self.size / 2.0
 
        glColor3f(0.35, 0.55, 0.35)
        for i in range(self.divisions):
            glBegin(GL_QUAD_STRIP)
            for j in range(self.divisions + 1):
                for xi in (i, i + 1):
                    x = -half + xi * step
                    z = -half + j * step
                    _, dy, _ = earthquake.get_offset(x, z, current_time)
                    glVertex3f(x, dy, z)
            glEnd()
 
 
def generate_city(rows=5, cols=5, spacing=5.0):
    """Cria uma grade de prédios com tamanhos levemente variados."""
    buildings = []
    offset = (rows - 1) * spacing / 2.0
    for i in range(rows):
        for j in range(cols):
            x = i * spacing - offset
            z = j * spacing - offset
            width = random.uniform(1.2, 2.0)
            depth = random.uniform(1.2, 2.0)
            height = random.uniform(3.0, 9.0)
            buildings.append(Building(x, z, width, depth, height))
    return buildings
 
 
class RockDebris:
    """Um pedaço de rocha que se desprendeu da montanha e cai/rola no chão."""
 
    GRAVITY = -9.8
 
    def __init__(self, x, y, z, vx, vy, vz, size=0.4,
                 color=(0.42, 0.38, 0.34), lifetime=5.0):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.size = size
        self.color = color
        self.lifetime = lifetime
        self.age = 0.0
 
    @property
    def alive(self):
        return self.age < self.lifetime
 
    def update(self, dt):
        self.vy += self.GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.age += dt
 
        # "chão": para de cair e perde velocidade (fricção simples)
        if self.y < 0.0:
            self.y = 0.0
            self.vy = 0.0
            self.vx *= 0.85
            self.vz *= 0.85
 
    def draw(self):
        glPushMatrix()
        glTranslatef(self.x, self.y, self.z)
        glColor3f(*self.color)
        _draw_box(self.size, self.size, self.size, y_offset=0.0)
        glPopMatrix()
 
 
class Mountain:
    """
    Montanha desenhada como um cone em camadas (usando GLU): cada
    camada é um pedaço de cone que vai afinando conforme sobe, e a
    cor muda de rocha (cinza/marrom) para neve (branco) a partir de
    uma certa altura. Durante tremores fortes, solta pedras que caem
    e rolam encosta abaixo.
    """
 
    def __init__(self, x, z, base_radius=12.0, height=22.0,
                 snow_start=0.62, bands=8, slices=28):
        self.x = x
        self.z = z
        self.base_radius = base_radius
        self.height = height
        self.snow_start = snow_start  # fração da altura onde a neve começa
        self.bands = bands            # nº de "fatias" verticais do cone
        self.slices = slices          # resolução radial (quanto mais, mais redondo)
        self.quadric = gluNewQuadric()
 
        # --- desmoronamento ---
        self.shake_threshold = 0.25    # amplitude mínima do tremor pra soltar pedras
        self.spawn_rate = 8.0          # "tentativas" de soltar pedra por segundo, no pico
        self.debris = []
 
    def _color_for_height(self, t):
        """t = fração da altura (0 na base, 1 no pico)."""
        if t >= self.snow_start:
            return (0.95, 0.96, 0.98)  # neve
        return (0.42, 0.38, 0.34)      # rocha
 
    def update(self, earthquake, current_time, dt):
        """Atualiza as pedras existentes e, se o tremor for forte o bastante
        neste ponto, pode soltar pedras novas da encosta."""
        dx, dy, dz = earthquake.get_offset(self.x, self.z, current_time)
        amplitude = math.sqrt(dx * dx + dy * dy + dz * dz)
 
        if amplitude > self.shake_threshold:
            excess = amplitude - self.shake_threshold
            spawn_probability = min(0.9, excess * self.spawn_rate) * dt * 10.0
            if random.random() < spawn_probability:
                self._spawn_rock()
 
        for rock in self.debris:
            rock.update(dt)
        self.debris = [r for r in self.debris if r.alive]
 
    def _spawn_rock(self):
        """Escolhe um ponto aleatório na encosta e solta uma pedra dali."""
        t = random.uniform(0.2, 0.95)  # altura relativa na montanha
        radius = self.base_radius * (1 - t) ** 1.3
        angle = random.uniform(0, 2 * math.pi)
 
        rx = self.x + math.cos(angle) * radius
        rz = self.z + math.sin(angle) * radius
        ry = t * self.height
 
        # velocidade inicial: cai e escorrega um pouco pra fora da encosta
        outward_speed = random.uniform(1.0, 3.0)
        vx = math.cos(angle) * outward_speed
        vz = math.sin(angle) * outward_speed
        vy = random.uniform(-1.0, 0.5)
 
        color = (0.95, 0.96, 0.98) if t >= self.snow_start else (0.42, 0.38, 0.34)
        self.debris.append(RockDebris(
            rx, ry, rz, vx, vy, vz,
            size=random.uniform(0.3, 0.7),
            color=color,
        ))
 
    def draw(self):
        glPushMatrix()
        glTranslatef(self.x, 0.0, self.z)
        # gluCylinder desenha ao longo do eixo Z local; giramos -90° em X
        # pra ele apontar "pra cima" (eixo Y), que é a nossa altura.
        glRotatef(-90, 1, 0, 0)
 
        band_height = self.height / self.bands
        for i in range(self.bands):
            t0 = i / self.bands
            t1 = (i + 1) / self.bands
            # expoente > 1 deixa a base mais larga e o topo afinando rápido,
            # dando um perfil mais parecido com uma montanha de verdade
            r0 = self.base_radius * (1 - t0) ** 1.3
            r1 = self.base_radius * (1 - t1) ** 1.3
 
            glColor3f(*self._color_for_height(t1))
            glPushMatrix()
            glTranslatef(0.0, 0.0, t0 * self.height)
            gluCylinder(self.quadric, r0, r1, band_height, self.slices, 1)
            glPopMatrix()
 
        glPopMatrix()
 
        # as pedras já caídas ficam em coordenadas de mundo (fora do
        # glRotatef acima, que era só pra desenhar o cone corretamente)
        for rock in self.debris:
            rock.draw()
 
 
class Tree:
    """Árvore simples: tronco (cilindro fino) + copa (cones empilhados)."""
 
    def __init__(self, x, z, trunk_height=1.5, trunk_radius=0.15,
                 foliage_layers=3, foliage_height=2.5, foliage_radius=1.0):
        self.x = x
        self.z = z
        self.trunk_height = trunk_height
        self.trunk_radius = trunk_radius
        self.foliage_layers = foliage_layers
        self.foliage_height = foliage_height
        self.foliage_radius = foliage_radius
        self.total_height = trunk_height + foliage_height
        self.quadric = gluNewQuadric()
 
    def draw(self, earthquake, current_time):
        dx, _, dz = earthquake.get_offset(self.x, self.z, current_time)
 
        glPushMatrix()
        glTranslatef(self.x, 0.0, self.z)
 
        # tronco (fica praticamente parado, perto da base)
        glColor3f(0.40, 0.26, 0.13)
        glPushMatrix()
        glRotatef(-90, 1, 0, 0)
        gluCylinder(self.quadric, self.trunk_radius,
                    self.trunk_radius * 0.8, self.trunk_height, 8, 1)
        glPopMatrix()
 
        # copa em camadas: quanto mais alta a camada, mais ela balança
        glColor3f(0.16, 0.45, 0.20)
        layer_height = self.foliage_height / self.foliage_layers
        for i in range(self.foliage_layers):
            t0 = i / self.foliage_layers
            y0 = self.trunk_height + t0 * self.foliage_height
            radius = self.foliage_radius * (1 - t0 * 0.6)
 
            sway = (y0 / self.total_height) * 1.5
            glPushMatrix()
            glTranslatef(dx * sway, y0, dz * sway)
            glRotatef(-90, 1, 0, 0)
            gluCylinder(self.quadric, radius, radius * 0.15,
                        layer_height * 1.4, 10, 1)
            glPopMatrix()
 
        glPopMatrix()
 
 
def generate_forest(count, center, radius_range, avoid_center=None, avoid_radius=0.0):
    """
    Espalha árvores em um anel ao redor de `center` (tipicamente a base
    da montanha), entre radius_range[0] e radius_range[1] de distância.
    Se avoid_center/avoid_radius forem passados, pula posições muito
    perto dali (útil pra não nascer árvore em cima da cidade).
    """
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
            trunk_height=random.uniform(1.2, 1.8),
            trunk_radius=random.uniform(0.12, 0.20),
            foliage_layers=random.randint(2, 4),
            foliage_height=random.uniform(2.0, 3.2),
            foliage_radius=random.uniform(0.8, 1.3),
        ))
 
    return trees