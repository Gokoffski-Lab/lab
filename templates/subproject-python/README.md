# <name>: <one-line purpose>

> **Status:** 🧪 experimental · **Owner:** @<github-handle> · **Language:** Python ≥3.10 ·
> **Runs on:** <analysis PC / laptop / HPC3> · **Docs:** [<workflow page>](https://gokoffski-lab.github.io/lab/workflows/<page>/)

<Two sentences: input → output, and what the output is used for.>

## Layout
```
<name>/
├── pyproject.toml
├── src/<package>/      code
├── tests/              pytest, small fake inputs only
└── config.example.toml paths and parameters (copy to config.toml, which is gitignored)
```

## Install
```bash
cd <path/to/name>
python -m venv .venv && .venv\Scripts\activate      # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -e ".[dev]"
```

## Run
```bash
python -m <package> --config config.toml
```

## Test
```bash
pytest -q
```

## Inputs / outputs
| | Where | Naming |
|---|---|---|
| In | CRSP `sourcedata/...` | |
| Out | CRSP `derivatives/<name>/` | `shared/` helpers |
