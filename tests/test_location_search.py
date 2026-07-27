"""
Testes unitários de tools/location_search.py relacionados com a integração
do retrieval semântico (Fase 2). A pesquisa semântica, o clima e o LLM são
mockados - sem rede, sem chaves de API. Ver docs/FASE1_DECISOES.txt para o
estilo geral e docs/FASE2_DECISOES.txt secção 6 para o porquê do sentinela
NO_PREFERENCE_SENTINEL.
"""

import asyncio

import tools.location_search as location_search


async def _fake_get_weather_data(lat, lon):
    return {"current": {"temperature_2m": 20, "precipitation": 0}}


async def _fake_analyze_weather_with_llm(weather_data, environment_type, model_client):
    return 0.7


def test_equilibrado_sentinel_skips_semantic_search(monkeypatch):
    """
    NO_PREFERENCE_SENTINEL ("equilibrado") é o default de environment_type
    em find_locations_wrapper quando o utilizador não especifica um ambiente.
    find_best_locations deve tratá-lo como "sem preferência" - sem chamar a
    pesquisa semântica, e com characteristics_score neutro (0.5) para os
    candidatos, exatamente como acontecia antes desta fase.
    """
    called = False

    def fake_semantic_query(environment_text, top_k=20):
        nonlocal called
        called = True
        return [("pt_norte_porto", 0.9)]

    monkeypatch.setattr(location_search, "semantic_query", fake_semantic_query)
    monkeypatch.setattr(location_search, "get_weather_data", _fake_get_weather_data)
    monkeypatch.setattr(location_search, "analyze_weather_with_llm", _fake_analyze_weather_with_llm)

    results = asyncio.run(
        location_search.find_best_locations(
            location_hint="Porto",
            environment_type="equilibrado",
            top_n=1,
            model_client=None,
        )
    )

    assert called is False
    assert results[0]["characteristics_score"] == 0.5


def test_real_environment_type_uses_semantic_search(monkeypatch):
    """Contraste com o teste acima: um environment_type real chama a pesquisa semântica."""
    called_with = []

    def fake_semantic_query(environment_text, top_k=20):
        called_with.append(environment_text)
        return [("pt_norte_porto", 0.85)]

    monkeypatch.setattr(location_search, "semantic_query", fake_semantic_query)
    monkeypatch.setattr(location_search, "get_weather_data", _fake_get_weather_data)
    monkeypatch.setattr(location_search, "analyze_weather_with_llm", _fake_analyze_weather_with_llm)

    results = asyncio.run(
        location_search.find_best_locations(
            location_hint="Porto",
            environment_type="tranquilo e histórico",
            top_n=1,
            model_client=None,
        )
    )

    assert called_with == ["tranquilo e histórico"]
    assert results[0]["characteristics_score"] == 0.85
