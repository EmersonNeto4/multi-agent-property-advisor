"""Modelos Pydantic (request/response) da API. Ver docs/FASE1_DECISOES.txt para as decisões de design."""

from typing import List, Optional
from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    """Corpo do pedido para POST /api/recommend."""

    query: str = Field(
        ...,
        description="Descrição em linguagem natural do imóvel procurado"
    )


class AgentOutput(BaseModel):
    """Saída de um agente: última mensagem (o que a UI mostra por defeito) + trace completo."""

    final: str = Field(..., description="Última mensagem do agente")
    messages: List[str] = Field(default_factory=list, description="Todas as mensagens do agente, por ordem")


class RecommendResponse(BaseModel):
    """Resposta de POST /api/recommend: saída de cada agente + estado de término."""

    planner: Optional[AgentOutput] = None
    location: Optional[AgentOutput] = None
    property: Optional[AgentOutput] = None
    analyst: Optional[AgentOutput] = None
    evaluator: Optional[AgentOutput] = None

    stop_reason: str = Field(..., description="Razão de término do team (AutoGen)")
    needs_more_info: bool = Field(
        default=False,
        description="True se o sistema parou a meio a pedir mais informação ao utilizador (ex: orçamento)"
    )
    message: Optional[str] = Field(
        default=None,
        description="Mensagem explícita a mostrar ao utilizador quando needs_more_info é True"
    )


class HealthResponse(BaseModel):
    """Resposta de GET /api/health."""

    status: str
    model_client_ready: bool


class LocationCoordinates(BaseModel):
    latitude: float
    longitude: float


class LocationResponse(BaseModel):
    """Uma entrada de GET /api/locations. Estrutura igual à de data/portugal_locations.json."""

    id: str
    name: str
    type: str
    nuts_ii: str
    nuts_iii: str
    population: int
    coordinates: LocationCoordinates
    characteristics: List[str]
