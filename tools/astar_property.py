import heapq
from typing import List, Dict, Tuple, Optional
from tools.search_algorithms import haversine_distance, euclidean_distance

class PropertyNode:
    """
    Nó para A* search representando um imóvel.
    """
    
    def __init__(
        self,
        property_data: Dict,
        service_coords: Tuple[float, float],
        parent: Optional['PropertyNode'] = None
    ):
        self.property = property_data
        self.service_lat, self.service_lon = service_coords
        
        # Coordenadas do imóvel
        self.lat = property_data['latitude']
        self.lon = property_data['longitude']
        
        # Custos A*
        self.g = 0  # Custo real (Haversine)
        self.h = 0  # Heurística (Euclidean)
        self.f = 0  # f = g + h
        
        self.parent = parent
        
        self._calculate_costs()
    
    def _calculate_costs(self):
        """Calcula g, h e f."""
        # g(n): Custo real usando Haversine
        self.g = haversine_distance(
            self.lat, self.lon,
            self.service_lat, self.service_lon
        )
        
        # h(n): Heurística usando Euclidean (admissível: sempre ≤ custo real)
        self.h = euclidean_distance(
            self.lat, self.lon,
            self.service_lat, self.service_lon
        )
        
        # f(n) = g(n) + h(n)
        self.f = self.g + self.h
    
    def __lt__(self, other):
        """Comparação para heap (menor f primeiro)."""
        return self.f < other.f
    
    def __eq__(self, other):
        """Igualdade baseada no ID do imóvel."""
        return self.property['id'] == other.property['id']
    
    def __hash__(self):
        """Hash baseado no ID do imóvel."""
        return hash(self.property['id'])

def astar_property_search(
    properties: List[Dict],
    service_coords: Tuple[float, float],
    max_results: int = 10
) -> List[Dict]:
    """
    Implementação de A* para encontrar imóveis mais próximos de um serviço.
    
    Args:
        properties: Lista de imóveis (já filtrados por CSP)
        service_coords: Coordenadas (lat, lon) do serviço desejado
        max_results: Número máximo de resultados
        
    Returns:
        Lista de imóveis ordenados por proximidade com scores A*
    """
    print(f"\n A* Search: Buscando imóveis próximos a ({service_coords[0]:.4f}, {service_coords[1]:.4f})")
    
    # Filtrar imóveis que têm coordenadas
    valid_properties = [
        p for p in properties 
        if p.get('latitude') and p.get('longitude')
    ]
    
    if not valid_properties:
        print(" Nenhum imóvel tem coordenadas disponíveis")
        return []
    
    print(f"    {len(valid_properties)} imóveis com coordenadas")
    
    # Criar nós A* para cada imóvel
    nodes = []
    for prop in valid_properties:
        node = PropertyNode(prop, service_coords)
        nodes.append(node)
    
    # Ordenar por f(n) usando heap
    heapq.heapify(nodes)
    
    # Extrair top N
    results = []
    for _ in range(min(max_results, len(nodes))):
        if nodes:
            node = heapq.heappop(nodes)
            
            # Adicionar informações A* ao imóvel
            result_prop = node.property.copy()
            result_prop['astar_score'] = round(node.f, 3)
            result_prop['distance_real_km'] = round(node.g, 2)
            result_prop['distance_heuristic_km'] = round(node.h, 2)
            result_prop['service_coords'] = service_coords
            
            results.append(result_prop)
    
    # Estatísticas
    if results:
        print(f"\n    Top {len(results)} imóveis encontrados:")
        print(f"      Mais próximo: {results[0]['distance_real_km']}km")
        print(f"      Mais distante: {results[-1]['distance_real_km']}km")
        print(f"      Distância média: {sum(r['distance_real_km'] for r in results)/len(results):.2f}km")
    
    return results