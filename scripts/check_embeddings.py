# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "voyageai",
#     "numpy",
#     "python-dotenv",
# ]
# ///
"""Embedding provider smoke test (Voyage AI), using the settings the pipeline will use.

Checks, in order:
  1. config    : EMBEDDING_MODEL, EMBEDDING_DIM and VOYAGE_API_KEY are set
  2. embed     : documents (input_type="document") and a query (input_type="query") embed
  3. dimension : vectors have EMBEDDING_DIM dimensions, the pgvector column size (vector(N))
  4. ranking   : the query's nearest document is the right one

Exits non-zero on the first failure. Run from anywhere:
  uv run --script scripts/check_embeddings.py
"""

import os
import sys
import time
from pathlib import Path

import numpy as np
import voyageai
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    "Specialist visits cost a $40 copay per visit after the deductible is met.",
    "Emergency room visits cost a $250 copay, waived if you are admitted.",
    "Generic drugs cost $10 for a 30-day supply at in-network pharmacies.",
]
QUERY = "How much do I pay to see a specialist?"  # nearest must be DOCS[0]


def fail(step: str, err: object) -> None:
    print(f"FAIL [{step}] {err}")
    sys.exit(1)


def main() -> None:
    load_dotenv(ROOT / ".env")
    model = os.environ.get("EMBEDDING_MODEL")
    dim = os.environ.get("EMBEDDING_DIM")
    if not (model and dim and os.environ.get("VOYAGE_API_KEY")):
        fail("config", f"set EMBEDDING_MODEL, EMBEDDING_DIM and VOYAGE_API_KEY in {ROOT / '.env'}")
    dim_n = int(dim)
    print(f"PASS [config]    model={model} dim={dim_n}")

    vo = voyageai.Client()  # reads VOYAGE_API_KEY
    try:
        start = time.perf_counter()
        docs = vo.embed(DOCS, model=model, input_type="document", output_dimension=dim_n)
        query = vo.embed([QUERY], model=model, input_type="query", output_dimension=dim_n)
        ms = (time.perf_counter() - start) * 1000
    except voyageai.error.VoyageError as e:
        fail("embed", f"{type(e).__name__}: {e}")
    tokens = docs.total_tokens + query.total_tokens
    print(f"PASS [embed]     {len(DOCS)} docs + 1 query, {tokens} tokens, {ms:.0f} ms")

    d = np.array(docs.embeddings)
    q = np.array(query.embeddings[0])
    if d.shape[1] != dim_n:
        fail("dimension", f"got {d.shape[1]}, expected {dim_n}: the vector(N) column must match")
    print(f"PASS [dimension] {d.shape[1]} (pgvector column: vector({dim_n}))")

    sims = d @ q  # Voyage vectors are unit length, so dot product = cosine similarity
    best = int(np.argmax(sims))
    if best != 0:
        fail("ranking", f"nearest was {DOCS[best]!r}, expected {DOCS[0]!r}")
    print(f"PASS [ranking]   nearest doc scored {sims[0]:.3f} (next best {sorted(sims)[-2]:.3f})")
    print(f"OK: {model} embeddings ready")


if __name__ == "__main__":
    main()
