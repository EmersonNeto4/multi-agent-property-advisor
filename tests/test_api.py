"""Testes mínimos da API. Nenhum teste chama a Groq ou o Idealista de facto —
ver docs/FASE1_DECISOES.txt secção 11 para o porquê de cada escolha de mocking."""

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from api.dependencies import get_model_client
from api.main import app
from api.schemas import HealthResponse, LocationResponse

FAKE_RESULTS = {
    "planner": ["Preferências extraídas com sucesso: T2 em Lisboa, budget de 400 mil euros."],
    "location": ["Localização candidata: Lisboa."],
    "property": ["3 imóveis encontrados que satisfazem as restrições CSP."],
    "analyst": ["Ranking KNN calculado para os 3 imóveis."],
    "evaluator": ["Recomendação final: o imóvel A é o mais adequado. TERMINATE"],
    "all_messages": [],
    "stop_reason": "Text 'TERMINATE' mentioned",
}


@pytest.fixture
def client():
    """
    TestClient só corre o lifespan (startup/shutdown) quando usado como context
    manager ("with TestClient(app) as c"). Instanciar diretamente evita isso,
    o que é necessário aqui: o lifespan real cria o model_client via
    create_model_client(), que rebentaria sem GROQ_API_KEY (o CI corre sem .env).
    get_model_client é sobreposto via dependency_overrides para os endpoints
    que o exigem.
    """
    app.dependency_overrides[get_model_client] = lambda: object()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    HealthResponse(**response.json())


def test_locations(client):
    response = client.get("/api/locations")
    assert response.status_code == 200

    body = response.json()
    assert len(body) == 42

    first = LocationResponse(**body[0])
    assert first.id
    assert first.name
    assert first.coordinates is not None


def test_recommend_empty_query(client):
    response = client.post("/api/recommend", json={"query": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "A query não pode estar vazia."


def test_recommend_valid_query(client, monkeypatch):
    async def fake_run_property_recommendation_system(user_query, model_client=None):
        return FAKE_RESULTS

    monkeypatch.setattr(
        api_main,
        "run_property_recommendation_system",
        fake_run_property_recommendation_system,
    )

    response = client.post(
        "/api/recommend",
        json={"query": "Quero um apartamento T2 em Lisboa, orçamento 400 mil euros."},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["planner"]["final"] == FAKE_RESULTS["planner"][-1]
    assert body["evaluator"]["final"] == FAKE_RESULTS["evaluator"][-1]
    assert body["stop_reason"] == FAKE_RESULTS["stop_reason"]
    assert body["needs_more_info"] is False
    assert body["message"] is None
