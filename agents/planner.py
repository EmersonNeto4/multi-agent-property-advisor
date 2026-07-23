from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from models import UserPreferences
from typing import Optional

def create_planner_agent(model_client: OpenAIChatCompletionClient) -> AssistantAgent:
    """
    Cria o Planner Agent que extrai preferências do utilizador.
    """
    
    # Tool que extrai as preferências
    def extract_preferences(
        budget: Optional[float] = None,
        rooms: Optional[int] = None,
        bathrooms: Optional[int] = None,
        area_m2: Optional[float] = None,
        operation: Optional[str] = None,
        property_type: Optional[str] = None,
        parking: Optional[bool] = None,
        pool: Optional[bool] = None,
        outdoor_space: Optional[bool] = None,
        location: Optional[str] = None,
        environment_type: Optional[str] = None,
        proximity_services: Optional[str] = None,
        skip_location_agent: bool = False,
        additional_notes: Optional[str] = None
    ) -> UserPreferences:
        """Extract user preferences."""
        
        # ==========================================
        # AUTO-EXTRAIR ROOMS DE PROPERTY_TYPE
        # ==========================================
        if property_type and not rooms:
            # Tentar extrair número de TX (T1, T2, T3, T4, etc.)
            import re
            match = re.match(r'T(\d+)', property_type, re.IGNORECASE)
            if match:
                rooms = int(match.group(1))
                print(f"Auto-extraído: T{rooms} → rooms={rooms}")
        
        print(f"\n Planner - Extracted Preferences:")
        print(f"   Budget: €{budget:,}" if budget else "   Budget: Not specified")
        print(f"   Property Type: {property_type}")
        print(f"   Rooms: {rooms}")
        print(f"   Location: {location}")
        
        return UserPreferences(
            budget=budget,
            rooms=rooms,
            bathrooms=bathrooms,
            area_m2=area_m2,
            operation=operation,
            property_type=property_type,
            parking=parking,
            pool=pool,
            outdoor_space=outdoor_space,
            location=location,
            environment_type=environment_type,
            proximity_services=proximity_services,
            skip_location_agent=skip_location_agent,
            additional_notes=additional_notes
        )

    system_message = """You are the Planner Agent. Your job is to analyze the user's real estate request.

    CRITICAL DECISION PROTOCOL:

    1. **ANALYZE:** Read the user's input carefully.
    EXTRACTION RULES:
    
    - **environment_type**: ABSTRACT adjectives describing the vibe/atmosphere.
      -  EXAMPLES: "calmo", "urbano", "perto da praia", "rural", "cosmopolita", "ameno".
      -  WRONG: "perto do Hospital", "perto de Lisboa", "ao lado da escola".

    

    

    EXTRACTION RULES calling the tool `extract_preferences` with the following parameters:
        - **budget**: Maximum price (number).
        - **rooms**: Minimum bedrooms (T1=1, etc).
        - **location**: Specific city, town, district, or neighborhood name.
        - EXAMPLES: "Lisboa", "Coimbra", "Benfica", "Algarve"
        - **environment_type**: Adjectives describing the place (e.g., "calmo", "urbano", "perto da praia", "ameno").
            -  EXAMPLES: "calmo", "urbano", "perto da praia", "rural", "cosmopolita", "ameno".
            -  WRONG: "perto do Hospital", "perto de Lisboa", "ao lado da escola".
        - **operation**: "sale" (buy/comprar) or "rent" (arrendar/alugar). Default is "sale".
        - **parking**: Set to True if user mentions "garagem", "estacionamento", or "lugar".
        - **pool**: Set to True if user mentions "piscina".
        - **proximity_services**: SPECIFIC physical places, landmarks, or infrastructure.
        - EXAMPLES: "Hospital Santa Maria", "Estádio da Luz", "metro", "escolas", "supermercado", "aeroporto".
        - WRONG: "zona calma", "boa vizinhança".
        - **property_type**: Specific type (Apartamento, Moradia, etc).
        - **skip_location_agent**: Set True ONLY if the user gives a VERY specific location.

    CRITICAL JSON FORMATTING RULES
        1. You MUST use DOUBLE QUOTES (") for ALL keys and string values.
        2. DO NOT use single quotes (') anywhere in the JSON structure.
        3. CORRECT: {"budget": 50000, "pool": true}
        4. WRONG: {'budget': 50000, 'pool': True}
    
    FORMATTING:
        - Use DOUBLE QUOTES for JSON.

    Be precise.
    """
    
    planner = AssistantAgent(
        name="Planner",
        model_client=model_client,
        tools=[extract_preferences],
        system_message=system_message,
    )

    return planner