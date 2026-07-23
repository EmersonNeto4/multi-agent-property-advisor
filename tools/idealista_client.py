import httpx
from typing import List, Dict, Optional, Tuple
from tools.idealista_oauth import get_idealista_auth
from utils.config import IDEALISTA_API_URL
import json
from pathlib import Path
import unicodedata


async def search_properties_by_coordinates(
    center_lat: float,
    center_lon: float,
    distance_meters: int = 5000,
    country: str = "pt",
    operation: str = "sale",
    property_type: str = "homes",
    max_price: Optional[int] = None,
    min_price: Optional[int] = None,
    bedrooms: Optional[str] = None,
    garage: Optional[bool] = None,
    pool: Optional[bool] = None,
    max_items: int = 50,
    page: int = 1,
    order: str = "distance",
    sort: str = "asc"
) -> List[Dict]:
    """
    Busca imóveis por COORDENADAS + RAIO.
    
    Args:
        center_lat, center_lon: Coordenadas do centro da busca
        distance_meters: Raio em METROS (ex: 5000 = 5km)
        country: País (pt, es, it)
        operation: sale ou rent
        property_type: homes, offices, premises, garages, bedrooms
        max_price: Preço máximo
        min_price: Preço mínimo
        bedrooms: Quartos (ex: "2" ou "2,3,4")
        max_items: Máximo por página (50)
        page: Número da página
        order: distance, price, publicationDate, size, rooms
        sort: asc ou desc
        
    Returns:
        Lista de imóveis
    """
    # Autenticar
    auth = get_idealista_auth()
    token = await auth.get_token()
    
    # Endpoint
    url = f"{IDEALISTA_API_URL}/{country}/search"
    
    # Headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Parâmetros (form-encoded)
    params = {
        "center": f"{center_lat},{center_lon}",  
        "distance": str(distance_meters),         
        "country": country,
        "operation": operation,
        "propertyType": property_type,
        "maxItems": str(max_items),
        "numPage": str(page),
        "order": order,
        "sort": sort,
        "locale": "pt"
    }
    
    # Filtros opcionais
    if max_price:
        params["maxPrice"] = str(max_price)
    if min_price:
        params["minPrice"] = str(min_price)
    if bedrooms:
        params["bedrooms"] = bedrooms
    if garage:
        params["garage"] = "true"
    if pool:
        params["swimmingPool"] = "true"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, data=params)
            response.raise_for_status()
            
            data = response.json()
            
            total = data.get('total', 0)
            properties = data.get('elementList', [])
            
            print(f" API Idealista retornou {len(properties)} imóveis (total: {total})")
            
            return properties
            
    except httpx.HTTPError as e:
        print(f" Erro HTTP: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Resposta: {e.response.text}")
        return []
    except Exception as e:
        print(f" Erro: {e}")
        return []
    
async def search_properties_by_location_id(
    location_id: str,
    country: str = "pt",
    operation: str = "sale",
    property_type: str = "homes",
    max_price: Optional[int] = None,
    min_price: Optional[int] = None,
    bedrooms: Optional[str] = None,
    garage: Optional[bool] = None,
    pool: Optional[bool] = None,
    max_items: int = 50,
    page: int = 1,
    order: str = "price",
    sort: str = "asc"
) -> List[Dict]:
    """
    Busca imóveis por LOCATIONID (distrito/concelho).
    
    Args:
        location_id: ID da localização (ex: "0-EU-PT-06")
        ... (resto igual)
    """
    from tools.idealista_oauth import get_idealista_auth
    from utils.config import IDEALISTA_API_URL
    
    # Autenticar
    auth = get_idealista_auth()
    token = await auth.get_token()
    
    # Endpoint
    url = f"{IDEALISTA_API_URL}/{country}/search"
    
    # Headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Parâmetros com LOCATIONID
    params = {
        "locationId": location_id,
        "country": country,
        "operation": operation,
        "propertyType": property_type,
        "maxItems": str(max_items),
        "numPage": str(page),
        "order": order,
        "sort": sort,
        "locale": "pt"
    }
    
    # Filtros opcionais
    if max_price:
        params["maxPrice"] = str(max_price)
    if min_price:
        params["minPrice"] = str(min_price)
    if bedrooms:
        params["bedrooms"] = bedrooms
    if garage:
        params["garage"] = "true"
    if pool:
        params["swimmingPool"] = "true"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, data=params)
            response.raise_for_status()
            
            data = response.json()
            
            total = data.get('total', 0)
            properties = data.get('elementList', [])
            
            print(f"   API retornou {len(properties)} imóveis (total: {total})")
            
            return properties
            
    except httpx.HTTPError as e:
        print(f"    Erro HTTP: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Resposta: {e.response.text}")
        return []
    except Exception as e:
        print(f"    Erro: {e}")
        return []

