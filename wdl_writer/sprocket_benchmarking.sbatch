#!/bin/bash
#SBATCH --job-name=sprocket_benchmarking
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=24:00:00
#SBATCH --mail-user=tfirman@fredhutch.org # Update with your email address
#SBATCH --mail-type=END
#SBATCH --output=logs/sprocket_benchmarking_%j.out # %j is replaced with job ID
#SBATCH --error=logs/sprocket_benchmarking_%j.err # %j is replaced with job ID

# Configuration (update these for your environment)
WDL_SCRIPT="/home/tfirman/benchmarking.wdl"                               # Branch to pull WDL from
WORK_DIR="/hpc/temp/_DaSL/user/tfirman"                            # Working directory on /hpc/temp/
INPUTS_JSON="/home/tfirman/benchmarking.inputs.json"            # Path to inputs JSON
SPROCKET_CONFIG="/fh/fast/_DaSL/public/minimal-sprocket-config.toml" # Sprocket config file

# Load necessary modules
module purge
module load sprocket/0.23.0 Apptainer/1.1.6

# Defining Apptainer cache and tmp directories
export APPTAINER_CACHEDIR="/hpc/temp/_DaSL/user/tfirman/.apptainer_cache"
export APPTAINER_TMPDIR="/hpc/temp/_DaSL/user/tfirman/.apptainer_tmp"
mkdir -p $APPTAINER_CACHEDIR $APPTAINER_TMPDIR

# Navigate to working directory
cd "${WORK_DIR}"

# Run Sprocket
sprocket run -c "${SPROCKET_CONFIG}" "${WDL_SCRIPT}" "${INPUTS_JSON}"

# Output file paths will be printed to the log file (logs/sprocket_benchmarking_<jobid>.out)
# Make sure to copy the final output files from /hpc/temp/ to a permanent location before they are deleted