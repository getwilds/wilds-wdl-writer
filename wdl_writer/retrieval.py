"""RAG retrieval for the WDL generation pipeline.

For a given case (user input), pull relevant WDL task definitions from the
ChromaDB collection populated by ingestion.py. The retrieved tasks are
returned as plain strings (full task WDL text) ready to pass into
`build_system(retrieved_examples=...)`.

Current strategy: metadata filter on `tool`. For each module the user
requested, retrieve all of that tool's tasks. Vector-search ranking by
analysis goal is a future addition (spec §6 calls for it as a fallback
when metadata filtering returns too few or too many results).
"""

from __future__ import annotations

from pathlib import Path

import chromadb

_HERE = Path(__file__).parent
# Look for chroma in two places: bundle root (sibling of this file) for
# WDL/HPC runs, then ../data/chroma/ for in-repo development runs.
_CANDIDATE_PATHS = [
    _HERE / "chroma",
    _HERE.parent / "data" / "chroma",
]

_COLLECTION_NAME = "wdl_tasks"


def _resolve_chroma_dir() -> Path:
    for p in _CANDIDATE_PATHS:
        if p.is_dir():
            return p
    raise FileNotFoundError(
        f"Could not find chroma db. Looked in: {[str(p) for p in _CANDIDATE_PATHS]}"
    )


def _strip_prefix(module_name: str) -> str:
    """`ww-bwa` → `bwa`. ChromaDB metadata stores tool names without the prefix."""
    return module_name.strip().removeprefix("ww-")


def retrieve_tasks(modules_field: str) -> list[str]:
    """Look up all WDL task definitions for the given comma-separated modules.

    `modules_field` is the raw string from the test case (e.g., `"ww-bwa, ww-samtools, ww-gatk"`).
    Returns a list of WDL task texts, one per retrieved task, in module-then-task order.
    """
    modules = [_strip_prefix(m) for m in modules_field.split(",") if m.strip()]
    if not modules:
        return []

    client = chromadb.PersistentClient(path=str(_resolve_chroma_dir()))
    collection = client.get_collection(_COLLECTION_NAME)

    documents = []
    for tool in modules:
        result = collection.get(where={"tool": tool}, include=["documents"])
        documents.extend(result["documents"])
    return documents
