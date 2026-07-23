"""Gestão do model_client partilhado (criado uma vez no lifespan). Ver docs/FASE1_DECISOES.txt."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from autogen_ext.models.openai import OpenAIChatCompletionClient

from utils import create_model_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cria o model_client no arranque da app e fecha-o no shutdown."""
    app.state.model_client = create_model_client()
    yield
    await app.state.model_client.close()


def get_model_client(request: Request) -> OpenAIChatCompletionClient:
    """Dependency que devolve o model_client partilhado aos endpoints."""
    return request.app.state.model_client


def is_model_client_ready(request: Request) -> bool:
    """Indica se o model_client já foi criado (usado por GET /api/health)."""
    return getattr(request.app.state, "model_client", None) is not None
