# behavior-video: PDCT acquisition + analysis

> **Status:** ✅ active · **Owner:** @winstonaluk · **Language:** Python ≥3.10 ·
> **Runs on:** acquisition PC (Windows, no CUDA) / analysis PC (GPU) ·
> **Docs:** [Behavior video workflow](https://gokoffski-lab.github.io/lab/workflows/behavior-video-pdct/)

Multi-camera behavior video for the **PDCT (Pole Descent Cliff Task)**, and VCA through the same pipeline.
The acquisition GUI attaches animal/session metadata when each file is written. The analysis pipeline turns
the video into `y(t)`, the rat's height on the pole over time.

## Layout
```
behavior-video/
├── shared/schema/   contract between the two apps (session_metadata.json, trials.csv, timestamps)
├── acquisition/     PySide6 GUI + Spinnaker/PySpin capture   → acquisition/CLAUDE.md
├── analysis/        DeepLabCut 3.0 (PyTorch) pipeline          → analysis/CLAUDE.md
├── QUESTIONS.md     open design questions (referenced by TODO(QUESTIONS.md) tags in code)
└── notes/           record of the initial unattended build (prompt + report)
```
`shared/schema/` here is internal to this subproject. The lab-wide naming helpers are in the repo root's `shared/`.

## Install
```bash
cd acquisition/behavior-video
python -m venv .venv && .venv\Scripts\activate      # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -e shared
pip install -r acquisition/requirements.txt          # acquisition PC
pip install -r analysis/requirements.txt             # analysis PC; torch from the cu128 index, see analysis/CLAUDE.md
```
PySpin comes from the Teledyne Spinnaker SDK download, not PyPI. All tests run without it (mock camera).

## Run
```bash
python -m app            # from acquisition/: launches the acquisition GUI
```

## Test
```bash
cd shared && pytest -q && cd ../acquisition && pytest -q && cd ../analysis && pytest -q
```
Linux CI needs `QT_QPA_PLATFORM=offscreen`. CI: `.github/workflows/behavior-video.yml`.

## History
Imported from `winstonaluk/dlc-acquisition` (archived) with full history.
