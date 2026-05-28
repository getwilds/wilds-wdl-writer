#!/bin/bash
#SBATCH --job-name=wdl-bench
#SBATCH --output=benchmarking_%j.out
#SBATCH --error=benchmarking_%j.err
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=4:00:00

# ---------------------------------------------------------------------------
# WDL Generation Benchmark — SLURM job script
#
# Starts a local Ollama server via Apptainer, pulls the model, and runs
# the benchmark script against it. All on the same compute node (no network
# latency for inference).
#
# Prerequisites (one-time setup on login node):
#   apptainer pull ollama_0.21.0.sif docker://getwilds/ollama:0.21.0
#
# Usage:
#   sbatch benchmarking.sbatch                         # defaults
#   sbatch --export=MODEL=gemma3:12b benchmarking.sbatch  # override model
#   sbatch --export=GIT_REF=<sha> benchmarking.sbatch     # pin to a commit
# ---------------------------------------------------------------------------

# Loading necessary modules. We run benchmarking.py inside the Apptainer
# container too (see below), so no host-side Python, venv, or sprocket
# module is required — the image carries all of those plus the functional-eval
# Python deps (rapidfuzz, llama-index embeddings, sentence-transformers, torch).
module load Apptainer/1.1.6

# Configurable via --export or edit here
MODEL="${MODEL:-llama3.1:8b}"
N_RUNS="${N_RUNS:-5}"
TIERS="${TIERS:-raw spec spec_plus_example spec_plus_wilds full}"
SIF="${SIF:-ollama_0.21.0.sif}"
GIT_REF="${GIT_REF:-main}"

# Resolve SIF to an absolute path so later `cd "$RUN_DIR"` doesn't break
# the apptainer invocations (callers may pass a bare filename relative to
# the submit dir).
SIF="$(readlink -f "$SIF")"
if [ ! -f "$SIF" ]; then
    echo "ERROR: SIF image not found: $SIF" >&2
    exit 1
fi

# Store models on scratch to avoid filling home directory
export OLLAMA_MODELS="$HOME/ollama_models"
mkdir -p "$OLLAMA_MODELS"

OLLAMA_HOST="http://localhost:11434"

# Clone the repo into a per-job working dir so concurrent jobs don't collide
RUN_DIR="$TMPDIR/wdl_writer_run_${SLURM_JOB_ID:-$$}"
mkdir -p "$RUN_DIR"
git clone https://github.com/getwilds/wilds-wdl-writer "$RUN_DIR/wilds-wdl-writer"
git -C "$RUN_DIR/wilds-wdl-writer" checkout "$GIT_REF"
WORK_DIR="$RUN_DIR/wilds-wdl-writer/wdl_writer"

echo "============================================"
echo "WDL Generation Benchmark"
echo "============================================"
echo "Model:    $MODEL"
echo "N_RUNS:   $N_RUNS"
echo "Tiers:    $TIERS"
echo "SIF:      $SIF"
echo "Git ref:  $GIT_REF"
echo "Work dir: $WORK_DIR"
echo "Node:     $(hostname)"
echo "GPU:      $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
echo "============================================"

# --- Start Ollama server in the background ---
echo "Starting Ollama server..."
apptainer exec --nv \
    --bind "$OLLAMA_MODELS:/root/.ollama/models" \
    --bind "$TMPDIR:$TMPDIR" \
    "$SIF" ollama serve &
OLLAMA_PID=$!

# Wait for server to be ready
echo "Waiting for Ollama server to start..."
for i in $(seq 1 30); do
    if curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        echo "Ollama server is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Ollama server failed to start after 30 seconds."
        kill $OLLAMA_PID 2>/dev/null
        exit 1
    fi
    sleep 1
done

# --- Pull the model ---
echo "Pulling model: $MODEL"
apptainer exec --nv \
    --bind "$OLLAMA_MODELS:/root/.ollama/models" \
    --bind "$TMPDIR:$TMPDIR" \
    "$SIF" ollama pull "$MODEL"

# --- Run the benchmark ---
echo "Running benchmark..."
cd "$WORK_DIR"
apptainer exec --nv \
    --bind "$OLLAMA_MODELS:/root/.ollama/models" \
    --bind "$TMPDIR:$TMPDIR" \
    --bind "$HOME:$HOME" \
    --env "HF_HOME=/opt/hf_cache" \
    --env "HF_HUB_OFFLINE=1" \
    --env "TRANSFORMERS_OFFLINE=1" \
    "$SIF" python3 -u benchmarking.py \
    --model "$MODEL" \
    --n-runs "$N_RUNS" \
    --tiers $TIERS \
    --host "$OLLAMA_HOST" \
    --cases benchmarking_cases.json \
    --output "$HOME/results_${MODEL//[:\/]/_}_${SLURM_JOB_ID}.json"

# --- Cleanup ---
echo "Shutting down Ollama server..."
kill $OLLAMA_PID 2>/dev/null
wait $OLLAMA_PID 2>/dev/null

echo "Done."
