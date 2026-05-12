version 1.0

workflow benchmark_wdl_generation {
  meta {
    description: "Benchmarks open-source LLMs on WDL generation across prompt tiers, scored by sprocket check"
    author: "Fred Hutch WILDS Team"
    email: "wilds@fredhutch.org"
    url: "https://github.com/getwilds/wdl-writer"
    outputs: {
      per_model_results: "One JSON file per model with full per-run results",
      combined_summary: "Single JSON merging all models for cross-model comparison",
      summary_md: "Human-readable markdown summary (model x tier grid and per-case breakdown)"
    }
  }

  parameter_meta {
    models: "List of Ollama model tags to benchmark (e.g., ['llama3.1:8b', 'gemma3:12b'])"
    bundle: "Tarball (tar.gz) of the wdl_writer package (benchmarking.py, prompts.py, prompts/, benchmarking_cases.json, summarize.py)"
    n_runs: "Number of generations per test case per tier"
    tiers: "Prompt tiers to evaluate (raw, spec, spec_plus_example, spec_plus_wilds, full)"
  }

  input {
    Array[String] models
    File bundle
    Int n_runs = 5
    Array[String] tiers = ["raw", "spec", "spec_plus_example", "spec_plus_wilds", "full"]
  }

  scatter (model in models) {
    call run_benchmark {
      input:
        model = model,
        bundle = bundle,
        n_runs = n_runs,
        tiers = tiers,
    }
  }

  call merge_results {
    input:
      per_model_json = run_benchmark.results_json,
      bundle = bundle,
  }

  output {
    Array[File] per_model_results = run_benchmark.results_json
    File combined_summary = merge_results.summary_json
    File summary_md = merge_results.summary_md
  }
}

task run_benchmark {
  meta {
    description: "Runs the full benchmark suite for one model against a local Ollama server"
    author: "Fred Hutch WILDS Team"
    email: "wilds@fredhutch.org"
    url: "https://github.com/getwilds/wdl-writer"
    outputs: {
      results_json: "Per-run pass/fail results for all tiers and test cases",
      server_log: "Ollama server stdout/stderr for debugging"
    }
  }

  parameter_meta {
    model: "Ollama model tag to pull and benchmark"
    bundle: "Tarball (tar.gz) of the wdl_writer package (benchmarking.py, prompts.py, prompts/, benchmarking_cases.json, summarize.py)"
    n_runs: "Generations per tier per test case"
    tiers: "Prompt tiers to evaluate"
    cpu_cores: "Number of CPU cores"
    memory_gb: "Memory in GB"
  }

  input {
    String model
    File bundle
    Int n_runs
    Array[String] tiers
    Int cpu_cores = 4
    Int memory_gb = 32
  }

  String safe_name = sub(sub(model, ":", "_"), "/", "_")

  command <<<
    set -eo pipefail

    # Unpack the bundle in place. The tarball must contain benchmarking.py,
    # prompts.py, prompts/, and benchmarking_cases.json at the top level
    # so `from prompts import ...` resolves correctly.
    # TODO: Once wilds-wdl-writer is public, replace this with a git clone
    # and drop the `bundle` input (see build_bundle.sh).
    tar -xzf ~{bundle}

    export OLLAMA_HOST="http://127.0.0.1:11434"
    export OLLAMA_MODELS="$PWD/ollama_models"
    mkdir -p "$OLLAMA_MODELS"

    ollama serve > ollama_server.log 2>&1 &
    SERVER_PID=$!
    trap 'kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null' EXIT

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
      --tiers ~{sep=" " tiers} \
      --host "$OLLAMA_HOST" \
      --cases benchmarking_cases.json \
      --output "results_~{safe_name}.json"
  >>>

  output {
    File results_json = "results_~{safe_name}.json"
    File server_log = "ollama_server.log"
  }

  runtime {
    docker: "getwilds/ollama:0.21.0"
    cpu: cpu_cores
    memory: "~{memory_gb} GB"
    gpus: "1"
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
    per_model_json: "Array of per-model result JSON files from run_benchmark"
    bundle: "Tarball (tar.gz) of the wdl_writer package (provides summarize.py)"
    cpu_cores: "Number of CPU cores"
    memory_gb: "Memory in GB"
  }

  input {
    Array[File] per_model_json
    File bundle
    Int cpu_cores = 1
    Int memory_gb = 2
  }

  command <<<
    set -eo pipefail
    tar -xzf ~{bundle}
    python3 summarize.py ~{sep=" " per_model_json}
  >>>

  output {
    File summary_json = "combined_summary.json"
    File summary_md = "combined_summary.md"
  }

  runtime {
    docker: "getwilds/ollama:0.21.0"
    cpu: cpu_cores
    memory: "~{memory_gb} GB"
  }
}
