"""
Retrieval semântico de localizações a partir de uma descrição de ambiente em
linguagem natural (ex: "sítio pacato perto do oceano"). Substitui o
keyword_mapping hardcoded que existia em tools/location_search.py.

Ver docs/FASE2_DECISOES.txt para o porquê de cada decisão: modelo escolhido,
índice em memória (sem persistência) e a estratégia de fallback.
"""

import json
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

DESCRIPTIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "portugal_locations_descriptions.json"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "portugal_locations"

# Estado do singleton lazy (ver _load()). Nunca acedido diretamente fora
# deste módulo - usar is_available() e query().
_model = None
_collection = None
_num_docs = 0
_load_failed = False


def _load() -> None:
    """
    Carrega o modelo de embeddings e constrói a coleção Chroma em memória a
    partir de data/portugal_locations_descriptions.json. Idempotente: só faz
    trabalho real na primeira chamada (singleton lazy) - chamadas seguintes
    são no-op enquanto _collection/_load_failed já estiverem definidos.

    Deliberadamente NÃO é chamado no lifespan da API: carregar um modelo de
    embeddings multilingue em CPU (download na primeira vez + inicialização
    do torch) pode demorar vários segundos, e a maioria dos pedidos à app
    (ex: GET /api/health) não precisa disto. Só corre no primeiro pedido que
    de facto chame query()/is_available() - o Location Agent, através de
    find_best_locations().

    Nunca levanta exceção: se falhar (sem rede, sem cache do modelo, versão
    incompatível), regista o erro via logging e marca _load_failed=True.
    is_available()/query() refletem essa falha em vez de rebentar - quem
    chama degrada para "sem informação semântica" (ver location_search.py).
    """
    global _model, _collection, _num_docs, _load_failed

    if _collection is not None or _load_failed:
        return

    try:
        from sentence_transformers import SentenceTransformer
        import chromadb

        model = SentenceTransformer(MODEL_NAME)

        with open(DESCRIPTIONS_PATH, "r", encoding="utf-8") as f:
            descriptions = json.load(f)

        ids = list(descriptions.keys())
        documents = [descriptions[loc_id]["description"] for loc_id in ids]
        embeddings = model.encode(documents, normalize_embeddings=True).tolist()

        # Cliente em memória, sem persistência em disco (ver secção 3 do
        # design da Fase 2): reconstruir a coleção custa frações de segundo
        # depois do modelo carregado, para 42 documentos.
        client = chromadb.EphemeralClient()
        collection = client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        collection.add(ids=ids, documents=documents, embeddings=embeddings)

        _model = model
        _collection = collection
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
    return _collection is not None


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
    if _collection is None:
        return []

    query_embedding = _model.encode([environment_text], normalize_embeddings=True).tolist()
    n_results = min(top_k, _num_docs)

    results = _collection.query(query_embeddings=query_embedding, n_results=n_results)

    ids = results["ids"][0]
    distances = results["distances"][0]

    # Coleção configurada com hnsw:space="cosine": distance = 1 - cosine_similarity.
    # similarity = 1 - distance, com clamp a [0, 1] (cosine_similarity raramente
    # é negativo entre frases do mesmo domínio, mas protege o caso limite).
    similarities = [max(0.0, min(1.0, 1.0 - d)) for d in distances]

    return list(zip(ids, similarities))


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
