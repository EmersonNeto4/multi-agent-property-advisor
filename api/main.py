"""API FastAPI do Sistema Multi-Agente de Recomendação de Imóveis. Ver docs/FASE1_DECISOES.txt para as decisões de arquitetura."""

import logging
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError

from api.dependencies import get_model_client, is_model_client_ready, lifespan
from api.schemas import AgentOutput, HealthResponse, LocationResponse, RecommendRequest, RecommendResponse
from main import run_property_recommendation_system
from tools.data_loader import get_all_locations

logger = logging.getLogger(__name__)

app = FastAPI(title="Sistema Multi-Agente de Recomendação de Imóveis", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health(request: Request):
    """Health check: confirma se a app e o model_client estão operacionais."""
    ready = is_model_client_ready(request)
    return HealthResponse(
        status="ok" if ready else "degraded",
        model_client_ready=ready,
    )


def _agent_output(messages: List[str]) -> Optional[AgentOutput]:
    """Converte a lista de mensagens de um agente em AgentOutput (ou None se o agente não correu)."""
    if not messages:
        return None
    return AgentOutput(final=messages[-1], messages=messages)


@app.post("/api/recommend", response_model=RecommendResponse)
async def recommend(payload: RecommendRequest, model_client=Depends(get_model_client)):
    """Executa o sistema multi-agente para uma query em linguagem natural e devolve os resultados por agente."""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="A query não pode estar vazia.")

    try:
        results = await run_property_recommendation_system(query, model_client=model_client)
    except RateLimitError:
        raise HTTPException(
            status_code=503,
            detail="Limite de pedidos à Groq API atingido. Tenta novamente dentro de momentos.",
        )
    except (APITimeoutError, APIConnectionError):
        raise HTTPException(
            status_code=503,
            detail="O modelo demorou demasiado tempo a responder. Tenta novamente.",
        )
    except APIError:
        logger.exception("Erro da API do modelo ao processar recomendação")
        raise HTTPException(status_code=502, detail="Erro ao comunicar com o modelo de linguagem.")
    except Exception:
        logger.exception("Erro inesperado ao executar o sistema multi-agente")
        raise HTTPException(status_code=500, detail="Erro interno ao processar o pedido.")

    planner_messages = results.get("planner", [])
    needs_more_info = bool(planner_messages) and "orçamento" in planner_messages[-1].lower()

    return RecommendResponse(
        planner=_agent_output(planner_messages),
        location=_agent_output(results.get("location", [])),
        property=_agent_output(results.get("property", [])),
        analyst=_agent_output(results.get("analyst", [])),
        evaluator=_agent_output(results.get("evaluator", [])),
        stop_reason=str(results.get("stop_reason", "unknown")),
        needs_more_info=needs_more_info,
        message=planner_messages[-1] if needs_more_info else None,
    )


@app.get("/api/locations", response_model=List[LocationResponse])
async def locations():
    """Devolve a lista de localizações disponíveis (data/portugal_locations.json)."""
    try:
        return get_all_locations()
    except Exception:
        logger.exception("Erro ao carregar o dataset de localizações")
        raise HTTPException(status_code=500, detail="Erro ao carregar as localizações.")


# Montado por último para não sombrear as rotas /api/*: pedidos a caminhos
# não reconhecidos acima (incluindo "/") são servidos a partir de frontend/.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
