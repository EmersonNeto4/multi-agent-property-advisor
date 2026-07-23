from models import UserPreferences
from tools import search_properties_by_coordinates, search_properties_by_location_id, get_location_id_for_city, parse_idealista_property, geocode_location
from tools.csp_solver import filter_properties_csp
from tools.astar_property import astar_property_search
from tools.search_algorithms import haversine_distance
from typing import List, Dict, Optional, Tuple, Union
import json

async def fetch_properties_from_locations(
    locations: List[Dict],
    preferences: UserPreferences,
    service_coords: Optional[Tuple[float, float]] = None,
    search_radius_km: float = 10.0,
    max_per_location: int = 50
) -> List[Dict]:
    """
    Busca imóveis nas localizações.
    """
    
    all_properties = []
    
    # ==========================================
    # 1. CÁLCULO DO RANGE DE PREÇO (80% - 100%)
    # ==========================================
    api_max_price = int(preferences.budget) if preferences.budget else None
    
    # Definir base mínima
    if preferences.operation == "rent":
        base_min = 100
    else:
        base_min = 50000
        
    api_min_price = base_min
    
    if api_max_price:
        # LÓGICA MAIS FLEXÍVEL PARA RENDAS
        if preferences.operation == "rent":
            # Se for renda baixa (<1000€), usa o mínimo base (não corta os baratos!)
            if api_max_price < 1000:
                api_min_price = base_min
            else:
                # Para rendas altas, corta os muito baratos (60%)
                calculated_min = int(api_max_price * 0.60)
                if calculated_min > base_min: api_min_price = calculated_min
        else:
            # Para venda, mantém a regra dos 75%
            calculated_min = int(api_max_price * 0.75)
            if calculated_min > base_min: api_min_price = calculated_min
            
        # Segurança final: min nunca pode ser >= max
        if api_min_price >= api_max_price:
            api_min_price = base_min
    location_scores = {loc['name']: loc.get('score', 0.5) for loc in locations}

    

            
    print(f"\n{'='*60}")
    print(f" DEBUG - FETCH PROPERTIES (SMART PRICE v2)")
    print(f"{'='*60}")
    print(f"Locations: {locations}")
    print(f"Budget: {preferences.budget} | Op: {preferences.operation}")
    print(f" API Price Filter: €{api_min_price} a {api_max_price}")
    print(f"{'='*60}\n")
    
    # ==========================================
    # DEBUG
    # ==========================================
    print(f"\n{'='*60}")
    print(f" DEBUG - FETCH PROPERTIES (SMART PRICE)")
    print(f"{'='*60}")
    print(f"Locations: {locations}")
    print(f"Budget: {preferences.budget}")
    print(f" Operação: {preferences.operation}")
    print(f" API Price Filter: €{api_min_price} a €{api_max_price}")
    print(f"{'='*60}\n")
    
    # CASO 1: Busca geográfica (com serviço específico)
    if service_coords:
        print(f" Busca geográfica: raio de {search_radius_km}km")
        print(f"   Centro: ({service_coords[0]:.4f}, {service_coords[1]:.4f})")
        
        # FALLBACK 1: Se falhar e tiver budget, tenta baixar o minimo
        try:
            properties = await search_properties_by_coordinates(
                center_lat=service_coords[0],
                center_lon=service_coords[1],
                distance_meters=int(search_radius_km * 1000),
                max_price=api_max_price,       
                min_price=api_min_price,       
                bedrooms=str(preferences.rooms) if preferences.rooms else None,
                garage=preferences.parking,
                pool=preferences.pool,
                max_items=max_per_location,
                operation="sale",
                order="distance" # Mantém distância se for busca por serviço
            )
            
            if (not properties) and api_max_price:
                print("    Nada encontrado no range ideal. Tentando FALLBACK (Range Total)...")
                properties = await search_properties_by_coordinates(
                    center_lat=service_coords[0],
                    center_lon=service_coords[1],
                    distance_meters=int(search_radius_km * 1000),
                    max_price=api_max_price,
                    min_price=base_min,
                    bedrooms=str(preferences.rooms) if preferences.rooms else None,
                    garage=preferences.parking,
                    pool=preferences.pool,
                    max_items=max_per_location,
                    operation=preferences.operation or "sale",
                    order="distance"
                )

            for prop in properties:
                parsed = parse_idealista_property(prop)
                if preferences.pool: parsed['has_pool'] = True
                if preferences.parking: parsed['parking'] = True
                location_name = locations[0].get('name') if locations else "unknown"
                parsed['location_score'] = location_scores.get(location_name, 0.5)
                all_properties.append(parsed)
                
        except Exception as e:
            print(f"    Erro na busca geográfica: {e}")
    
    # ==========================================
    # CASO 2: Busca por locationId
    # ==========================================
    else:
        print(f"\n Buscando imóveis por locationId (Modo Diversificado)...")
        
        # Calcular limite por cidade para garantir variedade
        # Se queremos 10 no final e temos 5 cidades, tentamos trazer ~5 de cada para o KNN escolher
        limit_per_city = max(5, int(50 / len(locations)))
        
        for location in locations:
            location_name = location.get('name')
            location_id = get_location_id_for_city(location_name)
            
            if not location_id: continue
            
            print(f"    Buscando em {location_name} (Top {limit_per_city})...")
            
            try:
                # TENTATIVA 1 (Com filtros todos)
                properties = await search_properties_by_location_id(
                    location_id=location_id,
                    max_price=api_max_price,
                    min_price=api_min_price,
                    bedrooms=str(preferences.rooms) if preferences.rooms else None,
                    garage=preferences.parking,
                    pool=preferences.pool,
                    max_items=limit_per_city, # <--- LIMITA AQUI
                    operation=preferences.operation or "sale",
                    order="price",
                    sort="desc"
                )

                # FALLBACK (Sem filtros se vazio)
                if not properties:
                    # ... (lógica de fallback com limit_per_city) ...
                    pass

                # Processar e Adicionar
                for prop in properties:
                    parsed = parse_idealista_property(prop)
                    parsed['source_location'] = location_name
                    parsed['location_score'] = location_scores.get(location_name, 0.5)
                    
                    # Injeção de confiança
                    if preferences.pool: parsed['has_pool'] = True
                    if preferences.parking: parsed['parking'] = True
                    
                    all_properties.append(parsed)
                    
            except Exception:
                continue

    # ORDENAÇÃO FINAL ANTES DE RETORNAR
    # Ordena por Location Score DESC para garantir que as cidades melhores aparecem primeiro na lista do KNN
    all_properties.sort(key=lambda x: x.get('location_score', 0), reverse=True)
    
    print(f" Total de {len(all_properties)} imóveis encontrados (Diversificados)")
    return all_properties

