
# Pull Apptainer .sif file (skip if already done)
apptainer pull docker://getwilds/ollama:0.21.0

# Command for an interactive session on a Chorus GPU node (48GB of VRAM)
srun --pty -c 4 --mem=64G -J $USER -t "1-0" --gpus=1 -p chorus /bin/bash -i

# Launch the Ollama container
mkdir -p /tmp/loc/scratch/$SLURM_JOB_ID
apptainer shell \
      --nv \
      --bind /tmp/loc:/loc \
      --bind "$HOME:$HOME" \
      ~/ollama_0.21.0.sif

# Start the Ollama server and pull Gemma 4
export OLLAMA_GPU_OVERHEAD=0
export CUDA_VISIBLE_DEVICES=0
export OLLAMA_MODELS="$HOME/.ollama/models"
mkdir -p "$OLLAMA_MODELS"
ollama serve > ~/ollama.log 2>&1 &
ollama pull gemma4:31b

# Create a 64K-context variant so Ollama doesn't use a tiny default context window
# (Gemma 4 31B weights ~28GB + ~4-8GB for 64K KV cache — well within 48GB VRAM)
cat > /tmp/Modelfile.gemma4-64k <<'EOF'
FROM gemma4:31b
PARAMETER num_ctx 65536
EOF
ollama create gemma4-64k -f /tmp/Modelfile.gemma4-64k

# Clone the repo on rhino before this step if you haven't already:
#   git clone https://github.com/getwilds/wilds-wdl-writer ~/wilds-wdl-writer
REPO_DIR="$HOME/wilds-wdl-writer"

# Set env vars so generate_wdl.py picks up the local Ollama server and model,
# then run it interactively
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="gemma4-64k"
cd "$REPO_DIR/wdl_writer"
python generate_wdl.py
