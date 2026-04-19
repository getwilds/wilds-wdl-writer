#!/usr/bin/env python3
"""WDL Generation Benchmark — CLI version for HPC runs.

Evaluates how well local open-source LLMs (served via Ollama) generate valid
WDL, graded by `sprocket check`. Runs each test prompt across multiple prompt
tiers (raw, spec, example) to measure how much WDL-specific context helps.

Usage:
    python benchmarking.py                          # all defaults
    python benchmarking.py --model gemma3:4b        # specific model
    python benchmarking.py --tiers raw example      # subset of tiers
    python benchmarking.py --n-runs 10              # more runs per case
    python benchmarking.py --host http://host:11434 # remote Ollama server
"""

import argparse
import subprocess
import tempfile
import os
import re
import json
from ollama import Client

# ---------------------------------------------------------------------------
# Prompt tiers
# ---------------------------------------------------------------------------

PROMPT_TIERS = {
    "raw": (
        "You are an expert programmer. "
        "Respond only with valid code inside a ```wdl code block."
    ),
    "spec": """\
You are an expert in WDL (Workflow Description Language) version 1.0.
Respond only with valid WDL code inside a ```wdl code block.

Follow these WDL 1.0 conventions exactly:

DOCUMENT STRUCTURE:
- The FIRST LINE of every WDL file MUST be `version 1.0` — even if the file only contains a single task
- Tasks define units of work; workflows orchestrate tasks

TASK STRUCTURE (every task needs ALL of these blocks):
- `meta` block — uses COLON syntax (key: "value"), NOT equals signs
- `parameter_meta` block — also uses COLON syntax (key: "value"), NOT equals signs
- `input` block with typed parameters; always include `Int cpu_cores` and `Int memory_gb` with defaults
- `command <<<` heredoc block (not command { }), starting with `set -eo pipefail`
- Use `~{variable}` interpolation inside command blocks (not ${variable})
- `output` block with typed outputs
- `runtime` block — also uses COLON syntax (docker: "image:tag", cpu: cpu_cores, memory: "~{memory_gb} GB")

IMPORTANT SYNTAX RULES:
- meta, parameter_meta, and runtime blocks all use COLON separators: `key: value`
- input and output blocks use EQUALS for assignments: `Type name = value`
- Never use `latest` for Docker tags — always pin a specific version

WORKFLOW STRUCTURE:
- Workflows call tasks with `call task_name { input: ... }`
- Use `scatter (item in collection) { ... }` for parallel execution
- Use WDL `struct` to group related inputs (e.g., sample name + files)
- Wire outputs from one task as inputs to the next: `input_name = previous_task.output_name`
- Collect workflow-level outputs in an `output` block

TYPES: String, Int, Float, Boolean, File, Array[T], Map[K,V], Pair[L,R], T? (optional)
""",
    "example": """\
You are an expert in WDL (Workflow Description Language) version 1.0.
Respond only with valid WDL code inside a ```wdl code block.

Follow these WDL 1.0 conventions exactly:

DOCUMENT STRUCTURE:
- The FIRST LINE of every WDL file MUST be `version 1.0` — even if the file only contains a single task
- Tasks define units of work; workflows orchestrate tasks

TASK STRUCTURE (every task needs ALL of these blocks):
- `meta` block — uses COLON syntax (key: "value"), NOT equals signs
- `parameter_meta` block — also uses COLON syntax (key: "value"), NOT equals signs
- `input` block with typed parameters; always include `Int cpu_cores` and `Int memory_gb` with defaults
- `command <<<` heredoc block (not command { }), starting with `set -eo pipefail`
- Use `~{variable}` interpolation inside command blocks (not ${variable})
- `output` block with typed outputs
- `runtime` block — also uses COLON syntax (docker: "image:tag", cpu: cpu_cores, memory: "~{memory_gb} GB")

IMPORTANT SYNTAX RULES:
- meta, parameter_meta, and runtime blocks all use COLON separators: `key: value`
- input and output blocks use EQUALS for assignments: `Type name = value`
- Never use `latest` for Docker tags — always pin a specific version

WORKFLOW STRUCTURE:
- Workflows call tasks with `call task_name { input: ... }`
- Use `scatter (item in collection) { ... }` for parallel execution
- Use WDL `struct` to group related inputs (e.g., sample name + files)
- Wire outputs from one task as inputs to the next: `input_name = previous_task.output_name`
- Collect workflow-level outputs in an `output` block

TYPES: String, Int, Float, Boolean, File, Array[T], Map[K,V], Pair[L,R], T? (optional)

MINIMAL EXAMPLE (a complete, valid WDL file with one task):

version 1.0

task hello {
  meta {
    description: "A simple hello world task"
    author: "Example Author"
    email: "author@example.org"
    url: "https://example.org"
    outputs: {
      greeting: "A text file with a greeting"
    }
  }

  parameter_meta {
    name: "Name to greet"
    cpu_cores: "Number of CPU cores"
    memory_gb: "Memory in GB"
  }

  input {
    String name
    Int cpu_cores = 1
    Int memory_gb = 2
  }

  command <<<
    set -eo pipefail
    echo "Hello, ~{name}!" > greeting.txt
  >>>

  output {
    File greeting = "greeting.txt"
  }

  runtime {
    docker: "ubuntu:22.04"
    cpu: cpu_cores
    memory: "~{memory_gb} GB"
  }
}
""",
}

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

