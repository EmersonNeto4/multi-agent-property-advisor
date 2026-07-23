import httpx
import re
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from typing import Dict, Optional, Tuple

async def get_weather_data(
        latitude: float,
        longitude: float,
        forecast_days: int = 7
) -> Dict:
    """
    Obtém dados climáticos de uma localização usando Open-Meteo API.
    
    Args:
        latitude: Latitude da localização
        longitude: Longitude da localização
        forecast_days: Número de dias de previsão (padrão: 7)
        
    Returns:
        Dicionário com dados climáticos:
        - current: dados atuais (temperatura, precipitação, vento)
        - daily: previsão diária (temp max/min, precipitação, horas de sol)
        
    Raises:
        httpx.HTTPError: Se houver erro na requisição
    """
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,sunshine_duration",
        "timezone": "Europe/Lisbon",
        "forecast_days": forecast_days
        }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

async def get_location_coordinates(location_name: str) -> Optional[Tuple[float, float]]:
    """
    Converte nome de localização em coordenadas (latitude, longitude) usando GeoPy.
    
    Args:
        location_name: Nome da localização (ex: "Coimbra", "Lisboa", "Porto")
        
    Returns:
        Tuplo (latitude, longitude) ou None se não encontrar
    """
    # Implementação do GeoPy
    
    try:
        # Criar geocoder (Nominatim usa OpenStreetMap - gratuito)
        geolocator = Nominatim(user_agent = "iarp_real_estate_recommender")

        # Se não mencionar Portugal, adicionar para melhor precisão
        if "portugal" not in location_name.lower():
            location_query = f"{location_name}, Portugal"
        else:
            location_query = location_name

        # Geocodificar
        location = geolocator.geocode(location_query, timeout=10)

        if location:
            return (location.latitude, location.longitude)
        else:
            print(f" Localização '{location_name}' não encontrada")
            return None
        
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f" Erro ao geocodificar '{location_name}': {e}")
        return None
    except Exception as e:
        print(f" Erro inesperado: {e}")
        return None

async def analyze_weather_simple(
    weather_data: Dict,
    environment_type: str
) -> float:
    """
    Análise com regras simples e heurísticas predefinidas.
    
    Vantagens: Rápido, não precisa de LLM, determinístico
    Desvantagens: Limitado a poucos tipos de ambiente conhecidos
    
    Args:
        weather_data: Dados climáticos do Open-Meteo
        environment_type: Tipo de ambiente desejado
        
    Returns:
        Score de 0.0 a 1.0 indicando compatibilidade
    """
    # Extrair médias dos dados diários
    temps_max = weather_data['daily']['temperature_2m_max']
    temps_min = weather_data['daily']['temperature_2m_min']
    precipitation = weather_data['daily']['precipitation_sum']
    sunshine = weather_data['daily']['sunshine_duration']
    
    avg_temp = sum(temps_max + temps_min) / len(temps_max + temps_min)
    avg_precip = sum(precipitation) / len(precipitation)
    avg_sunshine_hours = sum(sunshine) / len(sunshine) / 3600
    
    # Score base
    score = 0.5
    env_lower = environment_type.lower()
    
    # Regras heurísticas simples
    if "tranquilo" in env_lower or "calmo" in env_lower or "sossegado" in env_lower:
        if 15 <= avg_temp <= 25:
            score += 0.2
        if avg_precip < 2:
            score += 0.2
        if avg_sunshine_hours > 6:
            score += 0.1
            
    elif "vibrante" in env_lower or "animado" in env_lower or "movimentado" in env_lower:
        if 20 <= avg_temp <= 30:
            score += 0.3
        if avg_sunshine_hours > 8:
            score += 0.2
            
    elif "natureza" in env_lower or "natural" in env_lower or "verde" in env_lower:
        if 18 <= avg_temp <= 26:
            score += 0.2
        if 1 <= avg_precip <= 5:
            score += 0.2
        if avg_sunshine_hours > 5:
            score += 0.1
    
    return min(score, 1.0)

