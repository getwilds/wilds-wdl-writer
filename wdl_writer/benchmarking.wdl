version 1.2

workflow benchmark_wdl_generation {
  meta {
    description: "Benchmarks open-source LLMs on WDL generation across prompt tiers, scored by sprocket check"
    author: "Fred Hutch WILDS Team"
    email: "wilds@fredhutch.org"
    url: "https://github.com/getwilds/wdl-writer"
    outputs: {
      per_run_results: "One JSON file per (model, tier) pair with full per-run results",
      combined_summary: "Single JSON merging all (model, tier) records for cross-model comparison",
      summary_md: "Human-readable markdown summary (model x tier grid and per-case breakdown)"
    }
  }

  parameter_meta {
    models: "List of Ollama model tags to benchmark (e.g., ['llama3.1:8b', 'gemma3:12b'])"
    git_ref: "wilds-wdl-writer git ref to clone (commit SHA, tag, or branch). Pin to a commit for reproducibility."
    n_runs: "Number of generations per test case per tier"
    tiers: "Prompt tiers to evaluate (raw, spec, spec_plus_example, spec_plus_wilds, full)"
  }

  input {
    Array[String] models
    String git_ref = "main"
    Int n_runs = 5
    Array[String] tiers = ["raw", "spec", "spec_plus_example", "spec_plus_wilds", "full"]
  }

  scatter (model in models) {
    scatter (tier in tiers) {
      call run_benchmark {
        input:
          model = model,
          tier = tier,
          git_ref = git_ref,
          n_runs = n_runs,
      }
    }
  }

  call merge_results {
    input:
      per_run_json = flatten(run_benchmark.results_json),
      git_ref = git_ref,
  }

  output {
    Array[File] per_run_results = flatten(run_benchmark.results_json)
    File combined_summary = merge_results.summary_json
    File summary_md = merge_results.summary_md
  }
}

task run_benchmark {
  meta {
    description: "Runs the benchmark suite for one (model, tier) pair against a local Ollama server"
    author: "Fred Hutch WILDS Team"
    email: "wilds@fredhutch.org"
    url: "https://github.com/getwilds/wdl-writer"
    outputs: {
      results_json: "Per-run pass/fail results for all test cases under this (model, tier)",
      server_log: "Ollama server stdout/stderr for debugging"
    }
  }

  parameter_meta {
    model: "Ollama model tag to pull and benchmark"
    tier: "Prompt tier to evaluate (e.g., 'full', 'full_plus_rag')"
    git_ref: "wilds-wdl-writer git ref to clone (commit SHA, tag, or branch)"
    n_runs: "Generations per test case"
    cpu_cores: "Number of CPU cores"
    memory_gb: "Memory in GB"
  }

  input {
    String model
    String tier
    String git_ref
    Int n_runs
    Int cpu_cores = 4
    Int memory_gb = 32
  }

  String safe_name = sub(sub(model, ":", "_"), "/", "_")

  command <<<
    set -eo pipefail

    # Clone the repo so benchmarking.py, prompts/, data/chroma/, and
    # evals/data/ (ground truths) are all available at their natural
    # paths. retrieval.py and benchmarking.py both fall back to the
    # in-repo locations, so no env overrides are needed.
    git clone https://github.com/getwilds/wilds-wdl-writer
    cd wilds-wdl-writer
    git checkout ~{git_ref}
    cd wdl_writer

    # The sentence-transformers model is pre-baked into the image at
    # /opt/hf_cache (world-readable so Apptainer's non-root UID can read it);
    # force offline mode so we don't try to phone home (no per-shard download,
    # no shared scratch filling up across shards).
    export HF_HOME="/opt/hf_cache"
    export HF_HUB_OFFLINE=1
    export TRANSFORMERS_OFFLINE=1

    # Pick a per-shard port so co-located shards don't collide on 11434.
    # Apptainer doesn't isolate the host network namespace, so multiple shards
    # on the same node share localhost.
    OLLAMA_PORT=$(( 20000 + ($$ + RANDOM) % 40000 ))
    export OLLAMA_HOST="http://127.0.0.1:${OLLAMA_PORT}"
    # OLLAMA_MODELS is set by the sprocket config via --env, pointing at a
    # persistent host bind mount so models pulled across runs are cached.

    ollama serve > ollama_server.log 2>&1 &
    SERVER_PID=$!
    trap 'kill -9 $SERVER_PID 2>/dev/null || true' EXIT

    for i in $(seq 1 60); do
      if curl -sf "$OLLAMA_HOST/api/tags" > /dev/null; then
        echo "Ollama server ready after ${i}s"
        break
      fi
      if [ "$i" -eq 60 ]; then
        echo "ERROR: Ollama server did not start in 60s" >&2
        cat ollama_server.log >&2
        exit 1
      fi
      sleep 1
    done

    echo "Pulling ~{model}..."
    ollama pull "~{model}"

    python3 -u benchmarking.py \
      --model "~{model}" \
      --n-runs ~{n_runs} \
      --tiers "~{tier}" \
      --host "$OLLAMA_HOST" \
      --cases benchmarking_cases.json \
      --output "results_~{safe_name}_~{tier}.json"
  >>>

  output {
    File results_json = "wilds-wdl-writer/wdl_writer/results_~{safe_name}_~{tier}.json"
    File server_log = "wilds-wdl-writer/wdl_writer/ollama_server.log"
  }

  runtime {
    docker: "getwilds/ollama:0.21.0"
    gpu: true
    cpu: cpu_cores
    memory: "~{memory_gb} GB"
  }
}

task merge_results {
  meta {
    description: "Combines per-model benchmark JSONs into a single summary for cross-model comparison and renders a markdown table"
    author: "Fred Hutch WILDS Team"
    email: "wilds@fredhutch.org"
    url: "https://github.com/getwilds/wdl-writer"
    outputs: {
      summary_json: "Combined results across all benchmarked models",
      summary_md: "Human-readable markdown summary (model x tier grid and per-case breakdown)"
    }
  }

  parameter_meta {
    per_run_json: "Array of per-(model, tier) result JSON files from run_benchmark"
    git_ref: "wilds-wdl-writer git ref to clone (provides summarize.py)"
    cpu_cores: "Number of CPU cores"
    memory_gb: "Memory in GB"
  }

  input {
    Array[File] per_run_json
    String git_ref
    Int cpu_cores = 1
    Int memory_gb = 2
  }

  command <<<
    set -eo pipefail
    git clone https://github.com/getwilds/wilds-wdl-writer
    cd wilds-wdl-writer
    git checkout ~{git_ref}
    cd wdl_writer
    python3 summarize.py ~{sep=" " per_run_json}
  >>>

  output {
    File summary_json = "wilds-wdl-writer/wdl_writer/combined_summary.json"
    File summary_md = "wilds-wdl-writer/wdl_writer/combined_summary.md"
  }

  runtime {
    docker: "getwilds/ollama:0.21.0"
    cpu: cpu_cores
    memory: "~{memory_gb} GB"
  }
}
