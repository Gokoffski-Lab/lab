# 0003 — BIDS-style file names from shared helpers

**Status:** Accepted (eye coding open)

## Decision
`sub-<id>_ses-<YYYYMMDD>[_eye-<..>][_stim-<label>][_run-NN]_<modality>.<ext>`, built only through
`shared/` (Python `labnaming.py`, MATLAB `lab_filename.m`). Both read `shared/vocab.json`.

## Why
The renaming pipeline depends on exact capitalization and field values. With one vocab file and one
builder per language, a new value is a single edit and every tool picks it up.

## Open
- Eye coding: `OD/OS/OU` (schema) vs `LE/RE` (`pl2_to_mat.m`).
- Animal ID format per species.
- Long term, generate `vocab.json` from the `vocab_*` tables in `lab.db`.
