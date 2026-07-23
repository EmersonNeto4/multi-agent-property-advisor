import json
from typing import List, Dict, Optional, Tuple
from pathlib import Path

def load_portugal_locations() -> Dict:
    """
    Carrega o dataset de localizações de Portugal.
    
    Returns:
        Dicionário com metadata e lista de localizações
        
    Raises:
        FileNotFoundError: Se o ficheiro não existir
        json.JSONDecodeError: Se o JSON for inválido
    """

    data_path = Path(__file__).parent.parent / "data" / "portugal_locations.json"

    with open(data_path, "r", encoding="utf-8") as file:
        return json.load(file)
    
def get_all_locations() -> List[Dict]:
    """
    Retorna lista de todas as localizações disponíveis.
    
    Returns:
        Lista de dicionários com informação de cada localização
    """
    data = load_portugal_locations()
    return data['locations']


def filter_locations_by_region(nuts_ii: str) -> List[Dict]:
    """
    Filtra localizações por região NUTS II.
    
    Args:
        nuts_ii: Nome da região (ex: "Norte", "Centro", "Algarve")
        
    Returns:
        Lista de localizações na região especificada
    """
    locations = get_all_locations()
    return [loc for loc in locations if loc['nuts_ii'] == nuts_ii]


def filter_locations_by_characteristics(
    characteristics: List[str],
    min_matches: int = 1
) -> List[Dict]:
    """
    Filtra localizações que têm pelo menos min_matches das características especificadas.
    
    Args:
        characteristics: Lista de características desejadas (ex: ["costeiro", "tranquilo"])
        min_matches: Número mínimo de características que devem coincidir
        
    Returns:
        Lista de localizações que correspondem aos critérios
        
    Example:
        >>> locs = filter_locations_by_characteristics(["costeiro", "praia"], min_matches=2)
    """
    locations = get_all_locations()
    filtered = []
    
    for loc in locations:
        loc_chars = set(loc['characteristics'])
        search_chars = set(characteristics)
        matches = len(loc_chars.intersection(search_chars))
        
        if matches >= min_matches:
            filtered.append({
                **loc,
                'matches': matches  # Adicionar score de matches
            })
    
    # Ordenar por número de matches (descendente)
    filtered.sort(key=lambda x: x['matches'], reverse=True)
    return filtered


def find_location_by_name(name: str) -> Optional[Dict]:
    """
    Encontra uma localização pelo nome exato.
    
    Args:
        name: Nome da localização (ex: "Coimbra", "Porto")
        
    Returns:
        Dicionário com informação da localização ou None se não encontrar
    """
    locations = get_all_locations()
    
    # Procurar match exato (case-insensitive)
    name_lower = name.lower()
    for loc in locations:
        if loc['name'].lower() == name_lower:
            return loc
    
    return None


def find_locations_fuzzy(search_term: str) -> List[Dict]:
    """
    Procura localizações que contenham o termo de busca no nome.
    
    Args:
        search_term: Termo a procurar (ex: "Vila", "costa")
        
    Returns:
        Lista de localizações que correspondem
        
    Example:
        >>> locs = find_locations_fuzzy("Vila")  # Encontra "Vila Real", "Vila Nova de Gaia"
    """
    locations = get_all_locations()
    search_lower = search_term.lower()
    
    return [
        loc for loc in locations 
        if search_lower in loc['name'].lower()
    ]


def get_locations_by_population_range(
    min_population: int = 0,
    max_population: int = float('inf')
) -> List[Dict]:
    """
    Filtra localizações por intervalo de população.
    
    Args:
        min_population: População mínima
        max_population: População máxima
        
    Returns:
        Lista de localizações no intervalo especificado
    """
    locations = get_all_locations()
    
    return [
        loc for loc in locations
        if min_population <= loc['population'] <= max_population
    ]


def get_candidate_locations(
    location_hint: Optional[str] = None,
    environment_keywords: Optional[List[str]] = None,
    max_results: int = 10
) -> List[Dict]:
    """
    Obtém lista de localizações candidatas baseadas em hints do utilizador.
    
    Esta é a função principal para o Location Agent usar.
    
    Args:
        location_hint: Nome ou região mencionada pelo utilizador (ex: "Coimbra", "Norte")
        environment_keywords: Palavras-chave do ambiente desejado (ex: ["tranquilo", "costeiro"])
        max_results: Número máximo de candidatos a retornar
        
    Returns:
        Lista de localizações candidatas ordenadas por relevância
        
    Example:
        >>> candidates = get_candidate_locations(
        ...     location_hint="Lisboa",
        ...     environment_keywords=["costeiro", "vibrante"],
        ...     max_results=5
        ... )
    """
    candidates = []
    
    # Caso 1: Utilizador especificou localização
    if location_hint:
        # Tentar match exato primeiro
        exact_match = find_location_by_name(location_hint)
        if exact_match:
            return [exact_match]
        
        # Tentar match fuzzy
        fuzzy_matches = find_locations_fuzzy(location_hint)
        if fuzzy_matches:
            candidates.extend(fuzzy_matches)
        
        # Tentar match por região NUTS II
        regions = ["Norte", "Centro", "Área Metropolitana de Lisboa", "Alentejo", "Algarve"]
        for region in regions:
            if location_hint.lower() in region.lower():
                candidates.extend(filter_locations_by_region(region))
                break
    
    # Caso 2: Filtrar por características de ambiente
    if environment_keywords and not candidates:
        candidates = filter_locations_by_characteristics(
            environment_keywords,
            min_matches=1
        )
    
    # Caso 3: Sem hints específicos - retornar localizações principais
    if not candidates:
        all_locs = get_all_locations()
        # Priorizar cidades maiores
        candidates = sorted(all_locs, key=lambda x: x['population'], reverse=True)
    
    # Remover duplicados mantendo ordem
    seen = set()
    unique_candidates = []
    for loc in candidates:
        if loc['id'] not in seen:
            seen.add(loc['id'])
            unique_candidates.append(loc)
    
    # Limitar ao número máximo de resultados
    return unique_candidates[:max_results]


def get_location_coordinates(location_id: str) -> Optional[Tuple[float, float]]:
    """
    Obtém coordenadas de uma localização pelo ID.
    
    Args:
        location_id: ID da localização (ex: "pt_centro_coimbra")
        
    Returns:
        Tupla (latitude, longitude) ou None se não encontrar
    """
    locations = get_all_locations()
    
    for loc in locations:
        if loc['id'] == location_id:
            coords = loc['coordinates']
            return (coords['latitude'], coords['longitude'])
    
    return None