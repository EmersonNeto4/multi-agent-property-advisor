"""
Teste de integração de tools/semantic_search.py com o modelo de embeddings
REAL (descarrega-o na primeira vez que corre numa máquina/CI sem cache local).
Marcado @pytest.mark.slow - excluído da execução default do pytest (ver
addopts em pyproject.toml). Corre explicitamente com: pytest -m slow
"""

import json
from pathlib import Path

import pytest

from tools.semantic_search import query

LOCATIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "portugal_locations.json"


@pytest.mark.slow
def test_coastal_query_ranks_coastal_locations_first():
    """
    Uma query de ambiente costeiro deve devolver localizações costeiras à
    frente de localizações de interior/montanha. Usa "praia e costa" (não
    "perto do mar") porque o benchmark documentado em
    docs/FASE2_DECISOES.txt (secção 2) mostrou que frases mais amplas como
    "perto do mar" por vezes trazem localizações de interior (ex: Viseu)
    para o top 5 - "praia e costa" dá um sinal mais limpo e é o que este
    teste verifica de forma estável.
    """
    with open(LOCATIONS_PATH, "r", encoding="utf-8") as f:
        locations_data = json.load(f)["locations"]
    characteristics_by_id = {loc["id"]: set(loc["characteristics"]) for loc in locations_data}

    results = query("praia e costa", top_k=5)
    assert len(results) == 5

    for location_id, _similarity in results:
        tags = characteristics_by_id[location_id]
        assert "interior" not in tags and "montanha" not in tags, (
            f"{location_id} tem tags de interior/montanha {tags} - não devia "
            f"aparecer no top 5 de uma query de ambiente costeiro"
        )
