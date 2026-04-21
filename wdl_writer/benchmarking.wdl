version 1.0

workflow benchmark_wdl_generation {
  meta {
    description: "Benchmarks open-source LLMs on WDL generation across prompt tiers, scored by sprocket check"
    author: "Fred Hutch WILDS Team"
    email: "wilds@fredhutch.org"
    url: "https://github.com/getwilds/wdl-writer"
    outputs: {
      per_model_results: "One JSON file per model with full per-run results",
      combined_summary: "Single JSON merging all models for cross-model comparison"
    }
  }

  parameter_meta {
    models: "List of Ollama model tags to benchmark (e.g., ['llama3.1:8b', 'gemma3:12b'])"
    benchmark_script: "Python benchmarking script to execute inside each task"
    n_runs: "Number of generations per test case per tier"
    tiers: "Prompt tiers to evaluate (raw, spec, example)"
  }

  input {
    Array[String] models
    File benchmark_script
    Int n_runs = 5
    Array[String] tiers = ["raw", "spec", "example"]
  }

  scatter (model in models) {
    call run_benchmark {
      input:
        model = model,
        benchmark_script = benchmark_script,
        n_runs = n_runs,
        tiers = tiers,
    }
  }

  call merge_results {
    input:
      per_model_json = run_benchmark.results_json,
  }

  output {
    Array[File] per_model_results = run_benchmark.results_json
    File combined_summary = merge_results.summary_json
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
    benchmark_script: "Python benchmarking script"
    n_runs: "Generations per tier per test case"
    tiers: "Prompt tiers to evaluate"
    cpu_cores: "Number of CPU cores"
    memory_gb: "Memory in GB"
  }

  input {
    String model
    File benchmark_script
    Int n_runs
    Array[String] tiers
    Int cpu_cores = 4
    Int memory_gb = 32
  }

  String safe_name = sub(sub(model, ":", "_"), "/", "_")

  command <<<
    set -eo pipefail

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

    python3 -u ~{benchmark_script} \
      --model "~{model}" \
      --n-runs ~{n_runs} \
      --tiers ~{sep=" " tiers} \
      --host "$OLLAMA_HOST" \
      --output "results_~{safe_name}.json"
  >>>

  output {
    File results_json = "results_~{safe_name}.json"
    File server_log = "ollama_server.log"
  }

  runtime {
    docker: "getwilds/ollama:0.5.4"
    cpu: cpu_cores
    memory: "~{memory_gb} GB"
    gpus: "1"
  }
}

task merge_results {
  meta {
    description: "Combines per-model benchmark JSONs into a single summary for cross-model comparison"
    author: "Fred Hutch WILDS Team"
    email: "wilds@fredhutch.org"
    url: "https://github.com/getwilds/wdl-writer"
    outputs: {
      summary_json: "Combined results across all benchmarked models"
    }
  }

  parameter_meta {
    per_model_json: "Array of per-model result JSON files from run_benchmark"
    cpu_cores: "Number of CPU cores"
    memory_gb: "Memory in GB"
  }

  input {
    Array[File] per_model_json
    Int cpu_cores = 1
    Int memory_gb = 2
  }

  command <<<
    set -eo pipefail
    python3 <<'PY'
    import json
    paths = "~{sep=' ' per_model_json}".split()
    combined = []
    for p in paths:
        with open(p) as f:
            combined.extend(json.load(f))
    with open("combined_summary.json", "w") as f:
        json.dump(combined, f, indent=2)
    print(f"Merged {len(paths)} model result files -> {len(combined)} tier records")
    PY
  >>>

  output {
    File summary_json = "combined_summary.json"
  }

  runtime {
    docker: "getwilds/ollama:0.5.4"
    cpu: cpu_cores
    memory: "~{memory_gb} GB"
  }
}
