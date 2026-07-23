from models import UserPreferences
from tools import (
    get_candidate_locations,
    get_weather_data,
    analyze_weather_with_llm
)
from typing import List, Dict, Optional
import asyncio


async def evaluate_location(
    location: Dict,
    environment_type: Optional[str],
    model_client
) -> Dict:
    """
    Avalia uma localização e calcula score de adequação.
    
    Args:
        location: Dicionário com informação da localização
        environment_type: Tipo de ambiente desejado pelo utilizador
        model_client: Cliente do modelo LLM
        
    Returns:
        Dicionário com localização e scores detalhados
    """
    # Obter coordenadas
    coords = location['coordinates']
    lat, lon = coords['latitude'], coords['longitude']
    
    # Score base a partir das características do dataset
    characteristics_score = 0.5
    
    # Se o utilizador especificou environment_type, avaliar match de características
    if environment_type:
        env_keywords = environment_type.lower().split()
        loc_characteristics = [c.lower() for c in location['characteristics']]
        
        # Contar quantas keywords aparecem nas características
        matches = sum(1 for keyword in env_keywords if any(keyword in char for char in loc_characteristics))
        
        if matches > 0:
            characteristics_score = min(0.5 + (matches * 0.15), 1.0)
    
    # Obter dados climáticos e avaliar com LLM
    climate_score = 0.5
    weather_summary = "Dados climáticos não disponíveis"
    
    try:
        weather_data = await get_weather_data(lat, lon)
        weather_summary = f"Temp: {weather_data['current']['temperature_2m']}°C, Precip: {weather_data['current']['precipitation']}mm"
        
        if environment_type:
            climate_score = await analyze_weather_with_llm(
                weather_data,
                environment_type,
                model_client
            )
    except Exception as e:
        print(f" Erro ao obter clima para {location['name']}: {e}")
    
    # Score final é a média ponderada
    # 60% clima, 40% características
    final_score = (climate_score * 0.6) + (characteristics_score * 0.4)
    
    return {
        'location_id': location['id'],
        'name': location['name'],
        'nuts_ii': location['nuts_ii'],
        'nuts_iii': location['nuts_iii'],
        'coordinates': location['coordinates'],
        'characteristics': location['characteristics'],
        'population': location['population'],
        'climate_score': round(climate_score, 3),
        'characteristics_score': round(characteristics_score, 3),
        'final_score': round(final_score, 3),
        'weather_summary': weather_summary
    }

