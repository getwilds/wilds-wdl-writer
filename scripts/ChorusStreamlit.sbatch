#!/bin/bash
#SBATCH --job-name=wdl-writer
#SBATCH --partition=chorus
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=%x-%j.log

# ----------------------------------------------------------------------------
# Launch the WILDS WDL Writer Streamlit app on a Chorus GPU node.
#
# Usage (from rhino):
#   sbatch ChorusStreamlit.sbatch
#
# Then `tail -f wdl-writer-<jobid>.log` and watch for the banner. Run the
# printed `ssh -L ...` command on your laptop, then open http://localhost:8501.
#
# Prereqs (do once on rhino, outside this script):
#   - git clone https://github.com/getwilds/wilds-wdl-writer into $HOME
#     (or adjust REPO_DIR below)
#   - The Apptainer image is auto-pulled below if missing, but only if the
#     compute node has outbound internet. Otherwise pull it on rhino first:
#       apptainer pull docker://getwilds/ollama:0.21.0
# ----------------------------------------------------------------------------

# --- User-editable settings -------------------------------------------------
REPO_DIR="$HOME/wilds-wdl-writer"
SIF_PATH="$HOME/ollama_0.21.0.sif"
VENV_DIR="$HOME/wdl-writer-venv"
BASE_MODEL="gemma4:31b"
MODEL="gemma4-64k"
NUM_CTX=65536
PORT=8501
# ----------------------------------------------------------------------------

set -euo pipefail

export APPTAINER_TMPDIR="/tmp/loc/scratch/$SLURM_JOB_ID/apptainer-tmp"
export APPTAINER_CACHEDIR="/tmp/loc/scratch/$SLURM_JOB_ID/apptainer-cache"
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR" "/tmp/loc/scratch/$SLURM_JOB_ID"

if [ ! -f "$SIF_PATH" ]; then
  apptainer pull "$SIF_PATH" docker://getwilds/ollama:0.21.0
fi

export OLLAMA_MODELS="$HOME/.ollama/models"
mkdir -p "$OLLAMA_MODELS"

MODELFILE_PATH="/tmp/loc/scratch/$SLURM_JOB_ID/Modelfile.$MODEL"
cat > "$MODELFILE_PATH" <<MODELFILE
FROM $BASE_MODEL
PARAMETER num_ctx $NUM_CTX
MODELFILE

# Run Ollama inside Apptainer in the background
apptainer exec \
  --nv \
  --bind /tmp/loc:/loc \
  --bind "$HOME:$HOME" \
  "$SIF_PATH" \
  bash -c "
    export OLLAMA_GPU_OVERHEAD=0
    export CUDA_VISIBLE_DEVICES=0
    export OLLAMA_MODELS='$OLLAMA_MODELS'
    ollama serve > '$HOME/ollama-$SLURM_JOB_ID.log' 2>&1 &
    until curl -sf http://localhost:11434/api/tags > /dev/null; do sleep 1; done
    ollama pull '$BASE_MODEL'
    ollama create '$MODEL' -f '$MODELFILE_PATH'
    tail -f '$HOME/ollama-$SLURM_JOB_ID.log'
  " &

# Wait for Ollama to be ready before starting Streamlit
until curl -sf http://localhost:11434/api/tags > /dev/null; do sleep 1; done

# Create venv and install dependencies on first run
module load Python/3.13.1-GCCcore-14.2.0 sprocket/0.16.0
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet streamlit chromadb ollama rapidfuzz
fi

NODE_HOSTNAME="$(hostname -s)"
echo ""
echo "========================================================================"
echo " STEP 1 — On your LAPTOP, open an SSH tunnel:"
echo "   ssh -L $PORT:$NODE_HOSTNAME:$PORT rhino"
echo ""
echo " STEP 2 — Then open this URL in your browser:"
echo "   http://localhost:$PORT"
echo ""
echo " Job will end at the SLURM time limit. To stop early:"
echo "   scancel $SLURM_JOB_ID"
echo "========================================================================"
echo ""

export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="$MODEL"

cd "$REPO_DIR/wdl_writer"
"$VENV_DIR/bin/streamlit" run app.py --server.port "$PORT" --server.address 0.0.0.0
