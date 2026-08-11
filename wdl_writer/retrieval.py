"""RAG retrieval for the WDL generation pipeline.

For a given case (user input), pull relevant WDL task definitions from the
ChromaDB collection populated by ingestion.py. The retrieved tasks are
returned as plain strings (full task WDL text), ready for either
`build_system(retrieved_examples=...)` or `ingestion.parse_tasks_metadata()`
depending on which prompt pipeline the caller uses.

Current strategy: metadata filter on `tool`. For each module the user
requested, retrieve all of that tool's tasks. Vector-search ranking by
analysis goal is a future addition (spec §6 calls for it as a fallback
when metadata filtering returns too few or too many results).
"""

from __future__ import annotations

from pathlib import Path

import chromadb

from user_interface_dicts import operation_topic_dict

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

def retrieve_tasks(tasks_field: str) -> list[str]:
    """Look up all WDL task definitions for the given comma-separated document ids.

    `tasks_field` is the raw string from the test case (e.g., `"ww-bwa, ww-samtools, ww-gatk"`).
    Returns a list of WDL task texts, one per retrieved task, in module-then-task order.
    """
    doc_ids = [m for m in tasks_field.split(",") if m.strip()]
    if not doc_ids:
        return []

    client = chromadb.PersistentClient(path=str(_resolve_chroma_dir()))
    collection = client.get_collection(_COLLECTION_NAME)
    result = collection.get(ids=doc_ids, include=["documents"])
    return result["documents"]


def _build_filter(contains_filters: list[list[dict]]) -> dict:
    """Combine per-keyword filter lists into a single ChromaDB `where` filter."""
    or_filters = []
    for filt in contains_filters:
        if not filt:
            continue
        if len(filt) == 1:
            or_filters.append(filt[0])
        else:
            or_filters.append({'$or': filt})
    and_filters = {'$and': [i for i in or_filters]}
    return and_filters


def keyword_filter_tasks(keyword_dict: dict[str, list[str]]) -> tuple[set[str], set[str], set[str], set[str]]:
    """Filter tasks by keyword, returning (input_ids, tool_ids, op_ids, user_incompatible_tools) sets of task ids.

    The keyword_dict must be a dictionary of lists of terms for each metadata
    field we're filtering on.
    """
    client = chromadb.PersistentClient(path=str(_resolve_chroma_dir()))
    collection = client.get_collection(_COLLECTION_NAME)
    user_incompatible_tools = set()

    # Create "contains" filters from user input terms
    filter_species = [{'species': {'$contains': i}} for i in keyword_dict['species']]
    filter_bio_topic = [{'topic': {'$contains': i}} for i in keyword_dict['bio_topic']]
    filter_op_topic = [{'topic': {'$contains': i}} for i in keyword_dict['op_topic']]
    filter_operation = [{'operation': {'$contains': i}} for i in keyword_dict['operation']]
    filter_format = [{'input_sample_format_types': {'$contains': i}} for i in keyword_dict['format']]
    filter_tool = [{'tool': i} for i in keyword_dict['tool']]

    # Get tasks compatible with user input data.
    # Not all operations are performed on input data (some on intermediate data)
    # so we need a separate, narrow filter to get tasks compatible with the input.
    #
    # Retrieved WDL task metadata must contain at least one term from each:
    # species AND bio_topic AND op_topic AND operation AND format
    input_filt = _build_filter([filter_species, filter_bio_topic,
                                filter_op_topic, filter_operation, filter_format])
    input_meta = collection.get(where=input_filt, include=['metadatas'])

    if not input_meta['ids']:
        # Stop, can't process the input data
        return set(), set(), set(), set()
    input_ids = set(input_meta['ids'])

    # Get tasks compatible with requested tools.
    # Some of these may not use the input data, they use intermediate data, so
    # we won't filter on 'format'
    #
    # Retrieved WDL task metadata must contain at least one term from each:
    # species AND bio_topic AND op_topic AND operation AND tool
    if not filter_tool:
        tool_metadata = []
        tool_ids = set()
    else:
        tool_filt = _build_filter([filter_species, filter_bio_topic,
                                   filter_op_topic, filter_operation, filter_tool])
        tool_meta = collection.get(where=tool_filt, include=['metadatas'])
        tool_metadata = tool_meta['metadatas']
        tool_ids = set(tool_meta['ids'])

        # Note if any user requested were not retrieved
        requested_tools = keyword_dict['tool']
        retrieved_tools = set()
        for meta in tool_metadata:
            for tool in requested_tools:
                if tool in meta['tool']:
                    retrieved_tools.add(tool)
        user_incompatible_tools = set(requested_tools) - retrieved_tools

    # Drop Q4 checkboxes already covered by tasks retrieved so far. Each checkbox
    # is one (operations, topics) pair in operation_topic_dict -- e.g. "Annotate
    # variants" is (['annotation'], ['genomics']). A checkbox only counts as
    # covered if a retrieved task's operation actually matches THAT checkbox's own
    # operations; matching only on topic isn't enough, since unrelated checkboxes
    # can share a topic (e.g. variant calling and variant annotation are both
    # tagged 'genomics', but finding a variant caller doesn't mean annotation is
    # covered too).
    requested_pairs = [pair for pair in operation_topic_dict.values()
                        if set(pair[0]) <= set(keyword_dict['operation'])]

    already_retrieved_ops = set()
    for meta in input_meta['metadatas'] + tool_metadata:
        already_retrieved_ops.update(meta['operation'])

    uncovered_ops = set()
    uncovered_topics = set()
    for pair_ops, pair_topics in requested_pairs:
        if not already_retrieved_ops.intersection(pair_ops):
            uncovered_ops.update(pair_ops)
            uncovered_topics.update(pair_topics)

    uncovered_ops = list(uncovered_ops)
    uncovered_topics = list(uncovered_topics)

    # Get tasks for remaining operations.
    #
    # Retrieved WDL task metadata must contain at least one term from each:
    # species AND bio_topic AND uncovered_topics AND uncovered_ops
    if not uncovered_ops and not uncovered_topics:
        # Our work here is done
        return input_ids, tool_ids, set(), user_incompatible_tools

    filter_uncovered_ops = [{'operation': {'$contains': i}} for i in uncovered_ops]
    filter_uncovered_topics = [{'topic': {'$contains': i}} for i in uncovered_topics]

    op_filt = _build_filter([filter_species, filter_bio_topic,
                             filter_uncovered_topics, filter_uncovered_ops])
    op_meta = collection.get(where=op_filt, include=['metadatas'])
    op_ids = set(op_meta['ids'])

    return input_ids, tool_ids, op_ids, user_incompatible_tools
