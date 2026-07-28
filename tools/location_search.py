from models import UserPreferences
from tools import (
    get_candidate_locations,
    get_all_locations,
    get_weather_data,
    analyze_weather_with_llm
)
from tools.semantic_search import query as semantic_query
from typing import List, Dict, Optional
import asyncio

# Tem de bater com o default de environment_type em find_locations_wrapper
# (agents/location.py chama-o sem environment_type quando o utilizador não
# especifica um). Usado só para desligar a pesquisa semântica nesse caso -
# ver o guard em find_best_locations. analyze_weather_with_llm continua a
# receber este valor tal como antes desta fase (não mexe na análise climática).
NO_PREFERENCE_SENTINEL = "equilibrado"


async def evaluate_location(
    location: Dict,
    environment_type: Optional[str],
    model_client,
    characteristics_score: float = 0.5
) -> Dict:
    """
    Avalia uma localização e calcula score de adequação.

    Args:
        location: Dicionário com informação da localização
        environment_type: Tipo de ambiente desejado pelo utilizador
        model_client: Cliente do modelo LLM
        characteristics_score: Similaridade semântica pré-calculada entre
            environment_type e a descrição da localização (ver
            tools/semantic_search.py), em [0, 1]. Default 0.5 quando não
            há environment_type ou quando o retrieval semântico não está
            disponível (ver find_best_locations) - mantém o score neutro
            que já existia antes desta fase.

    Returns:
        Dicionário com localização e scores detalhados
    """
    # Obter coordenadas
    coords = location['coordinates']
    lat, lon = coords['latitude'], coords['longitude']

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

    max_candidates = min(20, top_n * 4)  # Avaliar 4x mais candidatos

    # Similaridade semântica entre environment_type e a descrição de CADA
    # localização (tools/semantic_search.py). top_k grande o suficiente para
    # cobrir as 42 localizações do dataset: precisamos da similaridade de
    # qualquer candidato que a filtragem geográfica (location_hint) venha a
    # escolher, não só do top-K global. Lista vazia se environment_type for
    # None OU se o modelo/índice não estiverem disponíveis (ver
    # semantic_search.is_available()) - em ambos os casos degrada-se para
    # características neutras (0.5), tratado abaixo.
    similarity_by_id: Dict[str, float] = {}
    if environment_type and environment_type.strip().lower() != NO_PREFERENCE_SENTINEL:
        similarity_by_id = dict(semantic_query(environment_type, top_k=200))

    if location_hint:
        # location_hint continua a mandar na seleção geográfica (nome exato/
        # fuzzy/região) - o retrieval semântico não participa nesta escolha,
        # só no scoring de characteristics_score mais abaixo.
        candidates = get_candidate_locations(
            location_hint=location_hint,
            environment_keywords=None,
            max_results=max_candidates
        )
    elif environment_type and similarity_by_id:
        # Sem location_hint: os candidatos são as localizações mais
        # similares semanticamente a environment_type, em vez do antigo
        # filter_locations_by_characteristics por keywords.
        locations_by_id = {loc['id']: loc for loc in get_all_locations()}
        ranked_ids = sorted(similarity_by_id, key=similarity_by_id.get, reverse=True)
        candidates = [locations_by_id[loc_id] for loc_id in ranked_ids if loc_id in locations_by_id][:max_candidates]
    else:
        # Nem location_hint nem environment_type (ou retrieval semântico
        # indisponível): mesmo fallback que já existia - localizações
        # mais populosas primeiro.
        candidates = get_candidate_locations(
            location_hint=None,
            environment_keywords=None,
            max_results=max_candidates
        )

    print(f" Encontrados {len(candidates)} candidatos para avaliar")

    # 2. Avaliar cada candidato
    print(f"\ Avaliando candidatos...")
    evaluated = []

    for i, candidate in enumerate(candidates, 1):
        print(f"  [{i}/{len(candidates)}] Avaliando {candidate['name']}...")
        characteristics_score = similarity_by_id.get(candidate['id'], 0.5)
        result = await evaluate_location(candidate, environment_type, model_client, characteristics_score)
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