def get_location_id_for_city(city_name: str) -> Optional[str]:
    """
    Obtém locationId da Idealista para uma cidade portuguesa.
    
    Lê do ficheiro data/portugal_location_ids.json
    
    Args:
        city_name: Nome da cidade (ex: "Coimbra", "Lisboa")
        
    Returns:
        LocationId (ex: "0-EU-PT-06") ou None se não encontrar
    """
    # Função auxiliar para normalizar texto (remover acentos e lower case)
    def normalize(text):
        return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8').lower().strip()

    mapping_path = Path(__file__).parent.parent / "data" / "portugal_location_ids.json"
    
    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        location_mappings = data.get('location_mappings', {})
        
        # 1. Tenta busca direta
        if city_name in location_mappings:
            return location_mappings[city_name]
            
        # 2. Tenta busca normalizada (Ignora Case e Acentos)
        target = normalize(city_name)
        
        for key, value in location_mappings.items():
            if normalize(key) == target:
                print(f"    LocationId encontrado por normalização: '{key}' -> {value}")
                return value
                
        # 3. Tenta busca parcial (Ex: "Viana" encontra "Viana do Castelo")
        for key, value in location_mappings.items():
            if target in normalize(key) or normalize(key) in target:
                print(f"    LocationId encontrado por match parcial: '{key}' -> {value}")
                return value

        print(f"    LocationId não encontrado para '{city_name}'")
        return None
            
    except Exception as e:
        print(f"    Erro ao ler location_ids: {e}")
        return None

def parse_idealista_property(prop: Dict) -> Dict:
    """
    Parseia propriedade da API Oficial (formato ligeiramente diferente).
    
    API Oficial retorna:
    - propertyCode (em vez de id)
    - address, latitude, longitude
    - price, size, rooms, bathrooms
    - url, thumbnail
    """
    # Extrair campos
    property_code = prop.get('propertyCode')
    address = prop.get('address', 'Sem título')
    price = prop.get('price', 0)
    size = prop.get('size')
    rooms = prop.get('rooms')
    has_pool = False
    
    # Extrair propertyCode
    property_code = prop.get('propertyCode')
    parking_data = prop.get('parkingSpace', {})
    has_parking = parking_data.get('hasParkingSpace', False)
    if prop.get('swimmingPool') is True: has_pool = True
    if prop.get('hasPool') is True: has_pool = True
    
    # Verifica descrição (fallback)
    if 'piscina' in prop.get('description', '').lower(): has_pool = True
    
    # Construir URL (sempre funciona, mesmo se API não retornar)
    url = prop.get('url')  # Tentar obter da API primeiro
    
    if not url and property_code:
        # Se API não retornou URL, construir manualmente
        url = f"https://www.idealista.pt/imovel/{property_code}/"
    
    if not price or price == 0:
        print(f"    Propriedade sem preço: {address[:40]}")
    
    if not size:
        print(f"    Propriedade sem área: {address[:40]}")
    
    if not url:
        print(f"    Propriedade sem URL: {address[:40]}")
    
    return {
        'id': str(property_code) if property_code else '',
        'title': prop.get('address', 'Sem título'),
        'price': prop.get('price', 0),
        'area_m2': prop.get('size'),
        'rooms': prop.get('rooms'),
        'bathrooms': prop.get('bathrooms'),
        'latitude': prop.get('latitude'),
        'longitude': prop.get('longitude'),
        'address': prop.get('address'),
        'neighborhood': prop.get('neighborhood'),
        'municipality': prop.get('municipality'),
        'district': prop.get('district'),
        'province': prop.get('province'),
        'url': url,  # ← URL construído ou da API
        'thumbnail': prop.get('thumbnail'),
        'num_photos': prop.get('numPhotos', 0),
        'has_video': prop.get('hasVideo', False),
        'status': prop.get('status'),  # good, renew, newdevelopment
        'has_lift': prop.get('hasLift', False),
        'exterior': prop.get('exterior', False),
        'floor': prop.get('floor'),
        'operation': prop.get('operation'),  # sale, rent
        'property_type': prop.get('propertyType'),
        'parking': has_parking,
        'pool': has_pool
    }