"""
Retrieval semântico de localizações a partir de uma descrição de ambiente em
linguagem natural (ex: "sítio pacato perto do oceano"). Substitui o
keyword_mapping hardcoded que existia em tools/location_search.py.

Ver docs/FASE2_DECISOES.txt para o porquê do modelo escolhido e da estratégia
de fallback, e docs/FASE2.5_DECISOES.txt para o porquê de a pesquisa ser feita
com numpy em vez de ChromaDB.
"""

import json
import logging
from pathlib import Path
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

DESCRIPTIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "portugal_locations_descriptions.json"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Estado do singleton lazy (ver _load()). Nunca acedido diretamente fora
# deste módulo - usar is_available() e query().
_model = None
_ids: List[str] = []
_embeddings = None  # np.ndarray (n_docs, dim), normalizado por linha
_num_docs = 0
_load_failed = False


def _load() -> None:
    """
    Carrega o modelo de embeddings e constrói o índice em memória a partir de
    data/portugal_locations_descriptions.json. Idempotente: só faz trabalho
    real na primeira chamada (singleton lazy) - chamadas seguintes são no-op
    enquanto _embeddings/_load_failed já estiverem definidos.

    Deliberadamente NÃO é chamado no lifespan da API: carregar um modelo de
    embeddings multilingue em CPU pode demorar vários segundos, e a maioria
    dos pedidos à app (ex: GET /api/health) não precisa disto. Só corre no
    primeiro pedido que de facto chame query()/is_available() - o Location
    Agent, através de find_best_locations().

    Nunca levanta exceção: se falhar (sem rede, sem cache do modelo, versão
    incompatível), regista o erro via logging e marca _load_failed=True.
    is_available()/query() refletem essa falha em vez de rebentar - quem
    chama degrada para "sem informação semântica" (ver location_search.py).
    """
    global _model, _ids, _embeddings, _num_docs, _load_failed

    if _embeddings is not None or _load_failed:
        return

    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(MODEL_NAME)

        with open(DESCRIPTIONS_PATH, "r", encoding="utf-8") as f:
            descriptions = json.load(f)

        ids = list(descriptions.keys())
        documents = [descriptions[loc_id]["description"] for loc_id in ids]
        embeddings = np.asarray(model.encode(documents, normalize_embeddings=True), dtype=np.float32)

        _model = model
        _ids = ids
        _embeddings = embeddings
        _num_docs = len(ids)
        logger.info("Retrieval semantico pronto: %d localizacoes indexadas (%s)", _num_docs, MODEL_NAME)
    except Exception:
        logger.exception(
            "Falha ao carregar o modelo de embeddings ou construir o indice semantico - "
            "retrieval semantico fica indisponivel, find_best_locations degrada para "
            "ignorar environment_type"
        )
        _load_failed = True


def is_available() -> bool:
    """Indica se o retrieval semântico está operacional (tenta carregar, se ainda não tiver sido tentado)."""
    _load()
    return _embeddings is not None


def query(environment_text: str, top_k: int = 20) -> List[Tuple[str, float]]:
    """
    Devolve até top_k localizações mais similares semanticamente a
    environment_text, como [(location_id, similarity), ...] ordenado do
    mais para o menos similar. similarity está aproximadamente em [0, 1]
    (1 = idêntico).

    Lista vazia se o retrieval não estiver disponível (ver is_available()) -
    isto NÃO é um erro para quem chama, é o sinal para tratar a pesquisa
    como se environment_text não tivesse sido fornecido.
    """
    if not environment_text or not environment_text.strip():
        return []

    _load()
    if _embeddings is None:
        return []

    query_embedding = np.asarray(
        _model.encode([environment_text], normalize_embeddings=True), dtype=np.float32
    )[0]

    # Documentos e query normalizados (norma 1) -> o produto interno É a
    # similaridade de cosseno. Com 42 vetores de 384 dimensões, a pesquisa
    # exaustiva é uma única multiplicação matriz-vetor (~16k multiplicações):
    # um índice aproximado (HNSW) não teria nada a acelerar aqui.
    similarities = _embeddings @ query_embedding

    n_results = min(top_k, _num_docs)
    # argsort decrescente; kind="stable" para a ordem entre empates exatos ser
    # determinística (a ordem do ficheiro de descrições) em vez de arbitrária.
    order = np.argsort(-similarities, kind="stable")[:n_results]

    # Clamp a [0, 1] (o cosseno raramente é negativo entre frases do mesmo
    # domínio, mas protege o caso limite e mantém o contrato da função).
    return [(_ids[i], float(np.clip(similarities[i], 0.0, 1.0))) for i in order]


if __name__ == "__main__":
    # Teste standalone rápido - ver docs/FASE2_DECISOES.txt para o output real.
    logging.basicConfig(level=logging.INFO)

    example_queries = [
        "quero sossego perto do mar",
        "cidade com vida noturna",
        "zona rural nas montanhas",
        "um sítio pacato, perto do oceano",  # sinónimos que o keyword_mapping antigo não apanhava
    ]

    for q in example_queries:
        print(f"\nQuery: {q!r}")
        for location_id, similarity in query(q, top_k=5):
            print(f"  {similarity:.3f}  {location_id}")
