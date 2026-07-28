"""
Mede o RSS do processo por etapa de arranque, para quantificar quanto custa
cada peça do runtime (numpy, sklearn, FastAPI/AutoGen, ChromaDB, torch, modelo
de embeddings) e qual é o PICO durante o primeiro encode.

Existe para a Fase 2.5 (emagrecimento do runtime): o Passo 1 corre-o para obter
a linha de base e o Passo 5 volta a corrê-lo, sem alterações, para medir o
ganho. Ver docs/FASE2.5_DECISOES.txt.

Uso (dentro de um contentor Linux, ver README da fase):

    python scripts/profile_memory.py --label baseline --out docs/bench/rss_baseline.json

Notas de metodologia (o porquê está em docs/FASE2.5_DECISOES.txt):
    - RSS lido de /proc/self/statm, não tracemalloc: o tracemalloc só vê
      alocações do heap do Python e é cego aos pesos do modelo e às arenas de
      alocação das bibliotecas nativas (torch, onnxruntime) - precisamente o
      que esta fase quer medir. É o RSS que o OOM killer vê.
    - Cada etapa corre num SUBPROCESSO novo, importando cumulativamente tudo
      até essa etapa. Medir várias etapas no mesmo processo contaminaria os
      deltas (imports partilhados, alocador que não devolve ao SO).
    - As etapas de encode são amostradas por uma thread a 50 ms para apanhar o
      PICO: uma leitura antes/depois perde-o, e é o pico que causa OOM kill.
    - ru_maxrss (getrusage) é reportado como confirmação independente do pico:
      é o mesmo valor que o `/usr/bin/time -v` mostra em "Maximum resident set
      size", vindo do kernel e não da nossa amostragem.
    - Etapas que não se aplicam ao estado atual do código (ex: chromadb/torch
      depois da Fase 2.5) são reportadas como "skipped", não são erro - é o que
      permite correr O MESMO script antes e depois e comparar.
"""

import argparse
import gc
import json
import os
import platform
import resource
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DESCRIPTIONS_PATH = PROJECT_ROOT / "data" / "portugal_locations_descriptions.json"

# Query da demo da Fase 2 (secção 8 de docs/FASE2_DECISOES.txt) - usar a query
# real e não uma frase qualquer mantém a medição representativa do caso de uso.
DEMO_QUERY = "zona sossegada e autêntica"

JSON_MARKER = "##PROFILE_JSON##"

# Ordem cumulativa: cada etapa corre depois de todas as anteriores, no mesmo
# subprocesso. O delta de uma etapa é o custo marginal dessa peça.
STAGE_ORDER = [
    "baseline",
    "numpy",
    "sklearn",
    "app",
    "chromadb",
    "onnxruntime",
    "torch",
    "model_load",
    "encode_docs",
    "encode_query",
    "steady",
]

# Etapas cujo PICO interessa (amostragem por thread durante a execução).
PEAK_STAGES = {"model_load", "encode_docs", "encode_query"}

_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


class StageSkipped(Exception):
    """A etapa não se aplica ao estado atual do código (ex: chromadb já removido)."""


def rss_bytes() -> int:
    """RSS do processo atual, em bytes. Linux via /proc; fora de Linux tenta psutil."""
    try:
        with open("/proc/self/statm", "r") as f:
            return int(f.read().split()[1]) * _PAGE_SIZE
    except FileNotFoundError:
        import psutil  # só necessário fora de Linux (ex: correr o script em Windows)

        return psutil.Process().memory_info().rss


def max_rss_bytes() -> int:
    """Pico de RSS reportado pelo kernel (o mesmo que `/usr/bin/time -v`)."""
    # ru_maxrss vem em kilobytes no Linux.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


class PeakSampler:
    """Amostra o RSS numa thread para apanhar picos transitórios."""

    def __init__(self, interval: float = 0.05):
        self.interval = interval
        self.peak = 0
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        self.peak = rss_bytes()

        def _run():
            while not self._stop.is_set():
                current = rss_bytes()
                if current > self.peak:
                    self.peak = current
                self._stop.wait(self.interval)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)
        current = rss_bytes()
        if current > self.peak:
            self.peak = current
        return False


# --------------------------------------------------------------------------
# Etapas. Cada uma devolve uma nota (string) ou None; levanta StageSkipped se
# a peça não existir neste estado do código.
# --------------------------------------------------------------------------


