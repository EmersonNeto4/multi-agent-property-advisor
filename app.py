import streamlit as st
import asyncio
from main import run_property_recommendation_system
import re

# Configuração da página
st.set_page_config(
    page_title="Sistema de Recomendação de Imóveis",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)


# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .agent-card {
        padding: 1rem;
        border-radius: 10px;
        background-color: #f0f2f6;
        margin: 1rem 0;
    }
    .property-card {
        padding: 1.5rem;
        border-radius: 10px;
        background-color: #ffffff;
        border: 2px solid #e0e0e0;
        margin: 1rem 0;
    }
    .stButton>button {
        width: 100%;
        background-color: #1f77b4;
        color: white;
        font-size: 1.2rem;
        padding: 0.75rem;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# Header
st.markdown('<div class="main-header">🏠 Sistema Multi-Agente de Recomendação de Imóveis</div>', 
            unsafe_allow_html=True)

st.markdown("""
Este sistema utiliza **5 agentes inteligentes** que colaboram para encontrar o imóvel perfeito:
- 🧠 **Planner**: Extrai suas preferências
- 📍 **Location Agent**: Encontra as melhores regiões
- 🏠 **Property Agent**: Busca imóveis (API + CSP + A*)
- 📊 **Data Analyst**: Aplica KNN para ranking
- 🎯 **Evaluator**: Cria recomendações finais
""")

st.divider()


# Sidebar com informações
with st.sidebar:
    st.header("ℹ️ Sobre o Sistema")
    
    st.markdown("""
    **Tecnologias:**
    - AutoGen (Multi-Agent)
    - Llama 3.3 - 70B
    - Idealista API
    - KNN (sklearn)
    - A* Search
    - CSP Solver
    
    **Algoritmos:**
    - CSP para filtragem
    - A* para proximidade
    - KNN para ranking
    """)
    
    st.divider()
    
    st.markdown("""
    **Desenvolvido por:**
    - Emerson Neto e Gonçalo Bento - IARP 2025/2026
    - Universidade de Coimbra
    """)


# Input do utilizador
st.header("📝 Descreva o que procura")

# Opção 1: Texto livre
tab1, tab2 = st.tabs(["✍️ Texto Livre", "📋 Formulário"])

with tab1:
    user_query = st.text_area(
        "Descreva o imóvel que procura:",
        placeholder="""Exemplo:
Quero um apartamento T2 em Lisboa, perto do Hospital Santa Maria, 
com orçamento máximo de 400 mil euros.""",
        height=150
    )

with tab2:
    col1, col2 = st.columns(2)
    
    with col1:
        location = st.text_input("📍 Localização", placeholder="Lisboa")
        rooms = st.number_input("🛏️ Quartos (T)", min_value=0, max_value=5, value=2)
        budget = st.number_input("💰 Budget (€)", min_value=0, max_value=5000000, 
                                  value=400000, step=10000)
    
    with col2:
        service = st.text_input("🏥 Proximidade a serviço (opcional)", 
                                placeholder="Hospital Santa Maria")
        bathrooms = st.number_input("🚿 Casas de banho (mín.)", min_value=0, max_value=5, value=1)
        area = st.number_input("📐 Área mínima (m²)", min_value=0, max_value=500, value=0)
    
    # Construir query a partir do formulário
    if st.button("🔄 Gerar Query a partir do formulário"):
        form_query = f"Quero um apartamento T{rooms} em {location}"
        
        if budget > 0:
            form_query += f", com orçamento máximo de {budget:,} euros".replace(',', ' ')
        
        if service:
            form_query += f", perto de {service}"
        
        if bathrooms > 0:
            form_query += f", com pelo menos {bathrooms} casa(s) de banho"
        
        if area > 0:
            form_query += f", e área mínima de {area}m²"
        
        form_query += "."
        
        user_query = form_query
        st.success(f"Query gerada: {form_query}")


# Botão de pesquisa
st.divider()

if st.button("🚀 Iniciar Pesquisa Multi-Agente", type="primary"):
    
    if not user_query or user_query.strip() == "":
        st.error("❌ Por favor, descreva o que procura!")
    
    has_budget = re.search(r'\d{3,}', user_query) or re.search(r'euros|€|mil', user_query, re.IGNORECASE)
    
    if not has_budget:
        st.warning("⚠️ Parece que não indicou um orçamento.")
        st.info("Por favor, inclua um valor (ex: 500000) na sua descrição.")
        st.stop() # Pára a execução aqui
    else:
        # Placeholder para progresso
        progress_placeholder = st.empty()
        results_placeholder = st.empty()
        
        with progress_placeholder.container():
            st.info("🔄 Sistema Multi-Agente em execução...")
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Simular progresso (em produção, capturar eventos reais dos agentes)
            status_text.text("🧠 Planner Agent extraindo preferências...")
            progress_bar.progress(20)
            
            # Executar sistema
            try:
                # Executar em loop assíncrono
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                status_text.text("📍 Location Agent encontrando regiões...")
                progress_bar.progress(40)
                
                # Executar
                results = loop.run_until_complete(
                    run_property_recommendation_system(user_query)
                )
                
                status_text.text("🏠 Property Agent buscando imóveis...")
                progress_bar.progress(60)
                
                status_text.text("📊 Data Analyst aplicando KNN...")
                progress_bar.progress(80)
                
                status_text.text("🎯 Evaluator criando recomendações...")
                progress_bar.progress(100)
                
                status_text.text("✅ Análise concluída!")
                
                # Limpar progress
                progress_placeholder.empty()
                
                # Mostrar resultados
                with results_placeholder.container():
                    st.success("✅ Sistema Multi-Agente concluído com sucesso!")
                    
                    # Tabs para diferentes agentes
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "🎯 Recomendações Finais",
                        "📊 Análise do Data Analyst",
                        "🏠 Imóveis Encontrados",
                        "📍 Localizações",
                        "🧠 Preferências Extraídas"
                    ])
                    
                    # Tab 1: Evaluator (principal)
                    with tab1:
                        st.header("🏆 Recomendações do Evaluator Agent")
                        
                        if results.get('evaluator'):
                            # Mostrar última mensagem do evaluator
                            evaluator_response = results['evaluator'][-1]
                            st.markdown(evaluator_response)
                        else:
                            st.warning("Sem recomendações do Evaluator")
                    
                    # Tab 2: Data Analyst
                    with tab2:
                        st.header("📊 Análise KNN do Data Analyst")
                        
                        if results.get('analyst'):
                            analyst_response = results['analyst'][-1]
                            st.markdown(analyst_response)
                        else:
                            st.info("Análise do Data Analyst não disponível")
                    
                    # Tab 3: Property Agent
                    with tab3:
                        st.header("🏠 Imóveis Encontrados")
                        
                        if results.get('property'):
                            property_response = results['property'][-1]
                            st.markdown(property_response)
                        else:
                            st.info("Dados do Property Agent não disponíveis")
                    
                    # Tab 4: Location Agent
                    with tab4:
                        st.header("📍 Análise de Localizações")
                        
                        if results.get('location'):
                            location_response = results['location'][-1]
                            st.markdown(location_response)
                        else:
                            st.info("Dados do Location Agent não disponíveis")
                    
                    # Tab 5: Planner
                    with tab5:
                        st.header("🧠 Preferências Extraídas")
                        
                        if results.get('planner'):
                            planner_response = results['planner'][-1]
                            st.markdown(planner_response)
                        else:
                            st.info("Dados do Planner não disponíveis")
                    
                    # Botão para nova pesquisa
                    st.divider()
                    if st.button("🔄 Nova Pesquisa"):
                        st.rerun()
            
            except Exception as e:
                progress_placeholder.empty()
                st.error(f"❌ Erro ao executar sistema: {str(e)}")
                st.exception(e)


# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem;'>
    <p>🏠 Sistema Multi-Agente de Recomendação de Imóveis</p>
    <p>Powered by AutoGen + Llama 3.3 + Idealista API</p>
</div>
""", unsafe_allow_html=True)