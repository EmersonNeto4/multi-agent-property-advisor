"""
Testes unitários de tools/semantic_search.py. O embedder (SentenceTransformer)
e o ChromaDB são ambos mockados - nenhum teste aqui descarrega/carrega o
modelo real, faz chamadas de rede, ou toca no ChromaDB real (que mantém as
coleções registadas por nome dentro do mesmo processo, mesmo em modo
"ephemeral" - reutilizar o real entre testes dava "Collection already
exists"). Para um teste com embeddings e índice reais (marcado slow,
excluído da execução default), ver tests/test_semantic_search_slow.py.
"""

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


class FakeCollection:
    """Faz nearest-neighbor real (numpy) sobre os embeddings fake - suficiente
    para os testes verificarem ordenação/formato sem depender do ChromaDB real."""

    def __init__(self):
        self._ids = []
        self._embeddings = None

    def add(self, ids, documents, embeddings):
        self._ids = list(ids)
        self._embeddings = np.array(embeddings)

    def query(self, query_embeddings, n_results):
        query_emb = np.array(query_embeddings[0])
        sims = self._embeddings @ query_emb  # embeddings normalizados -> cosseno
        order = np.argsort(-sims)[:n_results]
        ids = [self._ids[i] for i in order]
        distances = [1.0 - float(sims[i]) for i in order]
        return {"ids": [ids], "distances": [distances]}


class FakeChromaClient:
    def create_collection(self, name, metadata=None):
        return FakeCollection()


def _mock_embedder(monkeypatch, sentence_transformer_cls=FakeSentenceTransformer):
    monkeypatch.setattr("sentence_transformers.SentenceTransformer", sentence_transformer_cls)
    monkeypatch.setattr("chromadb.EphemeralClient", FakeChromaClient)


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
        semantic_search._collection = None
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