async def find_locations_wrapper(
    model_client,
    location: Optional[str] = None,
    location_hint: Optional[str] = None,
    environment_type: Optional[str] = None,
    budget: Optional[float] = None,
    rooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
    area_m2: Optional[float] = None,
    operation: Optional[str] = None,
    property_type: Optional[str] = None,
    parking: Optional[bool] = None,
    outdoor_space: Optional[bool] = None,
    proximity_services: Optional[str] = None,
    skip_location_agent: Optional[bool] = None,
    additional_notes: Optional[str] = None,
    top_n: Optional[int] = None
) -> List[Dict]:
    """
    Wrapper para find_best_locations que aceita todos os parâmetros do Planner.
    
    Extrai apenas os parâmetros relevantes (location, environment_type, top_n)
    e ignora os outros (budget, rooms, etc.) que são para outros agentes.
    
    Args:
        model_client: Cliente do modelo LLM
        location: Nome da localização
        location_hint: Hint alternativo de localização
        environment_type: Tipo de ambiente desejado
        top_n: Número de localizações a retornar
        ... (outros parâmetros ignorados)
        
    Returns:
        Lista simplificada de localizações: [{'name': '...', 'score': ...}]
    """
    
    # Determinar location
    final_location = location or location_hint
    
    # Environment type default
    final_environment = environment_type if environment_type else "equilibrado"
    
    # Top N validado
    final_top_n = 5
    if top_n is not None and isinstance(top_n, int) and top_n > 0:
        final_top_n = top_n
    
    print(f"\n Location Search - Parâmetros recebidos:")
    print(f"   Location: {final_location}")
    print(f"   Environment: {final_environment}")
    print(f"   Top N: {final_top_n}")
    
    # Verificar skip
    if skip_location_agent:
        print(f"    skip_location_agent=True - Usando location diretamente")
        return [{'name': final_location}]
    
    # Chamar função real
    try:
        result = await find_best_locations(
            location_hint=final_location,
            environment_type=final_environment,
            top_n=final_top_n,
            model_client=model_client
        )
        
        # ==========================================
        # SIMPLIFICAR RESULTADO (CRÍTICO!)
        # Só passar 'name' e 'score' para evitar truncamento
        # ==========================================
        simplified_result = []
        for loc in result:
            simplified_result.append({
                'name': loc.get('name'),
                'score': loc.get('final_score', 0)
            })
        
        print(f"\n Location Search - Retornando {len(simplified_result)} localizações:")
        for i, loc in enumerate(simplified_result, 1):
            print(f"   #{i}: {loc['name']} (score: {loc['score']:.2f})")
        
        return simplified_result
        
    except Exception as e:
        print(f"\n ERRO no Location Search: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback
        return [{'name': final_location or 'Portugal'}]

async def find_best_locations(
    location_hint: Optional[str] = None,
    environment_type: Optional[str] = None,
    top_n: int = 5,
    model_client = None
) -> List[Dict]:
    """
    Encontra as melhores localizações baseadas nas preferências do utilizador.
    
    Args:
        location_hint: Localização mencionada pelo utilizador (ex: "Lisboa", "Norte")
        environment_type: Tipo de ambiente desejado (ex: "tranquilo e perto da praia")
        top_n: Número de localizações a retornar (default: 5)
        model_client: Cliente do modelo LLM (necessário para avaliação climática)
        
    Returns:
        Lista de dicionários com localizações recomendadas:
        [
            {
                'location_id': str,
                'name': str,
                'coordinates': dict,
                'final_score': float,
                'climate_score': float,
                'characteristics_score': float,
                ...
            },
            ...
        ]
    """
    print(f"\n{'='*60}")
    print(f" Location Search: Iniciando busca de regiões")
    print(f"{'='*60}")
    
    if location_hint:
        print(f" Localização mencionada: {location_hint}")
    if environment_type:
        print(f" Ambiente desejado: {environment_type}")
    
    # 1. Obter candidatos do dataset
    print(f"\n Procurando candidatos no dataset...")
    
    # Extrair keywords do environment_type para filtro inicial
    env_keywords = []
    if environment_type:
        env_lower = environment_type.lower()
        # Mapear alguns termos comuns para características do dataset
        keyword_mapping = {
            'tranquilo': ['tranquilo'],
            'calmo': ['tranquilo'],
            'sossegado': ['tranquilo'],
            'vibrante': ['vibrante', 'urbano'],
            'animado': ['vibrante', 'urbano'],
            'movimentado': ['vibrante', 'urbano'],
            'praia': ['costeiro', 'praia'],
            'mar': ['costeiro'],
            'costa': ['costeiro'],
            'costeiro': ['costeiro'],
            'natureza': ['natureza'],
            'verde': ['natureza'],
            'rural': ['natureza', 'tranquilo'],
            'montanha': ['montanha'],
            'serra': ['montanha'],
            'histórico': ['histórico'],
            'cultural': ['cultural', 'histórico'],
            'universitário': ['universitário', 'jovem']
        }
        
        for term, chars in keyword_mapping.items():
            if term in env_lower:
                env_keywords.extend(chars)
        
        # Remover duplicados
        env_keywords = list(set(env_keywords))
    
    candidates = get_candidate_locations(
        location_hint=location_hint,
        environment_keywords=env_keywords if env_keywords else None,
        max_results=min(20, top_n * 4)  # Avaliar 4x mais candidatos
    )
    
    print(f" Encontrados {len(candidates)} candidatos para avaliar")
    
    # 2. Avaliar cada candidato
    print(f"\ Avaliando candidatos...")
    evaluated = []
    
    for i, candidate in enumerate(candidates, 1):
        print(f"  [{i}/{len(candidates)}] Avaliando {candidate['name']}...")
        result = await evaluate_location(candidate, environment_type, model_client)
        evaluated.append(result)
        await asyncio.sleep(0.3)  # Pequena pausa
    
    # 3. Ordenar por score final (melhor primeiro)
    evaluated.sort(key=lambda x: x['final_score'], reverse=True)
    
    # 4. Selecionar top N
    top_locations = evaluated[:top_n]
    
    print(f"\n Top {len(top_locations)} localizações selecionadas!")
    for i, loc in enumerate(top_locations, 1):
        print(f"  #{i} {loc['name']}: {loc['final_score']:.2f}")
    
    # 5. Retornar dados estruturados
    return top_locations