TEST_CASES = [
    {
        "id": "single_task",
        "prompt": (
            "Write a WDL 1.0 task called `index_bam` that takes a BAM file and "
            "runs `samtools index` on it, producing a .bai index file. "
            "The task must include all of these blocks: "
            "meta (with author, email, description, url, and outputs), "
            "parameter_meta (describing every input), "
            "input (with the BAM file, plus Int cpu_cores and Int memory_gb with defaults), "
            "command using heredoc syntax (command <<<) starting with `set -eo pipefail` "
            "and using ~{var} interpolation, "
            "output, and "
            "runtime (with a pinned Docker image tag, cpu, and memory)."
        ),
    },
    {
        "id": "scatter_workflow",
        "prompt": (
            "Write a WDL 1.0 file containing a struct called `SampleFastq` with fields "
            "`String name` and `File fastq`, a task called `run_fastqc` that runs FastQC "
            "on a single FASTQ file (with meta, parameter_meta, input, command <<<, output, "
            "and runtime blocks), and a workflow called `fastqc_pipeline` that takes an "
            "Array[SampleFastq], scatters over the samples to call `run_fastqc` on each, "
            "and collects the HTML report outputs into an Array[File]."
        ),
    },
    {
        "id": "multi_task_pipeline",
        "prompt": (
            "Write a WDL 1.0 file with two tasks and a workflow that wires them together. "
            "Task 1: `align_reads` takes paired-end FASTQ files (File r1, File r2), a "
            "reference genome File, and a sample name String, then runs `bwa mem` to produce "
            "a BAM file. "
            "Task 2: `sort_bam` takes a BAM file and runs `samtools sort` to produce a "
            "sorted BAM. "
            "Both tasks must have meta, parameter_meta, input, command <<<, output, and "
            "runtime blocks with pinned Docker images. "
            "The workflow `align_and_sort` should call align_reads, then pass its BAM output "
            "to sort_bam."
        ),
    },
    {
        "id": "conditional_branching",
        "prompt": (
            "Write a WDL 1.0 file with a task called `align_reads` that takes a File r1, "
            "an optional File? r2, a File reference, a String sample_name, and standard "
            "resource inputs. The command should run `bwa mem` with r1 only if r2 is not "
            "provided, or with both r1 and r2 if r2 is provided. "
            "Then write a workflow called `flexible_align` that takes a File r1, File? r2, "
            "and File reference as inputs. The workflow should use an `if` block: "
            "if r2 is defined, call align_reads with both files; otherwise call align_reads "
            "with only r1. Use `select_first` to pick the output BAM from whichever branch ran."
        ),
    },
]

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


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


def generate(client: Client, model: str, prompt: str, tier: str = "example") -> str:
    """Call the model via Ollama with the specified prompt tier."""
    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": PROMPT_TIERS[tier]},
            {"role": "user", "content": prompt},
        ],
    )
    return response["message"]["content"]


def run_eval(client: Client, model: str, n_runs: int, tiers: list[str]) -> list[dict]:
    """Run the eval across prompt tiers and test cases."""
    all_results = []
    for tier in tiers:
        print(f"\n{'='*60}")
        print(f"TIER: {tier}")
        print(f"{'='*60}")
        tier_results = []
        for case in TEST_CASES:
            print(f"\n  --- {case['id']} ---")
            passes = 0
            runs = []
            for i in range(n_runs):
                raw = generate(client, model, case["prompt"], tier=tier)
                wdl = extract_wdl(raw)
                check = validate_wdl(wdl)
                runs.append({"run": i, "valid": check["valid"], "stderr": check["stderr"]})
                if check["valid"]:
                    passes += 1
                print(f"    run {i+1}: {'PASS' if check['valid'] else 'FAIL'}")
                if not check["valid"]:
                    print(f"      {check['stderr'][:200]}")
            tier_results.append({
                "id": case["id"],
                "pass_rate": passes / n_runs,
                "runs": runs,
            })
            print(f"    -> {passes}/{n_runs} passed")
        all_results.append({
            "model": model,
            "tier": tier,
            "cases": tier_results,
            "avg_pass_rate": sum(r["pass_rate"] for r in tier_results) / len(tier_results),
        })

    return all_results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="WDL Generation Benchmark")
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model name (default: llama3.1:8b)")
    parser.add_argument("--n-runs", type=int, default=5, help="Runs per test case per tier (default: 5)")
    parser.add_argument("--tiers", nargs="+", default=list(PROMPT_TIERS.keys()),
                        choices=list(PROMPT_TIERS.keys()), help="Prompt tiers to evaluate (default: all)")
    parser.add_argument("--host", default="http://localhost:11434", help="Ollama server URL (default: http://localhost:11434)")
    parser.add_argument("--output", default="results.json", help="Output JSON file (default: results.json)")
    args = parser.parse_args()

    print(f"Model:  {args.model}")
    print(f"Tiers:  {', '.join(args.tiers)}")
    print(f"Runs:   {args.n_runs} per case per tier")
    print(f"Host:   {args.host}")
    print(f"Output: {args.output}")

    client = Client(host=args.host)
    results = run_eval(client, args.model, args.n_runs, args.tiers)

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    # Summary table
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'Tier':<12} {'Avg Pass Rate':>14}   Per-case breakdown")
    print(f"{'-'*12} {'-'*14}   {'-'*40}")
    for tr in results:
        case_rates = "  ".join(f"{c['id']}:{c['pass_rate']:.0%}" for c in tr["cases"])
        print(f"{tr['tier']:<12} {tr['avg_pass_rate']:>13.0%}   {case_rates}")


if __name__ == "__main__":
    main()
