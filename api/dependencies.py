from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from autogen_ext.models.openai import OpenAIChatCompletionClient

from utils import create_model_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cria o model_client uma vez no arranque da app e fecha-o no shutdown."""
    app.state.model_client = create_model_client()
    yield
    await app.state.model_client.close()


def get_model_client(request: Request) -> OpenAIChatCompletionClient:
    """Dependency: devolve o model_client partilhado, gerido pelo lifespan."""
    return request.app.state.model_client


def is_model_client_ready(request: Request) -> bool:
    """Usado por GET /api/health para reportar se o model_client está operacional."""
    return getattr(request.app.state, "model_client", None) is not None
