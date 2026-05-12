#!/bin/bash
# Build bundle.zip for the benchmarking WDL.
# Contains everything benchmarking.py needs to run inside a WDL task:
# the script itself, the prompts module, the prompts/ directory, and
# the test cases JSON.
#
# NOTE: This bundling step is a stopgap while the wilds-wdl-writer repo is
# private. Once the repo is public, both benchmarking.wdl and benchmarking.sbatch
# can clone it directly (e.g. `git clone https://github.com/getwilds/wilds-wdl-writer`)
# instead of taking a bundle input, and this script + the `bundle` WDL input
# can be removed.

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OUT="bundle.zip"
rm -f "$OUT"

zip -r "$OUT" \
  benchmarking.py \
  prompts.py \
  prompts/ \
  benchmarking_cases.json \
  summarize.py \
  -x '*/__pycache__/*' '*.pyc'

echo "Built $SCRIPT_DIR/$OUT"
unzip -l "$OUT"
