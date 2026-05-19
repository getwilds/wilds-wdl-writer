#!/usr/bin/env python3
"""WDL Generation Benchmark — CLI version for HPC runs.

Evaluates how well local open-source LLMs (served via Ollama) generate valid
WILDS WDL pipelines, graded by `sprocket check`. Each test case is a dropdown-
style input set (pipeline name, modules, analysis goal, etc.) rendered through
`build_user()`; the system prompt is varied across prompt tiers to measure the
contribution of each context layer (WDL spec, minimal example, WILDS conventions).

Usage:
    python benchmarking.py                                      # all defaults
    python benchmarking.py --model gemma3:4b                    # specific model
    python benchmarking.py --tiers spec spec_plus_wilds         # subset of tiers
    python benchmarking.py --n-runs 10              # more runs per case
    python benchmarking.py --host http://host:11434 # remote Ollama server
    python benchmarking.py --cases custom_cases.json # different test set
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
import os
import re
import json
from pathlib import Path
import numpy as np
from ollama import Client
from rapidfuzz.distance import Levenshtein
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from prompts import PROMPT_CONFIGS, build_system, build_user, build_retry
from retrieval import retrieve_tasks

DEFAULT_CASES_PATH = Path(__file__).parent / "benchmarking_cases.json"
GROUND_TRUTH_DIR = Path(__file__).parent.parent / "evals" / "data"

LEXICAL_PASS_THRESHOLD = 0.85
SEMANTIC_PASS_THRESHOLD = 0.90

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def load_ground_truth(filename: str) -> str:
    """Return a reference WDL as a string."""
    full_wdl = Path(GROUND_TRUTH_DIR, filename).read_text()
    return full_wdl


def lexical_similarity(ref: str, to_eval: str) -> float:
    """Measure text similarity"""
    return 1 - Levenshtein.normalized_distance(ref, to_eval)


def semantic_similarity(embed_model: HuggingFaceEmbedding, ref: str, to_eval: str) -> float:
    """Measure 'meaning' similarity by comparing text embeddings."""
    emb_ref = np.array(embed_model.get_text_embedding(ref))
    emb_eval = np.array(embed_model.get_text_embedding(to_eval))
    # Calculate cosine similarity with numpy
    dot_product = np.dot(emb_ref, emb_eval)
    product_of_lengths = np.linalg.norm(emb_ref) * np.linalg.norm(emb_eval)
    return float(dot_product / product_of_lengths)


def check_retrieved_module_usage(case: dict, to_eval: str) -> bool:
    """Confirm that retrieved modules appear in the output WDL imports."""
    expected = {m.strip() for m in case["modules"].split(",")}
    found = set(re.findall(r'ww-[\w-]+(?=/ww-[\w-]+\.wdl)', to_eval))
    return expected == found


def extract_wdl(text: str) -> str:
    """Pull WDL out of a code fence, or return the whole thing if no fence."""
    match = re.search(r"```(?:wdl)?\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def validate_wdl(wdl_text: str) -> dict:
    """Run sprocket check. Returns pass/fail and stderr."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".wdl", delete=False) as f:
        f.write(wdl_text)
        path = f.name
    try:
        result = subprocess.run(
            ["sprocket", "check", path],
            capture_output=True, text=True, timeout=30,
        )
        return {
            "valid": result.returncode == 0,
            "stderr": (result.stderr or result.stdout).strip(),
        }
    except subprocess.TimeoutExpired:
        return {"valid": False, "stderr": "timeout"}
    finally:
        os.unlink(path)


def chat_call(client: Client, model: str, messages: list[dict]) -> str:
    """Single chat completion. Returns the assistant message content."""
    response = client.chat(model=model, messages=messages)
    return response["message"]["content"]


def initial_messages(case: dict, tier: str) -> list[dict]:
    """Build the [system, user] message list for the first attempt."""
    template_vars = {k: v for k, v in case.items() if k != "id"}
    # Split RAG flag out of the config since build_system() doesn't know about it.
    config = {**PROMPT_CONFIGS[tier]}
    use_rag = config.pop("use_rag", False)
    if use_rag:
        config["retrieved_examples"] = retrieve_tasks(case.get("modules", ""))
    return [
        {"role": "system", "content": build_system(**config)},
        {"role": "user", "content": build_user(template_vars)},
    ]


