#!/bin/bash
# Build bundle.tar.gz for the benchmarking WDL.
# Contains everything benchmarking.py needs to run inside a WDL task:
# the script itself, the prompts module, the prompts/ directory, and
# the test cases JSON.
#
# Tarball (not zip) because the getwilds/ollama image has tar but not unzip.
#
# NOTE: This bundling step is a stopgap while the wilds-wdl-writer repo is
# private. Once the repo is public, both benchmarking.wdl and benchmarking.sbatch
# can clone it directly (e.g. `git clone https://github.com/getwilds/wilds-wdl-writer`)
# instead of taking a bundle input, and this script + the `bundle` WDL input
# can be removed.

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OUT="bundle.tar.gz"
rm -f "$OUT"

tar --exclude='*/__pycache__' --exclude='*.pyc' -czf "$OUT" \
  benchmarking.py \
  prompts.py \
  prompts/ \
  benchmarking_cases.json \
  summarize.py \
  retrieval.py

# Append the chroma db from ../data/chroma/ so it lands at the bundle root as chroma/.
# Use -A (append to archive) with the gzip workflow: tar can't append to .tar.gz directly,
# so we gunzip, append, then re-gzip.
gunzip "$OUT"
tar --exclude='*/__pycache__' -rf "${OUT%.gz}" -C ../data chroma
gzip "${OUT%.gz}"

echo "Built $SCRIPT_DIR/$OUT"
tar -tzf "$OUT" | head -20
echo "..."
tar -tzf "$OUT" | wc -l | xargs -I{} echo "({} total entries)"
