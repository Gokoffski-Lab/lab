# 0003 — BIDS-style file names from shared helpers

**Status:** Accepted · **Updated:** 2026-11-24 (eye coding decided)

## Decision
`sub-<id>_ses-<YYYYMMDD>[_eye-<..>][_stim-<label>][_run-NN]_<modality>.<ext>`, built only through
`shared/` (Python `labnaming.py`, MATLAB `lab_filename.m`). Both read `shared/vocab.json`.

**Eye codes are `OD/OS/OU`** in all code, Python and MATLAB alike. Legacy `LE/RE` (old `pl2_to_mat.m` output)
are accepted as input and mapped `LE→OS`, `RE→OD` via `legacy_eye_map` in `vocab.json`; they are never written.

## Why
The renaming pipeline depends on exact capitalization and field values. With one vocab file and one
builder per language, a new value is a single edit and every tool picks it up. OD/OS/OU matches the
`lab.db` schema and standard ophthalmology usage.

## Open
- Animal ID format per species.
- Long term, generate `vocab.json` from the `vocab_*` tables in `lab.db`.
