import math
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula a distância real entre dois pontos geográficos usando a fórmula de Haversine.
    
    Esta é a distância REAL ao longo da superfície da Terra (great-circle distance).
    Usada como custo g(n) no A*.
    
    Args:
        lat1, lon1: Coordenadas do ponto 1 (latitude, longitude em graus)
        lat2, lon2: Coordenadas do ponto 2 (latitude, longitude em graus)
        
    Returns:
        Distância em quilómetros
    """
    # Raio da Terra em km
    R = 6371.0
    
    # Converter graus para radianos
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Diferenças
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Fórmula de Haversine
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    
    return distance

def euclidean_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula distância Euclidiana entre duas coordenadas.
    
    Esta é uma APROXIMAÇÃO que é sempre ≤ distância real (Haversine).
    Usada como heurística h(n) no A* (admissível).
    
    Args:
        lat1, lon1: Coordenadas do ponto 1
        lat2, lon2: Coordenadas do ponto 2
        
    Returns:
        Distância aproximada em km
    """
    # Converter graus para km aproximadamente
    # 1 grau de latitude ≈ 111 km
    # 1 grau de longitude ≈ 111 km * cos(latitude)
    
    lat_diff = (lat2 - lat1) * 111
    lon_diff = (lon2 - lon1) * 111 * math.cos(math.radians((lat1 + lat2) / 2))
    
    return math.sqrt(lat_diff**2 + lon_diff**2)

def find_locations_within_radius(
    center_lat: float,
    center_lon: float,
    locations: List[Dict],
    radius_km: float
) -> List[Dict]:
    """
    Encontra todas as localizações dentro de um raio (em km) de um ponto central.
    
    Args:
        center_lat, center_lon: Coordenadas do centro
        locations: Lista de localizações com 'coordinates' → {'latitude', 'longitude'}
        radius_km: Raio de busca em km
        
    Returns:
        Lista de localizações dentro do raio, com distância adicionada
    """
    results = []
    
    for location in locations:
        coords = location.get('coordinates', {})
        lat = coords.get('latitude')
        lon = coords.get('longitude')
        
        if lat and lon:
            distance = haversine_distance(center_lat, center_lon, lat, lon)
            
            if distance <= radius_km:
                location_copy = location.copy()
                location_copy['distance_to_center_km'] = round(distance, 2)
                results.append(location_copy)
    
    # Ordenar por distância (mais próximo primeiro)
    results.sort(key=lambda x: x['distance_to_center_km'])
    
    return results