def _stage_baseline(ctx):
    return "interpretador + stdlib"


def _stage_numpy(ctx):
    import numpy

    return numpy.__version__


def _stage_sklearn(ctx):
    # Os mesmos imports que tools/knn_ranking.py faz.
    from sklearn.neighbors import NearestNeighbors  # noqa: F401
    from sklearn.preprocessing import MinMaxScaler  # noqa: F401
    import sklearn

    return sklearn.__version__


def _stage_app(ctx):
    # Importa a app inteira (FastAPI + uvicorn + AutoGen + agents + tools).
    # Não arranca o servidor nem o lifespan: mede o custo dos imports.
    import api.main  # noqa: F401

    return "api.main importado"


def _stage_chromadb(ctx):
    try:
        import chromadb
    except ImportError:
        raise StageSkipped("chromadb não instalado")
    return getattr(chromadb, "__version__", "?")


def _stage_onnxruntime(ctx):
    try:
        import onnxruntime
    except ImportError:
        raise StageSkipped("onnxruntime não instalado")
    return onnxruntime.__version__


def _stage_torch(ctx):
    try:
        import torch
    except ImportError:
        raise StageSkipped("torch não instalado")
    return torch.__version__


def _stage_model_load(ctx):
    """
    Carrega o encoder. Tenta primeiro tools.embeddings (a interface da Fase 2.5)
    e só depois o SentenceTransformer direto (estado pré-2.5) - é isto que
    permite ao mesmo script medir os dois estados sem alterações.
    """
    try:
        from tools.embeddings import get_embedder

        embedder = get_embedder()
        if embedder is None:
            raise StageSkipped("tools.embeddings.get_embedder() devolveu None")
        ctx["encode"] = embedder.encode
        return f"tools.embeddings: {getattr(embedder, 'name', '?')}"
    except ImportError:
        pass

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise StageSkipped("nem tools.embeddings nem sentence_transformers disponíveis")

    from tools.semantic_search import MODEL_NAME

    model = SentenceTransformer(MODEL_NAME)
    ctx["encode"] = lambda texts: model.encode(texts, normalize_embeddings=True)
    return f"sentence-transformers: {MODEL_NAME}"


def _stage_encode_docs(ctx):
    if "encode" not in ctx:
        raise StageSkipped("encoder não carregado")

    with open(DESCRIPTIONS_PATH, "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    documents = [entry["description"] for entry in descriptions.values()]

    vectors = ctx["encode"](documents)
    return f"{len(documents)} documentos, shape={getattr(vectors, 'shape', '?')}"


def _stage_encode_query(ctx):
    if "encode" not in ctx:
        raise StageSkipped("encoder não carregado")

    vectors = ctx["encode"]([DEMO_QUERY])
    return f"query={DEMO_QUERY!r}, shape={getattr(vectors, 'shape', '?')}"


def _stage_steady(ctx):
    # Estado estacionário: o que um contentor idle mostraria depois de servir um
    # pedido. É esta a métrica do critério de aceitação da fase (< 400 MB).
    gc.collect()
    time.sleep(2)
    return "após gc.collect() + 2 s"


STAGE_FUNCS = {
    "baseline": _stage_baseline,
    "numpy": _stage_numpy,
    "sklearn": _stage_sklearn,
    "app": _stage_app,
    "chromadb": _stage_chromadb,
    "onnxruntime": _stage_onnxruntime,
    "torch": _stage_torch,
    "model_load": _stage_model_load,
    "encode_docs": _stage_encode_docs,
    "encode_query": _stage_encode_query,
    "steady": _stage_steady,
}


# --------------------------------------------------------------------------
# Execução de uma etapa (dentro do subprocesso)
# --------------------------------------------------------------------------


def run_single_stage(target: str) -> dict:
    """Corre todas as etapas até target (inclusive) e mede a última."""
    ctx = {}
    skipped_before = []

    for name in STAGE_ORDER[: STAGE_ORDER.index(target)]:
        try:
            STAGE_FUNCS[name](ctx)
        except StageSkipped as exc:
            skipped_before.append(f"{name}: {exc}")

    started = time.perf_counter()
    status, note, peak = "ok", None, None

    try:
        if target in PEAK_STAGES:
            with PeakSampler() as sampler:
                note = STAGE_FUNCS[target](ctx)
            peak = sampler.peak
        else:
            note = STAGE_FUNCS[target](ctx)
    except StageSkipped as exc:
        status, note = "skipped", str(exc)
    except Exception as exc:  # falha real da etapa - não invalida as outras
        status, note = "error", f"{type(exc).__name__}: {exc}"

    duration = time.perf_counter() - started

    return {
        "stage": target,
        "status": status,
        "note": note,
        "rss_bytes": rss_bytes(),
        "peak_bytes": peak,
        "max_rss_bytes": max_rss_bytes(),
        "duration_s": round(duration, 3),
        "skipped_before": skipped_before,
    }


# --------------------------------------------------------------------------
# Orquestração (processo pai)
# --------------------------------------------------------------------------


def _environment_info() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }


