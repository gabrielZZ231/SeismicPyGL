"""Geradores procedurais de povoados e cidades (generate_village e generate_city)."""

import math
import random
from .building import Building, create_house
from .street import Street
from .light_pole import LightPole


def generate_village(center=(0.0, 0.0), building_count=9, house_count=24, block_spacing=6.0, street_width=2.5):
    """Gera uma vila mista com núcleo de prédios, quarteirões de casas, ruas e postes de iluminação."""
    buildings = []
    houses = []
    streets = []
    light_poles = []
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
        st_z = Street(cx + offset, cz, street_width, street_len, direction="z")
        st_x = Street(cx, cz + offset, street_width, street_len, direction="x")
        streets.append(st_z)
        streets.append(st_x)

        # Distribui postes ao longo das calçadas
        lp_spacing = 16.0
        lp_count = max(2, int(street_len / lp_spacing))
        for k in range(lp_count):
            along = -street_len * 0.5 + (k + 0.5) * (street_len / lp_count)
            side = 1.0 if k % 2 == 0 else -1.0
            curb_dist = street_width * 0.72 * side

            lp_z = LightPole(cx + offset + curb_dist, cz + along, street_direction="z", side=side)
            light_poles.append(lp_z)

            lp_x = LightPole(cx + along, cz + offset + curb_dist, street_direction="x", side=side)
            light_poles.append(lp_x)

    return buildings, houses, streets, light_poles


def generate_city(rows=5, cols=5, spacing=5.5):
    """Compatibilidade retroativa: gera cidade simples."""
    return generate_village(center=(0.0, 0.0), building_count=rows * cols)[0]