async def analyze_weather_with_llm(
    weather_data: Dict,
    environment_type: str,
    model_client
) -> float:
    """
    Análise inteligente usando LLM para interpretar qualquer tipo de ambiente.
    
    Vantagens: Flexível, entende descrições complexas e nuances
    Desvantagens: Mais lento, requer chamada à API
    
    Args:
        weather_data: Dados climáticos do Open-Meteo
        environment_type: Tipo de ambiente desejado (qualquer descrição)
        model_client: Cliente do modelo LLM configurado
        
    Returns:
        Score de 0.0 a 1.0 indicando compatibilidade
    """
    from autogen_agentchat.agents import AssistantAgent
    
    # Preparar resumo dos dados climáticos
    temps_max = weather_data['daily']['temperature_2m_max']
    temps_min = weather_data['daily']['temperature_2m_min']
    precipitation = weather_data['daily']['precipitation_sum']
    sunshine = weather_data['daily']['sunshine_duration']
    
    avg_temp = sum(temps_max + temps_min) / len(temps_max + temps_min)
    avg_precip = sum(precipitation) / len(precipitation)
    avg_sunshine_hours = sum(sunshine) / len(sunshine) / 3600
    
    current_temp = weather_data['current']['temperature_2m']
    current_precip = weather_data['current']['precipitation']
    
    # Criar prompt estruturado para o LLM
    prompt = f"""You are a climate analysis expert for real estate recommendations.

        Given the following climate data for a location:
        - Current temperature: {current_temp}°C
        - Current precipitation: {current_precip}mm
        - Average temperature (7 days): {avg_temp:.1f}°C
        - Average daily precipitation: {avg_precip:.1f}mm
        - Average daily sunshine: {avg_sunshine_hours:.1f} hours

        The user is looking for a location with the following environment type:
        "{environment_type}"

        Analyze how well this climate suits the desired environment type. Consider:
        - Temperature comfort for the lifestyle
        - Precipitation levels (too much rain? too dry?)
        - Sunshine duration (affects mood and outdoor activities)
        - Overall climate compatibility with the environment description

        Return ONLY a score from 0.0 to 1.0 where:
        - 0.0 = completely unsuitable
        - 0.5 = neutral/acceptable
        - 1.0 = perfectly suited

        Your response must be ONLY the numeric score (e.g., "0.75"), nothing else.
        """

    # Criar agente temporário para análise
    analyzer = AssistantAgent(
        name="ClimateAnalyzer",
        model_client=model_client,
        system_message="You are a climate analysis expert. Respond only with numeric scores between 0.0 and 1.0."
    )
    
    try:
        # Executar análise
        result = await analyzer.run(task=prompt)
        
        # Extrair score da resposta
        response_text = str(result.messages[-1].content)
        
        # Procurar por um número decimal usando regex
        match = re.search(r'0\.\d+|1\.0|0\.0', response_text)
        if match:
            score = float(match.group())
            return max(0.0, min(1.0, score))
        else:
            print(f" Não foi possível extrair score da resposta: {response_text}")
            return 0.5
            
    except Exception as e:
        print(f" Erro ao processar análise com LLM: {e}")
        # Fallback para análise simples em caso de erro
        print("   Usando análise simples como fallback...")
        return await analyze_weather_simple(weather_data, environment_type)

async def analyze_weather_for_environment(
    weather_data: Dict,
    environment_type: str,
    model_client = None
) -> float:
    """
    Função principal para análise de compatibilidade clima-ambiente.
    
    Escolhe automaticamente o melhor método:
    - Se model_client fornecido: usa análise inteligente com LLM (recomendado)
    - Se não: usa análise com regras simples (fallback)
    
    Args:
        weather_data: Dados climáticos do Open-Meteo
        environment_type: Tipo de ambiente desejado pelo utilizador
        model_client: Cliente do modelo LLM (opcional)
        
    Returns:
        Score de 0.0 a 1.0 indicando quão bem o clima se adequa ao ambiente
        
    Example:
        >>> weather = await get_weather_data(40.2033, -8.4103)
        >>> score = await analyze_weather_for_environment(
        ...     weather, 
        ...     "zona tranquila perto da natureza",
        ...     model_client
        ... )
    """
    if model_client is not None:
        return await analyze_weather_with_llm(weather_data, environment_type, model_client)
    else:
        return await analyze_weather_simple(weather_data, environment_type)