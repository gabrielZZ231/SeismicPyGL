"""
Lógica pura do terremoto: onde ele começa, como se propaga e como
decai com o tempo e a distância. Não sabe nada de OpenGL — só
matemática. Isso deixa fácil testar/ajustar a física sem mexer no
código de desenho.
"""

import math
import random


class EarthquakeSimulator:
    """
    Modela o terremoto como uma onda circular que se espalha a partir
    de um epicentro (x, z), com amplitude que diminui com a distância
    percorrida e com o tempo desde que a onda passou por aquele ponto.
    """

    def __init__(self):
        self.active = False
        self.epicenter = (0.0, 0.0)
        self.start_time = 0.0
        self.magnitude = 1.0        # amplitude inicial do tremor
        self.wave_speed = 6.0       # unidades de cena por segundo
        self.frequency = 3.0        # Hz da vibração
        self.damping = 0.35         # decaimento por segundo (no tempo)
        self.spatial_falloff = 0.08  # decaimento por unidade de distância

    def trigger(self, current_time, epicenter=None, magnitude=1.4):
        """Inicia um novo terremoto. Se epicenter=None, sorteia um ponto."""
        self.epicenter = epicenter or (
            random.uniform(-15, 15), random.uniform(-15, 15)
        )
        self.magnitude = magnitude
        self.start_time = current_time
        self.active = True

    def stop(self):
        self.active = False

    def get_offset(self, x, z, current_time):
        """
        Retorna o deslocamento (dx, dy, dz) que o ponto (x, z) deve
        sofrer no instante current_time. Devolve (0, 0, 0) se não há
        terremoto ativo ou se a onda ainda não chegou nesse ponto.
        """
        if not self.active:
            return 0.0, 0.0, 0.0

        elapsed = current_time - self.start_time
        if elapsed < 0:
            return 0.0, 0.0, 0.0

        dist = math.hypot(x - self.epicenter[0], z - self.epicenter[1])

        # a onda demora pra "chegar" em pontos distantes do epicentro
        arrival = dist / self.wave_speed
        local_t = elapsed - arrival
        if local_t < 0:
            return 0.0, 0.0, 0.0

        temporal_decay = math.exp(-self.damping * local_t)
        spatial_decay = math.exp(-self.spatial_falloff * dist)
        amplitude = self.magnitude * temporal_decay * spatial_decay

        if amplitude < 0.001:
            return 0.0, 0.0, 0.0

        phase = 2 * math.pi * self.frequency * local_t
        dy = amplitude * math.sin(phase)
        dx = amplitude * 0.4 * math.sin(phase * 0.6 + dist)
        dz = amplitude * 0.4 * math.cos(phase * 0.6 + dist)
        return dx, dy, dz