async def search_properties_with_astar(
    properties: List[Dict],
    service_coords: Tuple[float, float],
    max_results: int = 10
) -> List[Dict]:
    """
    Wrapper async para A* search.
    
    Args:
        properties: Lista de imóveis (já filtrados por CSP)
        service_coords: Coordenadas (lat, lon) do serviço desejado
        max_results: Número máximo de resultados
        
    Returns:
        Lista de imóveis ordenados por proximidade
    """
    return astar_property_search(properties, service_coords, max_results)

async def find_properties(
    locations: List[Dict],
    preferences: UserPreferences,
    proximity_service: Optional[str] = None,
    proximity_radius_km: float = 5.0,
    top_n: int = 10
) -> List[Dict]:
    """
    Busca imóveis.
    
    Args:
        locations: Lista de localizações
        preferences: UserPreferences completo com TODAS as restrições
        proximity_service: Serviço para busca por proximidade
        proximity_radius_km: Raio de busca
        top_n: Número de resultados
        
    Returns:
        Lista de imóveis filtrados e ranqueados
    """
    
    # Validação
    if not locations or len(locations) == 0:
        print(" ERRO: Nenhuma localização fornecida!")
        return []
    
    # Geocodificar serviço se necessário
    service_coords = None
    if proximity_service:
        print(f" Geocodificando serviço: {proximity_service}")
        service_coords = await geocode_location(proximity_service)
        if service_coords:
            print(f"    Coordenadas: ({service_coords[0]:.4f}, {service_coords[1]:.4f})")
    
    # Buscar imóveis
    properties = await fetch_properties_from_locations(
        locations,
        preferences,
        service_coords=service_coords,
        search_radius_km=proximity_radius_km
    )
    
    if not properties:
        print(" Nenhuma propriedade encontrada!")
        return []
    
    print(f"\n Aplicando CSP a {len(properties)} imóveis...")
    print(f"   Budget: €{preferences.budget:,}" if preferences.budget else "   Budget: Não especificado")
    print(f"   Rooms: ≥{preferences.rooms}" if preferences.rooms else "   Rooms: Não especificado")
    
    # Aplicar CSP com preferências completas
    filtered = await filter_properties_csp(properties, preferences)
    
    print(f" CSP concluído: {len(filtered)} imóveis passaram")
    
    # Debug dos primeiros
    for i, prop in enumerate(filtered[:3], 1):
        csp_score = prop.get('csp_score', 0)
        prefs = prop.get('satisfied_preferences', [])
        print(f"   #{i} ID:{prop.get('id')} - €{prop.get('price', 0):,.0f} - {prop.get('rooms')}Q - Score:{csp_score:.2f} - Prefs:{len(prefs)}")
    
    # A* se tiver coordenadas de serviço
    if service_coords and filtered:
        print(f"\n Aplicando A* para proximidade...")
        final = await search_properties_with_astar(filtered, service_coords, top_n)
    else:
        # Ordenar por CSP score (melhor primeiro)
        filtered_sorted = sorted(filtered, key=lambda x: x.get('csp_score', 0), reverse=True)
        final = filtered_sorted[:top_n]
    
    # Debug final
    print(f"\n DEBUG PropertyAgent Tool - RETORNANDO:")
    print(f"   Tipo: {type(final)}")
    print(f"   Length: {len(final)}")
    
    if final:
        print(f"   Primeiras 3 propriedades:")
        for i, prop in enumerate(final[:3], 1):
            print(f"      #{i} ID:{prop.get('id')} - {prop.get('title', 'N/A')[:40]}")
            print(f"         Preço: €{prop.get('price', 0):,}")
            print(f"         Quartos: {prop.get('rooms')}")
            print(f"         URL: {prop.get('url', 'MISSING')}")
    
    return final
