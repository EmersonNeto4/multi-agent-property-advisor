from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from tools import calculate_knn_scores
from typing import Union, List, Dict, Annotated
import json


def create_data_analyst_agent(model_client: OpenAIChatCompletionClient) -> AssistantAgent:
    """
    Cria o Data Analyst Agent que calcula KNN scores.
    """
    
    # Wrapper com parse robusto
    def calculate_knn_scores_wrapper(
        properties: Annotated[Union[List[Dict], str], "A lista de imóveis filtrados recebida do agente anterior (ou string JSON)."],
        user_budget: Annotated[float, "O orçamento MÁXIMO do utilizador extraído do histórico da conversa (ex: 1500000)."],
        k: Annotated[int, "Número de vizinhos a considerar."] = 5
    ) -> List[Dict]:
        """
        Calcula a pontuação KNN para uma lista de imóveis baseada na proximidade ao orçamento do utilizador.
        IMPORTANTE: O argumento 'user_budget' é obrigatório e deve ser extraído da solicitação inicial do utilizador.
        """
        
        # --- Início do teu código original de limpeza ---
        if isinstance(properties, str):
            print(" Properties recebido como string, fazendo parse...")
            try:
                clean = properties.rstrip(', ').strip()
                clean = clean.replace('\\u00ba', 'º').replace('\\u00b0', 'º')
                if "'" in clean:
                    clean = clean.replace("'", '"')
                properties = json.loads(clean)
                print(f" Parse bem-sucedido: {len(properties)} propriedades")
            except json.JSONDecodeError as e:
                print(f" Erro ao fazer parse de properties: {e}")
                return []
        
        if not isinstance(properties, list):
            return []
        
        if len(properties) == 0:
            print(" Lista de properties está vazia!")
            return []
            
        print(f"\n Calculando KNN scores")
        print(f"   Dataset: {len(properties)} imóveis")
        print(f"   User budget: €{user_budget:,}") # Agora isto não vai falhar
        print(f"   K: {k}")
        
        if len(properties) > 20:
            print(f"    Limitando análise a primeiras 20 propriedades")
            properties = properties[:20]
        
        try:
            result = calculate_knn_scores(
                properties=properties,
                user_budget=user_budget,
                k=k
            )
            print(f" KNN concluído: {len(result)} imóveis com scores")
            return result
        except Exception as e:
            print(f" Erro no cálculo KNN: {e}")
            return properties
    
    system_message = """You are the Data Analyst Agent in a real estate recommendation system.

            Your responsibilities:
            1. Receive filtered properties from Property Agent
            2. Calculate KNN (K-Nearest Neighbors) scores based on similarity to user budget
            3. Add analytical insights about each property
            4. Format data clearly for Evaluator Agent

             CRITICAL INSTRUCTION - TOOL ARGUMENTS:
            When calling 'calculate_knn_scores_wrapper', you MUST provide two arguments:
            1. 'properties': The list you just received.
            2. 'user_budget': You MUST search the CONVERSATION HISTORY to find the user's budget (e.g., "budget of 1500000"). 
               DO NOT call the tool without this number. If you cannot find it, ask the user.

            Process:
            1. Receive list of properties (already filtered by CSP)
            2. Calculate KNN similarity scores using user's budget as reference
            3. Identify K nearest neighbors (most similar properties)
            4. Add knn_score and knn_neighbors to each property
            5. Format results with ALL property fields intact

            IMPORTANT - DATA HANDLING:
            - You may receive 10-50 properties
            - If more than 20 properties, analyze only first 20
            - Preserve ALL fields: id, title, url, price, area_m2, rooms, bathrooms, etc.
            - Add knn_score (0.0 to 1.0) to each property
            - Properties closer to user's budget get higher scores

            CRITICAL - PASS COMPLETE DATA:
            When passing results to Evaluator, ensure EVERY property has:
            - id (REQUIRED)
            - title (REQUIRED)  
            - url (REQUIRED - CRITICAL!)
            - price, area_m2, rooms, bathrooms
            - address, municipality, province
            - latitude, longitude
            - csp_score, satisfied_preferences
            - knn_score, knn_neighbors (added by you)

            FORMAT FOR EVALUATOR:
            Present data as structured list with clear separators:
            "Analyzed N properties with KNN scores:

            Property #1:
            - ID: [id]
            - Title: [title]
            - URL: [url]
            - Price: €[price]
            - Area: [area_m2]m²
            - Rooms: [rooms]
            - CSP Score: [csp_score]
            - KNN Score: [knn_score]
            [... all other fields ...]

            Property #2:
            [...]
            "

            REMEMBER: The Evaluator needs complete, accurate data to make recommendations!
        """
    
    analyst_agent = AssistantAgent(
        name="DataAnalystAgent",
        model_client=model_client,
        tools=[calculate_knn_scores_wrapper],
        system_message=system_message
    )
    
    return analyst_agent