def _installed_versions() -> dict:
    from importlib.metadata import PackageNotFoundError, version

    packages = [
        "numpy",
        "scikit-learn",
        "scipy",
        "fastapi",
        "autogen-agentchat",
        "chromadb",
        "sentence-transformers",
        "torch",
        "onnxruntime",
        "tokenizers",
    ]
    out = {}
    for pkg in packages:
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            out[pkg] = None
    return out


def _mb(value) -> str:
    if value is None:
        return "-"
    return f"{value / (1024 * 1024):.1f}"


def run_all(label: str) -> dict:
    results = []
    previous_rss = None

    for stage in STAGE_ORDER:
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--run-stage", stage],
            capture_output=True,
            text=True,
        )
        payload = None
        for line in proc.stdout.splitlines():
            if line.startswith(JSON_MARKER):
                payload = json.loads(line[len(JSON_MARKER) :])

        if payload is None:
            payload = {
                "stage": stage,
                "status": "error",
                "note": f"subprocesso falhou (rc={proc.returncode}): {proc.stderr.strip()[-500:]}",
                "rss_bytes": None,
                "peak_bytes": None,
                "max_rss_bytes": None,
                "duration_s": None,
                "skipped_before": [],
            }

        if payload["status"] == "ok" and payload["rss_bytes"] is not None:
            payload["delta_bytes"] = None if previous_rss is None else payload["rss_bytes"] - previous_rss
            previous_rss = payload["rss_bytes"]
        else:
            payload["delta_bytes"] = None

        results.append(payload)
        print(
            f"  {stage:<14} {payload['status']:<8} "
            f"rss={_mb(payload['rss_bytes']):>8} MB  "
            f"delta={_mb(payload.get('delta_bytes')):>8} MB  "
            f"pico={_mb(payload.get('peak_bytes')):>8} MB",
            flush=True,
        )

    return {
        "label": label,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "environment": _environment_info(),
        "versions": _installed_versions(),
        "demo_query": DEMO_QUERY,
        "stages": results,
    }


def print_table(report: dict) -> None:
    print()
    print(f"{'etapa':<14} {'estado':<8} {'RSS (MB)':>10} {'delta (MB)':>11} {'pico (MB)':>10} {'maxRSS (MB)':>12} {'t (s)':>7}")
    print("-" * 78)
    for row in report["stages"]:
        print(
            f"{row['stage']:<14} {row['status']:<8} {_mb(row['rss_bytes']):>10} "
            f"{_mb(row.get('delta_bytes')):>11} {_mb(row.get('peak_bytes')):>10} "
            f"{_mb(row.get('max_rss_bytes')):>12} "
            f"{(row['duration_s'] if row['duration_s'] is not None else '-'):>7}"
        )
    print()
    for row in report["stages"]:
        if row["note"]:
            print(f"  {row['stage']}: {row['note']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", default="baseline", help="identificador do perfil (ex: baseline, slim)")
    parser.add_argument("--out", default=None, help="ficheiro JSON de saída")
    parser.add_argument("--run-stage", default=None, help=argparse.SUPPRESS)  # uso interno (subprocesso)
    args = parser.parse_args()

    if args.run_stage:
        print(JSON_MARKER + json.dumps(run_single_stage(args.run_stage)))
        return

    print(f"A medir RSS por etapa (label={args.label}, python={sys.version.split()[0]})\n")
    report = run_all(args.label)
    print_table(report)

    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = PROJECT_ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nRelatório escrito em {out_path}")


if __name__ == "__main__":
    main()