def generate_with_retry(client: Client, model: str, case: dict, tier: str, max_retries: int) -> dict:
    """Generate WDL, retrying on validation failure with the error fed back.

    Returns a dict with the final outcome plus per-attempt history.
    """
    messages = initial_messages(case, tier)
    attempts = []

    for attempt_idx in range(max_retries + 1):
        raw = chat_call(client, model, messages)
        wdl = extract_wdl(raw)
        check = validate_wdl(wdl)
        attempts.append({
            "attempt": attempt_idx,
            "valid": check["valid"],
            "stderr": check["stderr"],
            "raw_response": raw,
            "extracted_wdl": wdl,
        })
        if check["valid"] or attempt_idx == max_retries:
            break
        # Continue the conversation: include the failed WDL and the sprocket error.
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": build_retry(check["stderr"])})

    final = attempts[-1]
    return {
        "valid": final["valid"],
        "stderr": final["stderr"],
        "raw_response": final["raw_response"],
        "extracted_wdl": final["extracted_wdl"],
        "attempts": attempts,
        "first_attempt_valid": attempts[0]["valid"],
        "attempts_used": len(attempts),
    }


def run_eval(client: Client, model: str, n_runs: int, tiers: list[str], cases: list[dict], max_retries: int) -> list[dict]:
    """Run the eval across prompt tiers and test cases."""
    all_results = []
    for tier in tiers:
        print(f"\n{'='*60}")
        print(f"TIER: {tier}")
        print(f"{'='*60}")
        tier_results = []
        for case in cases:
            print(f"\n  --- {case['id']} ---")
            passes = 0
            first_passes = 0
            runs = []
            for i in range(n_runs):
                result = generate_with_retry(client, model, case, tier, max_retries)
                runs.append({"run": i, **result})
                if result["valid"]:
                    passes += 1
                if result["first_attempt_valid"]:
                    first_passes += 1
                status = "PASS" if result["valid"] else "FAIL"
                attempts = result["attempts_used"]
                attempt_note = f" (attempt {attempts})" if attempts > 1 else ""
                print(f"    run {i+1}: {status}{attempt_note}")
                if not result["valid"]:
                    print(f"      {result['stderr'][:200]}")
            tier_results.append({
                "id": case["id"],
                "pass_rate": passes / n_runs,
                "first_attempt_pass_rate": first_passes / n_runs,
                "runs": runs,
            })
            print(f"    -> {passes}/{n_runs} passed (first attempt: {first_passes}/{n_runs})")
        all_results.append({
            "model": model,
            "tier": tier,
            "cases": tier_results,
            "avg_pass_rate": sum(r["pass_rate"] for r in tier_results) / len(tier_results),
            "avg_first_attempt_pass_rate": sum(r["first_attempt_pass_rate"] for r in tier_results) / len(tier_results),
        })

    return all_results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="WDL Generation Benchmark")
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model name (default: llama3.1:8b)")
    parser.add_argument("--n-runs", type=int, default=5, help="Runs per test case per tier (default: 5)")
    parser.add_argument("--tiers", nargs="+", default=list(PROMPT_CONFIGS.keys()),
                        choices=list(PROMPT_CONFIGS.keys()), help="Prompt tiers to evaluate (default: all)")
    parser.add_argument("--host", default="http://localhost:11434", help="Ollama server URL (default: http://localhost:11434)")
    parser.add_argument("--output", default="results.json", help="Output JSON file (default: results.json)")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help=f"Test case JSON file (default: {DEFAULT_CASES_PATH.name})")
    parser.add_argument("--max-retries", type=int, default=3, help="Max validator-feedback retries per run (default: 3, 0 disables)")
    args = parser.parse_args()

    with open(args.cases) as f:
        cases = json.load(f)

    print(f"Model:       {args.model}")
    print(f"Tiers:       {', '.join(args.tiers)}")
    print(f"Runs:        {args.n_runs} per case per tier")
    print(f"Max retries: {args.max_retries}")
    print(f"Host:        {args.host}")
    print(f"Cases:       {args.cases} ({len(cases)} cases)")
    print(f"Output:      {args.output}")

    client = Client(host=args.host)
    results = run_eval(client, args.model, args.n_runs, args.tiers, cases, args.max_retries)

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    # Summary table
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'Tier':<20} {'1st':>5}  {'Final':>5}   Per-case (final)")
    print(f"{'-'*20} {'-'*5}  {'-'*5}   {'-'*40}")
    for tr in results:
        case_rates = "  ".join(f"{c['id']}:{c['pass_rate']:.0%}" for c in tr["cases"])
        print(f"{tr['tier']:<20} {tr['avg_first_attempt_pass_rate']:>4.0%}  {tr['avg_pass_rate']:>4.0%}    {case_rates}")


if __name__ == "__main__":
    main()
