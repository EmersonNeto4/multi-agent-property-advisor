import os
from dotenv import load_dotenv
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv()

# ============================================
# API Keys
# ============================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

IDEALISTA_API_KEY = os.getenv("IDEALISTA_API_KEY")
IDEALISTA_API_SECRET = os.getenv("IDEALISTA_API_SECRET")
IDEALISTA_API_URL = "https://api.idealista.com/3.5"

# ============================================
# Model Configuration
# ============================================

DEFAULT_MODEL = "llama-3.3-70b-versatile"
BASE_URL = "https://api.groq.com/openai/v1"

DEFAULT_MODEL_CAPABILITIES = {
    "vision": False,
    "function_calling": True,
    "json_output": True,
    "structured_output": True,
    "family": "llama"
}


# ============================================
# Helper Functions
# ============================================

def create_model_client(
    model: str = DEFAULT_MODEL,
    api_key: str = None,
    base_url: str = BASE_URL
) -> OpenAIChatCompletionClient:
    """
    Cria um cliente de modelo configurado.
    
    Args:
        model: Nome do modelo a usar
        api_key: API key (usa OPENROUTER_API_KEY por padrão)
        base_url: Base URL da API
        
    Returns:
        OpenAIChatCompletionClient configurado
    """
    if api_key is None:
        api_key = GROQ_API_KEY
    
    return OpenAIChatCompletionClient(
        model=model,
        api_key=api_key, 
        base_url=base_url,
        model_capabilities=DEFAULT_MODEL_CAPABILITIES,
        )