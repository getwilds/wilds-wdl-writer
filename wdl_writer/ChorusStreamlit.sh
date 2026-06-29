
# Pull Apptainer .sif file (skip if already done)
apptainer pull docker://getwilds/ollama:0.21.0

# Command for an interactive session on a Chorus GPU node (48GB of VRAM)
srun --pty -c 4 --mem=64G -J $USER -t "1-0" --gpus=1 -p chorus /bin/bash -i

# Launch the Ollama container in the background (--nv for GPU, detached with &)
mkdir -p /tmp/loc/scratch/$SLURM_JOB_ID
apptainer exec \
      --nv \
      --bind /tmp/loc:/loc \
      --bind "$HOME:$HOME" \
      ~/ollama_0.21.0.sif \
      bash -c "
        export OLLAMA_GPU_OVERHEAD=0
        export CUDA_VISIBLE_DEVICES=0
        export OLLAMA_MODELS=$HOME/.ollama/models
        ollama serve > ~/ollama.log 2>&1 &
        # Wait for Ollama to be ready
        until curl -sf http://localhost:11434/api/tags > /dev/null; do sleep 1; done
        ollama pull gemma4:31b
        cat > /tmp/Modelfile.gemma4-64k <<'EOF'
FROM gemma4:31b
PARAMETER num_ctx 65536
EOF
        ollama create gemma4-64k -f /tmp/Modelfile.gemma4-64k
        # Keep the container alive while Streamlit runs on the host
        tail -f ~/ollama.log
      " &

# Wait for Ollama to be ready before starting Streamlit
until curl -sf http://localhost:11434/api/tags > /dev/null; do sleep 1; done

# Set up a venv with Streamlit if not already done
module load Python/3.13.1-GCCcore-14.2.0 sprocket/0.16.0
VENV_DIR="$HOME/wdl-writer-venv"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet streamlit chromadb ollama rapidfuzz
fi

# Point the app at the local Ollama server and model
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="gemma4-64k"

# Streamlit needs to be reachable via SSH tunnel (same pattern as ChorusOpenCode.sh)
# On your LAPTOP, run: ssh -L 8501:<node-hostname>:8501 rhino
# Then open: http://localhost:8501
NODE_HOSTNAME="$(hostname -s)"
echo ""
echo "========================================================================"
echo " On your LAPTOP, open an SSH tunnel:"
echo "   ssh -L 8501:$NODE_HOSTNAME:8501 rhino"
echo ""
echo " Then open this URL in your browser:"
echo "   http://localhost:8501"
echo "========================================================================"
echo ""

REPO_DIR="$HOME/wilds-wdl-writer"
cd "$REPO_DIR/wdl_writer"
"$VENV_DIR/bin/streamlit" run app.py --server.port 8501 --server.address 0.0.0.0
