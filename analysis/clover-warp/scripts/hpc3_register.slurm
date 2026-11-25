#!/bin/bash
#SBATCH --job-name=cloverwarp
#SBATCH --account=CHANGEME
#SBATCH --partition=standard
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=logs/cloverwarp_%A_%a.out
#SBATCH --array=0-7
#
# Register one retina per array task on UCI HPC3.
#
# Usage:
#   mkdir -p logs
#   ls config/*.yaml > config/manifest.txt
#   sbatch --array=0-$(( $(wc -l < config/manifest.txt) - 1 )) \
#          scripts/hpc3_register.slurm
#
# This is CPU-only and modest: the heavy step is reading the stitched
# flatmount, not the registration. Do NOT request a GPU -- nothing here uses
# one. A GPU allocation becomes relevant only if learned vessel segmentation
# is ever trained (vessels.segment_learned), which is a separate job.

set -euo pipefail

module purge
module load anaconda/2023.03
source activate cloverwarp

CONFIG=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" config/manifest.txt)
if [[ -z "${CONFIG}" ]]; then
  echo "no config for array index ${SLURM_ARRAY_TASK_ID}" >&2
  exit 1
fi

echo "host:   $(hostname)"
echo "config: ${CONFIG}"

# Keep BLAS single-threaded per task; the parallelism is across array tasks.
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Manual landmarks take precedence when present: they are the reference
# standard, and there is no reason to re-derive a worse answer automatically.
PETAL_ARGS=()
STEM=$(basename "${CONFIG}" .yaml)
shopt -s nullglob
for csv in "landmarks/${STEM}"/*.csv; do
  PETAL_ARGS+=( --landmarks "$(basename "${csv}" .csv)=${csv}" )
done
shopt -u nullglob

if [[ ${#PETAL_ARGS[@]} -gt 0 ]]; then
  echo "using ${#PETAL_ARGS[@]} manual landmark files"
  cloverwarp manual "${CONFIG}" "${PETAL_ARGS[@]}"
else
  echo "no manual landmarks found; running automatic matching"
  cloverwarp auto "${CONFIG}"
fi
