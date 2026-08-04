#!/usr/bin/env python3
"""Generation pipeline: interactive CLI -> RAG -> LLM -> WDL output."""

from __future__ import annotations

import os
from ollama import Client

from user_interface import prompt_user_for_keywords, filter_keywords_for_tasks, human_tool_approval
from retrieval import retrieve_tasks
from prompts import build_system, build_user
from generation import generate_with_retry

_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
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

    # Build prompt
    system_prompt = build_system(
        include_spec=True,
        include_example=True,
        include_wilds=True,
        retrieved_examples=retrieved_examples,
    )
    template_vars = {
        "tasks": ", ".join(human_approved_ids),
        "input_data_type": ", ".join(keyword_dict["bio_topic"]),
        "format": ", ".join(keyword_dict["format"]),
        "species": ", ".join(keyword_dict["species"]),
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_user(template_vars)},
    ]

    # Generate
    print("\nGenerating WDL workflow (this may take a while)...")
    client = Client(host=_HOST)
    result = generate_with_retry(client, _MODEL, messages, _MAX_RETRIES)

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
