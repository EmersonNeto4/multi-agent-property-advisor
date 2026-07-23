from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from models import UserPreferences
from typing import Optional, List, Dict, Union
import json
from tools.property_search import find_properties


def create_property_agent(model_client: OpenAIChatCompletionClient) -> AssistantAgent:
    """Cria o Property Agent."""
    
    async def find_properties_wrapper(
        locations: Union[List[Dict], List[str], str],  # ← Aceitar vários tipos!
        budget: Optional[float] = None,
        rooms: Optional[int] = None,
        bathrooms: Optional[int] = None,
        area_m2: Optional[float] = None,
        operation: Optional[str] = None,
        property_type: Optional[str] = None,
        parking: Optional[bool] = None,
        pool: Optional[bool] = None,
        outdoor_space: Optional[bool] = None,
        proximity_service: Optional[str] = None,
        proximity_radius_km: float = 5.0,
        top_n: int = 10
    ) -> List[Dict]:
        """Wrapper que reconstrói UserPreferences completo."""
        
        # ==========================================
        # NORMALIZAR LOCATIONS (CRÍTICO!)
        # ==========================================
        if isinstance(locations, str):
            # Caso 1: String JSON
            print("Locations recebido como string, fazendo parse...")
            try:
                locations_clean = locations.strip().replace("'", '"')
                
                # Remover escapes problemáticos
                locations_clean = locations_clean.replace('\\u00ba', 'º').replace('\\u00b0', 'º')
                
                if not locations_clean.endswith(']'):
                    # String truncada - extrair nomes com regex
                    import re
                    names = re.findall(r"['\"]name['\"]:\s*['\"]([^'\"]+)['\"]", locations_clean)
                    if names:
                        locations = [{'name': name} for name in names]
                        print(f" Extraídos {len(names)} nomes de string truncada")
                    else:
                        print(" Não foi possível extrair nomes")
                        return []
                else:
                    locations = json.loads(locations_clean)
                    print(f" Parse JSON bem-sucedido: {len(locations)} localizações")
                    
            except Exception as e:
                print(f" Erro no parse: {e}")
                import re
                names = re.findall(r"['\"]name['\"]:\s*['\"]([^'\"]+)['\"]", locations)
                if names:
                    locations = [{'name': name} for name in names]
                    print(f" Fallback regex: {len(names)} nomes")
                else:
                    return []
        
        elif isinstance(locations, list):
            # Caso 2: Lista (pode ser de strings ou dicts)
            if len(locations) == 0:
                print(" Lista de locations vazia!")
                return []
            
            # Sub-caso 2a: Lista de strings → converter para dicts
            if all(isinstance(loc, str) for loc in locations):
                print(f" Locations recebido como lista de strings: {locations}")
                print(f"   Convertendo para lista de dicts...")
                locations = [{'name': loc} for loc in locations]
                print(f" Convertidos {len(locations)} nomes para dicts")
            
            # Sub-caso 2b: Lista de dicts → OK!
            elif all(isinstance(loc, dict) for loc in locations):
                print(f" Locations é lista de dicts: {len(locations)} localizações")
            
            # Sub-caso 2c: Misto → normalizar
            else:
                print(" Locations tem tipos mistos, normalizando...")
                normalized = []
                for loc in locations:
                    if isinstance(loc, str):
                        normalized.append({'name': loc})
                    elif isinstance(loc, dict) and 'name' in loc:
                        normalized.append(loc)
                    else:
                        print(f"    Item inválido ignorado: {loc}")
                locations = normalized
                print(f" Normalizados {len(locations)} localizações")
        
        else:
            print(f" Tipo inválido para locations: {type(locations)}")
            return []
        
        # Validação final
        if not locations:
            print(" Nenhuma localização válida após normalização!")
            return []
        
        print(f"\n PropertyAgent - Localizações normalizadas:")
        for i, loc in enumerate(locations, 1):
            print(f"   #{i}: {loc.get('name', 'UNKNOWN')}")
        
        # ==========================================
        # CRIAR USER PREFERENCES
        # ==========================================
        preferences = UserPreferences(
            budget=budget,
            rooms=rooms,
            bathrooms=bathrooms,
            area_m2=area_m2,
            operation=operation,
            property_type=property_type,
            parking=parking,
            pool=pool,
            outdoor_space=outdoor_space
        )
        
        print(f"\nPropertyAgent - Preferências:")
        print(f"   Budget: €{preferences.budget:,}" if preferences.budget else "   Budget: None")
        print(f"   Rooms: {preferences.rooms}" if preferences.rooms else "   Rooms: None")
        print(f"   Property Type: {preferences.property_type}" if preferences.property_type else "   Property Type: None")
        print(f"   Operation: {preferences.operation}" if preferences.operation else "   Operation: None")
        
        # ==========================================
        # CHAMAR BUSCA
        # ==========================================
        
        raw_results = await find_properties(
            locations=locations,
            preferences=preferences,
            proximity_service=proximity_service,
            proximity_radius_km=proximity_radius_km,
            top_n=top_n
        )

        # ==========================================
        #  LIMPEZA DE DADOS 
        # ==========================================
        clean_results = []
        for p in raw_results:
            # Criar um novo dicionário APENAS com o essencial
            # Removemos 'thumbnail', 'num_photos', 'has_video' que confundem o LLM
            clean_p = {
                'id': p.get('id'),
                'title': p.get('title'),
                'price': p.get('price'),
                'area_m2': p.get('area_m2'),
                'rooms': p.get('rooms'),
                'bathrooms': p.get('bathrooms'),
                'address': p.get('address'),
                'municipality': p.get('municipality'),
                'province': p.get('province'),
                'url': p.get('url'),  # O URL é importante manter
                'csp_score': p.get('csp_score'),
                'satisfied_preferences': p.get('satisfied_preferences'),
                # Manter flags importantes
                'parking': p.get('parking'),
                'has_pool': p.get('has_pool', False),
                'has_lift': p.get('has_lift')
            }
            clean_results.append(clean_p)
            
        print(f" Dados limpos: Reduzido de {len(str(raw_results))} chars para {len(str(clean_results))} chars")
        
        return clean_results
    
    system_message = """You are the Property Agent.

Your responsibilities:
1. Receive locations and preferences.
2. **EXECUTE** the 'find_properties_wrapper' tool.
3. Output the result.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CRITICAL RULES - DO NOT HALLUCINATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1.  **NEVER** write the tool call as JSON text in the chat.
   - WRONG: {"function": "find_properties", ...}
   - RIGHT: [Actually calling the function code]

2.  **NEVER** invent properties or URLs.
   - If the tool returns [], say "No properties found".
   - Do NOT make up "Apartamento T2" with "example.com".

3. **MANDATORY:** You MUST call the tool 'find_properties_wrapper'. Do not just talk about it.

**LOCATIONS PARAMETER:**
Pass the list exactly as received (list of dicts).

**COMPLETE EXAMPLE:**
find_properties_wrapper(
    locations=[{"name": "Lisboa", "score": 0.63}],
    budget=1000000,
    rooms=2,
    operation="sale",
    property_type="T2",
    proximity_service="Hospital Santa Maria"
)

EXECUTE THE TOOL NOW.
"""
    
    property_agent = AssistantAgent(
        name="PropertyAgent",
        model_client=model_client,
        tools=[find_properties_wrapper],
        system_message=system_message
    )
    
    return property_agent