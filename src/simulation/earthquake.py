"""
Lógica do simulador de terremotos (física e parâmetros da onda sísmica).
Fornece parâmetros para os shaders da GPU e para cálculos na CPU.
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
        self.richter_magnitude = 0.0
        self.max_richter = 0.0
        self.magnitude = 0.0        # amplitude da vibração mecânica
        self.wave_speed = 10.0      # unidades de cena por segundo
        self.frequency = 2.5        # Hz da vibração
        self.damping = 0.25         # decaimento temporal
        self.spatial_falloff = 0.05 # decaimento espacial

    def trigger(self, current_time: float = 0.0, epicenter=None, magnitude: float = 5.0):
        """Inicia um novo terremoto com magnitude Richter e epicentro."""
        self.epicenter = epicenter or (
            random.uniform(-10, 10), random.uniform(-10, 10)
        )
        self.richter_magnitude = float(magnitude)
        self.max_richter = max(self.max_richter, float(magnitude))
        # Escala a amplitude da deformação visual com a escala Richter
        self.magnitude = max(0.4, float(magnitude) * 0.42)
        if self.richter_magnitude >= 7.0:
            self.damping = 0.15
        else:
            self.damping = 0.25
        self.start_time = float(current_time)
        self.active = True

    def get_crack_intensity(self) -> float:
        """Retorna a intensidade das rachaduras no solo e asfalto [0.0, 1.0]."""
        effective_mag = self.max_richter if self.max_richter > 0 else self.richter_magnitude
        if effective_mag < 3.8:
            return 0.0
        return min(1.0, (effective_mag - 3.8) / 4.2)

    def stop(self):
        self.active = False
        self.magnitude = 0.0
        self.richter_magnitude = 0.0
        self.damping = 0.25

    def reset(self):
        """Reset total da simulação sísmica e das fendas no asfalto/terreno."""
        self.stop()
        self.max_richter = 0.0

    def get_offset(self, x: float, z: float, current_time: float):
        """
        Retorna o deslocamento (dx, dy, dz) que o ponto (x, z) sofre
        no instante current_time. Devolve (0, 0, 0) se não há tremor.
        """
        if not self.active:
            return 0.0, 0.0, 0.0

        elapsed = current_time - self.start_time
        if elapsed < 0:
            return 0.0, 0.0, 0.0

        dist = math.hypot(x - self.epicenter[0], z - self.epicenter[1])
        arrival = dist / self.wave_speed
        local_t = elapsed - arrival
        if local_t < 0:
            return 0.0, 0.0, 0.0

        temporal_decay = math.exp(-self.damping * local_t)
        spatial_decay = math.exp(-self.spatial_falloff * dist)
        amplitude = self.magnitude * temporal_decay * spatial_decay

        if amplitude < 0.005:
            return 0.0, 0.0, 0.0

        phase = 2.0 * math.pi * self.frequency * local_t
        dy = amplitude * math.sin(phase)
        dx = amplitude * 0.35 * math.sin(phase * 0.7 + dist)
        dz = amplitude * 0.35 * math.cos(phase * 0.7 + dist)
        return dx, dy, dz
