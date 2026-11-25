#!/usr/bin/env bash
# RGC analysis in three steps:
#   1. automated counting (headless Fiji)             <- this script
#   2. manual review of every field in Fiji           <- Plugins > RGC > Review Counts Full
#   3. summary: review status always; density analysis
#      for a project only once all its fields are reviewed   <- this script, again
#
# Usage (Git Bash, from anywhere):
#   scripts/run_analysis.sh                  # count new images, then report review status / analysis
#   OVERWRITE=true scripts/run_analysis.sh   # recount everything (keeps manual reviews; re-review if outlines change)
#   PRELIMINARY=true scripts/run_analysis.sh # also analyse unreviewed projects from automated counts (marked PRELIMINARY)
#   DATA_DIR=/d/new_batch OUT_DIR=results/batch2 scripts/run_analysis.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
OUT_DIR="${OUT_DIR:-$ROOT/results/simple_rgc}"
mkdir -p "$OUT_DIR/logs"

# Tuned for 20x/0.4 widefield, 0.227 um/px (somata ~40-90 px). Simple RGC defaults are
# radius 20 / sigma 3, which over-detect background texture at this resolution
# (see results/parameter_tuning/).
RADIUS="${RADIUS:-60}"          # Niblack local threshold radius (px)
SIGMA="${SIGMA:-8.0}"           # Gaussian blur sigma
MIN_D="${MIN_D:-35.0}"          # min soma diameter (px)  ~ 8 um
MAX_D="${MAX_D:-130.0}"         # max soma diameter (px)  ~ 30 um
MIN_CONTRAST="${MIN_CONTRAST:-1.15}"  # soma mean / rolling-ball background
BG_RADIUS="${BG_RADIUS:-100}"   # rolling-ball radius (px)
CHANNEL="${CHANNEL:-1}"
AXONS="${AXONS:-false}"
OVERWRITE="${OVERWRITE:-false}"
PRELIMINARY="${PRELIMINARY:-false}"

w() { cygpath -m "$1"; }
echo "[1/2] automated counting: $DATA_DIR -> $OUT_DIR"
"$ROOT/scripts/fiji_headless.sh" "$(w "$ROOT/scripts/simple_rgc_count.groovy")" \
  "inputDir='$(w "$DATA_DIR")',outputDir='$(w "$OUT_DIR")',channel=$CHANNEL,localThresholdRadius=$RADIUS,gaussianSigma=$SIGMA,minDiameterPx=$MIN_D,maxDiameterPx=$MAX_D,minContrast=$MIN_CONTRAST,bgRadiusPx=$BG_RADIUS,removeAxons=$AXONS,overwrite=$OVERWRITE,onlyFiles=''" \
  > "$OUT_DIR/logs/fiji_stdout.txt" 2>&1 || { echo "Fiji failed; see $OUT_DIR/logs/"; exit 1; }
grep -E "ERROR" "$OUT_DIR/logs/count_log.txt" && echo "(some files failed - see count_log.txt)" || true

echo "[2/2] review status and analysis"
EXTRA=()
[ "$PRELIMINARY" = "true" ] && EXTRA+=(--preliminary)
python "$ROOT/scripts/summarize_counts.py" "$OUT_DIR" "${EXTRA[@]}"

cat <<EOF

Next: review the automated counts in Fiji (Plugins > RGC > Review Counts Full),
choosing the results folder $(w "$OUT_DIR").
Then run this script again; a project's density analysis appears once all its fields are reviewed.
EOF
