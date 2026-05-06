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
#   apptainer pull ollama.sif docker://ollama/ollama
#   pip install ollama  (or into a venv/conda env)
#
# Usage:
#   sbatch benchmarking.sbatch                         # defaults
#   sbatch --export=MODEL=gemma3:12b benchmarking.sbatch  # override model
# ---------------------------------------------------------------------------

# Loading necessary modules
module load Apptainer/1.1.6 Python/3.12.3-GCCcore-13.3.0 sprocket/0.23.0

# If a virtual environment exists, activate it
# If not, create one and install the ollama Python client
VENV_DIR="$HOME/venvs/ollama"
if [ -d "$VENV_DIR" ]; then
    echo "Activating existing virtual environment at $VENV_DIR"
    source "$VENV_DIR/bin/activate"
else
    echo "Creating virtual environment at $VENV_DIR"
    python -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --no-cache-dir ollama
fi

# Configurable via --export or edit here
MODEL="${MODEL:-llama3.1:8b}"
N_RUNS="${N_RUNS:-5}"
TIERS="${TIERS:-raw spec spec_plus_example}"
SIF="${SIF:-ollama.sif}"

# Store models on scratch to avoid filling home directory
export OLLAMA_MODELS="$HOME/ollama_models"
mkdir -p "$OLLAMA_MODELS"

OLLAMA_HOST="http://localhost:11434"
SCRIPT_DIR="$HOME"

echo "============================================"
echo "WDL Generation Benchmark"
echo "============================================"
echo "Model:    $MODEL"
echo "N_RUNS:   $N_RUNS"
echo "Tiers:    $TIERS"
echo "SIF:      $SIF"
echo "Node:     $(hostname)"
echo "GPU:      $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
echo "============================================"

# --- Start Ollama server in the background ---
echo "Starting Ollama server..."
apptainer run --nv \
    --bind "$OLLAMA_MODELS:/root/.ollama/models" \
    --bind "$TMPDIR:$TMPDIR" \
    "$SIF" serve &
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
python -u "$SCRIPT_DIR/benchmarking.py" \
    --model "$MODEL" \
    --n-runs "$N_RUNS" \
    --tiers $TIERS \
    --host "$OLLAMA_HOST" \
    --output "$SCRIPT_DIR/results_${MODEL//[:\/]/_}_${SLURM_JOB_ID}.json"

# --- Cleanup ---
echo "Shutting down Ollama server..."
kill $OLLAMA_PID 2>/dev/null
wait $OLLAMA_PID 2>/dev/null

echo "Done."
