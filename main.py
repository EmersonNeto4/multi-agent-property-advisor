import asyncio
from typing import Dict
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.ui import Console
from utils import create_model_client
from agents import (
    create_planner_agent,
    create_location_agent,
    create_property_agent,
    create_data_analyst_agent,
    create_evaluator_agent
)

async def run_property_recommendation_system(user_query: str) -> Dict:
    """
    Executa o sistema multi-agente de recomendação de imóveis.
    """
    
    print("=" * 80)
    print(" SISTEMA MULTI-AGENTE DE RECOMENDAÇÃO DE IMÓVEIS")
    print("=" * 80)
    
    # Criar model client
    model_client = create_model_client()
    
    # Criar todos os agentes
    print("\n Criando agentes...")
    
    planner = create_planner_agent(model_client)
    location_agent = create_location_agent(model_client)
    property_agent = create_property_agent(model_client)
    analyst = create_data_analyst_agent(model_client)
    evaluator = create_evaluator_agent(model_client)
    
    print(" 5 agentes criados!")
    
    # ============================================
    # CONDIÇÕES DE TÉRMINO (AQUI ESTÁ A MAGIA )
    # ============================================
    
    # 1. Término Normal
    text_termination = TextMentionTermination("TERMINATE")
    
    # 2. Término por Falta de Budget (O Planner disse a frase mágica?)
    # A frase tem de ser igual à que definiste no system_message do Planner
    budget_termination = TextMentionTermination("indique o seu orçamento")
    
    # 3. Segurança
    max_message_termination = MaxMessageTermination(max_messages=20)
    
    # Combinar: Pára se QUALQUER uma acontecer
    termination_condition = text_termination | budget_termination | max_message_termination
    
    print("\n Condições de término configuradas:")
    print("   - TextMention: 'TERMINATE'")
    print("   - TextMention: 'indique o seu orçamento' (NOVO!)")
    print("   - MaxMessages: 20")
    
    # ============================================
    # CRIAR TEAM
    # ============================================
    
    team = RoundRobinGroupChat(
        participants=[
            planner,
            location_agent,
            property_agent,
            analyst,
            evaluator
        ],
        termination_condition=termination_condition
    )
    
    print(f"\n Query do utilizador:")
    print(f'"{user_query}"')
    
    print("\n Iniciando team...")
    
    # Executar team
    result = await Console(team.run_stream(task=user_query))
    
    print("\n Team concluído!")
    
    # Extrair resultados
    messages = result.messages if hasattr(result, 'messages') else []
    
    # Organizar por agente
    results = {
        'planner': [],
        'location': [],
        'property': [],
        'analyst': [],
        'evaluator': [],
        'all_messages': messages,
        'stop_reason': getattr(result, 'stop_reason', 'unknown')
    }
    
    for msg in messages:
        source = getattr(msg, 'source', 'unknown')
        content = getattr(msg, 'content', '')
        
        # Normalizar nomes dos agentes
        source_lower = source.lower()
        
        if 'planner' in source_lower:
            results['planner'].append(content)
        elif 'location' in source_lower:
            results['location'].append(content)
        elif 'property' in source_lower:
            results['property'].append(content)
        elif 'analyst' in source_lower:
            results['analyst'].append(content)
        elif 'evaluator' in source_lower:
            results['evaluator'].append(content)
    
    print(f"\n Razão de término: {results['stop_reason']}")
    
    await model_client.close()
    
    return results


async def main():
    """Execução standalone para teste."""
    
    # Teste sem budget para ver se pára
    user_query = "Quero comprar um apartamento T2 em Lisboa."
    
    results = await run_property_recommendation_system(user_query)
    
    print("\n" + "=" * 80)
    print(" RESULTADOS FINAIS")
    print("=" * 80)
    
    # Se parou no Planner, mostra a pergunta
    if results['planner'] and "orçamento" in results['planner'][-1].lower():
        print("\nO SISTEMA PAROU PARA PEDIR INFORMAÇÃO:")
        print(results['planner'][-1])
    
    # Mostrar recomendações do Evaluator (se existirem)
    elif results['evaluator']:
        print("\n RECOMENDAÇÕES DO EVALUATOR:")
        print(results['evaluator'][-1])
    
    print("\n Sistema concluído!")
