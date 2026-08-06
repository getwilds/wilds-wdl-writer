"""Core WDL generation: LLM call, output extraction, validation, and retry loop.

Shared by the generation pipeline (generate_wdl.py) and the benchmarking
harness (benchmarking.py). Neither entrypoint should duplicate this logic.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile

from ollama import Client

from prompts import build_retry


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
    """Single chat completion with streaming dot progress. Returns the assistant message content."""
    chunks = []
    for i, chunk in enumerate(client.chat(
        model=model,
        messages=messages,
        stream=True,
        options={"num_ctx": 16000},
    )):
        token = chunk["message"]["content"]
        chunks.append(token)
        if i % 10 == 0:
            print(".", end="", flush=True)
    print()
    return "".join(chunks)


def generate_with_retry(
    client: Client,
    model: str,
    messages: list[dict],
    max_retries: int,
) -> dict:
    """Generate WDL, retrying on validation failure with the error fed back.

    `messages` is the initial [system, user] list; the caller is responsible
    for building it (benchmarking uses initial_messages(); the generation
    pipeline assembles it directly from prompts.build_system/build_user).

    Returns a dict with the final outcome plus per-attempt history.
    """
    attempts = []

    for attempt_idx in range(max_retries + 1):
        print(f"Attempt {attempt_idx + 1} of {max_retries + 1}: generating", end="", flush=True)
        raw = chat_call(client, model, messages)
        print("Validating...", end=" ", flush=True)
        wdl = extract_wdl(raw)
        check = validate_wdl(wdl)
        print("passed." if check["valid"] else f"failed.\n{check['stderr']}")
        attempts.append({
            "attempt": attempt_idx,
            "valid": check["valid"],
            "stderr": check["stderr"],
            "raw_response": raw,
            "extracted_wdl": wdl,
        })
        if check["valid"] or attempt_idx == max_retries:
            break
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
