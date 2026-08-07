#!/usr/bin/env python3
"""Generation pipeline: interactive CLI -> RAG -> LLM -> WDL output."""

from __future__ import annotations

import os
from ollama import Client

from user_interface import prompt_user_for_keywords, filter_keywords_for_tasks, human_tool_approval
from retrieval import retrieve_tasks
from ingestion import parse_tasks_metadata, format_tasks_as_yaml
from prompts import build_short_system, build_short_user, build_select_system
from generation import generate_with_retry, select_tasks

_MODEL = os.environ.get("OLLAMA_MODEL", "granite-code:8b")
_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_MAX_RETRIES = int(os.environ.get("WDL_MAX_RETRIES", 5))


def main():
    keyword_dict = prompt_user_for_keywords()

    # RAG step 1: filter tasks by keyword metadata
    print("\nSearching for relevant WDL tasks...")
    final_retrieved_ids = filter_keywords_for_tasks(keyword_dict)

    if not final_retrieved_ids:
        return

    print(f"Found {len(final_retrieved_ids)} relevant task(s).")

    human_approved_ids = human_tool_approval(final_retrieved_ids)

    print(f"Tasks that will be presented to LLM (displaying modulename_taskname) :\n{human_approved_ids}")

    # RAG step 2: fetch documents for the confirmed tasks
    retrieved_examples = retrieve_tasks(",".join(human_approved_ids))

    # Extract relevant metadata from the retrieved tasks for the LLM, keyed by
    # task name so the selection step below can narrow it down
    candidate_tasks = parse_tasks_metadata(retrieved_examples)

    template_vars = {
        "user_input_format": ", ".join(keyword_dict["format"]),
        "user_operations": ", ".join(keyword_dict["operation"]),
    }
    client = Client(host=_HOST)

    # LLM call 1: pick which candidate tasks to chain together. Kept separate
    # from WDL writing so the model isn't juggling task tie-breaking and WDL
    # syntax in the same pass -- the two-view schema plus every alternative
    # task is a lot for a small model to hold onto at once.
    print("\nSelecting tasks for the workflow...")
    select_messages = [
        {"role": "system", "content": build_select_system()},
        {"role": "user", "content": build_short_user(
            {**template_vars, "tasks_yaml": format_tasks_as_yaml(candidate_tasks)}
        )},
    ]
    selected_names = select_tasks(client, _MODEL, select_messages, set(candidate_tasks))
    print(f"Selected tasks: {', '.join(selected_names)}")
    selected_tasks = {name: candidate_tasks[name] for name in selected_names}

    # LLM call 2: write the WDL, now seeing only the tasks already chosen.
    write_messages = [
        {"role": "system", "content": build_short_system()},
        {"role": "user", "content": build_short_user(
            {**template_vars, "tasks_yaml": format_tasks_as_yaml(selected_tasks)}
        )},
    ]

    print("\nGenerating WDL workflow (this may take a while)...")
    result = generate_with_retry(client, _MODEL, write_messages, _MAX_RETRIES)

    # Display result
    print("\n" + "=" * 80)
    if result["valid"]:
        print("Validation passed.")
    else:
        print(f"Validation failed after {result['attempts_used']} attempt(s).")
        print(f"Errors:\n{result['stderr']}")
    if result["attempts_used"] > 1:
        print(f"Generated in {result['attempts_used']} attempt(s).")
    print("=" * 80)
    print("\n```wdl")
    print(result["extracted_wdl"])
    print("```\n")

    print("For help running your WDL, contact OCDO via Data House Calls: "
          "https://ocdo.fredhutch.org/programs/data-house-calls.html")


if __name__ == "__main__":
    main()
