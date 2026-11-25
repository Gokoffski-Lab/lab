# Behavior video: PDCT (Pole Descent Cliff Task)

**Owner:** Winston · **Projects:** Amblyopia – Rats (PDCT), mTOR/Rheb (VCA, same pipeline) ·
**Code:** [`acquisition/behavior-video/`](https://github.com/Gokoffski-Lab/lab/tree/main/acquisition/behavior-video)

## What it produces
Trial videos with metadata attached at the time they're written (acquisition GUI). The analysis pipeline
then turns them into `y(t)`, the animal's vertical position on the pole over time. Descent time and
height-resolved velocity come from `y(t)`.

## Parts
| Part | Runs on | Notes |
|---|---|---|
| `acquisition/` | Acquisition PC (Windows, i7-7700, no CUDA) | PySide6 GUI, Spinnaker/PySpin, one keypress per trial |
| `analysis/` | Analysis PC (GPU) | DeepLabCut 3.0 (PyTorch). Torch from the cu128 index (see `analysis/CLAUDE.md`) |
| `shared/schema/` | both | Contract: `session_metadata.json`, `trials.csv`, timestamp sidecars |

Detailed design and invariants: `acquisition/CLAUDE.md`, `analysis/CLAUDE.md`,
`acquisition/acquisition/SPINNAKER_PLAN.md`. Open questions from the build: `QUESTIONS.md`.

## Install (per part)
```bash
cd acquisition/behavior-video
pip install -e shared
pip install -r acquisition/requirements.txt   # or analysis/requirements.txt
```
PySpin comes from the Spinnaker SDK download, not PyPI.

## Steps
!!! note "TODO"
    Write the operator steps: session setup screen → start trial (keypress) → exclusion flags (fall / freeze / no descent) → review → where files land on CRSP.