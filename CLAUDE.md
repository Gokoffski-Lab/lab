# CLAUDE.md: Gokoffski lab monorepo

Public monorepo for the Gokoffski lab (UCI, Gavin Herbert Eye Institute): lab tools, pipelines, SOPs and workflow docs.
Read `docs/contributing/monorepo.md` before adding or moving code.

## Layout
- `acquisition/<tool>/`: runs at the rig (recording, stimuli, instrument export)
- `analysis/<tool>/`: runs on recorded data
- `data-system/`: `lab.db` (SQLite) schema, migrations, Streamlit dashboard
- `shared/`: naming helpers (Python `labnaming.py`, MATLAB `lab_filename.m` / `lab_eye_code.m`) + `vocab.json`
- `docs/`: MkDocs site (SOPs, workflows, setup, decisions). `templates/`: new-subproject starters

Each subproject is self-contained: its own README, environment and tests. If a subproject has its own
`CLAUDE.md` (e.g. `acquisition/behavior-video/`), read it before working there; its rules apply inside that folder.

## Hard rules
- **Public repo:** never commit data (`.pl2 .mat .tif .ims .lif .mp4 .xlsx .db` …), PII, credentials, hostnames/usernames, or unpublished results. Example files use fake IDs (`R000`).
- Subprojects never import from each other. Shared code goes in `shared/` (that change needs review).
- File names are built with `shared/` helpers. Eye codes are **OD/OS/OU** (legacy LE→OS, RE→OD on input only).
- The experimental group never appears in paths or file names. ML splits are by animal.
- `data-system/`: SQLite is single-writer. Re-run `db/gen_audit_triggers.py` after any table change. WET-Pig is GLP: never weaken audit triggers.
- Code or behavior changes update the matching `docs/workflows/` page in the same commit.
- PDCT = Pole Descent Cliff Task.

## Commands
- Naming tests: `cd shared/python && python -m pytest -q`; MATLAB: `runtests('shared/matlab/tests')`
- Behavior video: see `acquisition/behavior-video/README.md`
- Docs: `pip install mkdocs-material && mkdocs serve` (build check: `mkdocs build --strict`)

Commit messages start with the subproject: `sholl: …`, `docs: …`.
