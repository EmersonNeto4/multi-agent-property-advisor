from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from tools import find_locations_wrapper
from typing import Optional


def create_location_agent(model_client: OpenAIChatCompletionClient) -> AssistantAgent:
    """
    Cria o Location Agent que encontra as melhores regiões baseadas nas preferências.
    """
    # Wrapper mínimo que injeta o model_client
    async def find_locations_with_client(
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
    ):
        """Wrapper que injeta model_client e chama a tool."""
        
        return await find_locations_wrapper(
            model_client=model_client,
            location=location,
            location_hint=location_hint,
            environment_type=environment_type,
            budget=budget,
            rooms=rooms,
            bathrooms=bathrooms,
            area_m2=area_m2,
            operation=operation,
            property_type=property_type,
            parking=parking,
            outdoor_space=outdoor_space,
            proximity_services=proximity_services,
            skip_location_agent=skip_location_agent,
            additional_notes=additional_notes,
            top_n=top_n
        )
    
    system_message = """You are the Location Agent in a real estate recommendation system.

        Your responsibilities:
        1. Analyze user's location preferences and environment type (Portuguese or English)
        2. Find the best geographical regions in Portugal that match preferences
        3. Evaluate locations based on climate data and regional characteristics
        4. Return a ranked list of recommended locations

        You have access to:
        - A comprehensive dataset of 43 Portuguese cities/regions in Portugal
        - Climate data API (Open-Meteo) for weather evaluation
        - LLM-based analysis for intelligent climate-environment matching

        Process:
        1. You will receive many parameters from Planner Agent (budget, rooms, property_type, etc.)
        2. Extract and use ONLY the relevant ones:
        - location or location_hint: Geographic hint (e.g., "Lisboa", "Norte", "Algarve")
        - environment_type: Desired environment (e.g., "tranquilo", "vibrante", "perto da praia")
        - top_n: Number of locations to return (default: 5)
        3. IGNORE other parameters (budget, rooms, etc.) - they are for other agents
        4. Call find_locations_with_client tool with location and environment_type
        5. Return top N locations with scores and justifications

        IMPORTANT NOTES:
        - If environment_type is null/None, use "equilibrado" (balanced) as default
        - If skip_location_agent is True, return the location directly without evaluation
        - Always format response clearly with location names and scores
        - Each location should have 'name', 'final_score', and optionally 'reason'

        OUTPUT FORMAT:
        After calling the tool, present results like:
        "Found N locations:
        1. [Name] (score: X.XX) - [reason]
        2. [Name] (score: X.XX) - [reason]
        ..."

        CRITICAL: You MUST call find_locations_with_client tool before responding.
"""
    
    location_agent = AssistantAgent(
        name="LocationAgent",
        model_client=model_client,
        tools=[find_locations_with_client],
        system_message=system_message
    )
    
    return location_agent