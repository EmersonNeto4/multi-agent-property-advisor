"""
Testes unitários de tools/semantic_search.py. Só o embedder
(SentenceTransformer) é mockado - nenhum teste aqui descarrega/carrega o
modelo real nem faz chamadas de rede. Para um teste com embeddings reais
(marcado slow, excluído da execução default), ver
tests/test_semantic_search_slow.py.

Desde a Fase 2.5 não há nada a mockar do lado do índice: a pesquisa é uma
multiplicação matriz-vetor com numpy sobre os embeddings em memória, por isso
os testes exercitam a pesquisa a sério e não um substituto dela.
"""

import json

import numpy as np
import pytest

import tools.semantic_search as semantic_search


class FakeSentenceTransformer:
    """
    Substituto determinístico do SentenceTransformer real: gera um vetor fixo
    por texto (a partir de um hash), sem qualquer download ou rede. Não
    pretende ser semanticamente coerente - só testa a estrutura/fluxo do
    módulo (is_available, query, fallback), não a qualidade do ranking (isso
    é o teste slow, com o modelo real).
    """

    def __init__(self, model_name):
        self.model_name = model_name

    def encode(self, texts, normalize_embeddings=True):
        vectors = []
        for text in texts:
            rng = np.random.default_rng(abs(hash(text)) % (2**32))
            vec = rng.normal(size=8)
            if normalize_embeddings:
                vec = vec / np.linalg.norm(vec)
            vectors.append(vec)
        return np.array(vectors)


def _mock_embedder(monkeypatch, sentence_transformer_cls=FakeSentenceTransformer):
    monkeypatch.setattr("sentence_transformers.SentenceTransformer", sentence_transformer_cls)


@pytest.fixture(autouse=True)
def reset_singleton():
    """
    is_available()/query() usam um singleton lazy a nível de módulo (ver
    docstring de _load()) - sem repor este estado entre testes, o primeiro
    teste que carregar (ou falhar a carregar) o "modelo" contaminaria todos
    os seguintes.
    """
    def _reset():
        semantic_search._model = None
        semantic_search._ids = []
        semantic_search._embeddings = None
        semantic_search._num_docs = 0
        semantic_search._load_failed = False

    _reset()
    yield
    _reset()


def test_is_available_true_with_mocked_embedder(monkeypatch):
    _mock_embedder(monkeypatch)
    assert semantic_search.is_available() is True


def test_query_returns_sorted_similarity_tuples(monkeypatch):
    _mock_embedder(monkeypatch)

    results = semantic_search.query("qualquer coisa", top_k=5)

    assert len(results) == 5
    for location_id, similarity in results:
        assert isinstance(location_id, str)
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0

    similarities = [s for _, s in results]
    assert similarities == sorted(similarities, reverse=True)


def test_query_similarities_are_the_cosine_of_the_embeddings(monkeypatch):
    """
    A similaridade devolvida tem de ser o cosseno entre a query e o documento,
    calculado aqui de forma independente do módulo. É o teste que substitui o
    antigo FakeCollection: antes verificava-se que o módulo falava
    corretamente com o ChromaDB; agora verifica-se a própria aritmética da
    pesquisa, que passou a ser nossa.
    """
    _mock_embedder(monkeypatch)

    text = "zona sossegada"
    results = semantic_search.query(text, top_k=42)

    expected_query_vec = FakeSentenceTransformer(semantic_search.MODEL_NAME).encode([text])[0]
    embeddings_by_id = dict(zip(semantic_search._ids, semantic_search._embeddings))

    for location_id, similarity in results:
        expected = float(embeddings_by_id[location_id] @ expected_query_vec)
        assert similarity == pytest.approx(max(0.0, expected), abs=1e-6)


def test_all_descriptions_are_indexed(monkeypatch):
    _mock_embedder(monkeypatch)
    semantic_search.is_available()

    with open(semantic_search.DESCRIPTIONS_PATH, "r", encoding="utf-8") as f:
        descriptions = json.load(f)

    assert semantic_search._num_docs == len(descriptions)
    assert semantic_search._ids == list(descriptions.keys())
    assert semantic_search._embeddings.shape[0] == len(descriptions)


def test_query_respects_top_k(monkeypatch):
    _mock_embedder(monkeypatch)
    assert len(semantic_search.query("teste", top_k=3)) == 3
    assert len(semantic_search.query("teste", top_k=1)) == 1


@pytest.mark.parametrize("empty_text", ["", "   ", None])
def test_query_empty_text_returns_empty_list(monkeypatch, empty_text):
    _mock_embedder(monkeypatch)
    assert semantic_search.query(empty_text) == []


def test_fallback_when_model_fails_to_load(monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("sem rede - simulado no teste")

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", _raise)

    assert semantic_search.is_available() is False
    assert semantic_search.query("qualquer coisa") == []


def test_load_is_idempotent(monkeypatch):
    """_load() só deve instanciar o modelo uma vez, mesmo com várias chamadas a query()/is_available()."""
    calls = []

    class CountingFakeSentenceTransformer(FakeSentenceTransformer):
        def __init__(self, model_name):
            calls.append(model_name)
            super().__init__(model_name)

    _mock_embedder(monkeypatch, CountingFakeSentenceTransformer)

    semantic_search.query("primeira")
    semantic_search.query("segunda")
    semantic_search.is_available()

    assert len(calls) == 1
