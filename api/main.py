from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import lifespan, is_model_client_ready
from api.schemas import HealthResponse

app = FastAPI(title="Sistema Multi-Agente de Recomendação de Imóveis", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health(request: Request):
    ready = is_model_client_ready(request)
    return HealthResponse(
        status="ok" if ready else "degraded",
        model_client_ready=ready,
    )
