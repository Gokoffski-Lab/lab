# Data organization SOP

Full SOP (living document): **[Data Organization SOP](https://claude.ai/artifact/EwCQc5b9DMmxYfRDmDoZmz)**
· Rollout plan: [Working Demo Plan](https://claude.ai/artifact/3KjLRFTgSZMcUcFGNa7wdC).
Data steward: Winston. PI: Dr. Gokoffski.

!!! note "TODO"
    Paste the final SOP text into this page so it is versioned with the code. The links above are the working drafts.

## Where data lives

| What | Where |
|---|---|
| Raw instrument files | CRSP lab `share/` → `sourcedata/` (**write-once**: read-only after ingest) |
| Processed outputs | CRSP `derivatives/` |
| Metadata registry | `lab.db` (SQLite). Snapshots pushed to CRSP `registry/` |
| Code, SOPs, workflows | This repo (**public**, see [decision 0004](../decisions/0004-public-repo.md)) |
| Signed GLP forms, PII | **Not** on CRSP or in this repo |

Lab data always goes in the lab `share/` area, never in personal folders or on laptops long-term.

## Hard rules

- **SQLite is single-writer.** One app writes a local `lab.db` and pushes snapshots to CRSP.
  Never open `lab.db` for writing over a network mount (CRSP/Box/SSHFS file locking fails).
  See [decision 0002](../decisions/0002-sqlite-single-writer.md).
- **`sourcedata/` is write-once.** Corrections go in derivatives or new records, never in the raw file.
- **Blinding:** the experimental group never appears in paths or file names.
- **ML splits are by animal**, never by frame, slice or session.
- **No PII on CRSP** (cadaver donor details stay out).
- **WET-Pig is GLP (21 CFR 58).** Rows for GLP projects need a user ID (+ reason on edit), deletes
  are blocked, and `audit_log` is append-only. `lab.db` is **not** a validated Part 11 system:
  instrument files and signed forms remain the GLP raw data.
- **Raw spreadsheets are never edited.** Every cleaning step is code, rejected rows are written out
  with reasons, and missing values stay missing (no imputation).

## Conventions

- Dates are ISO 8601 (`2026-11-23`; `20261123` inside file names).
- File names: see [File naming](file-naming.md).
- Vocab values (modality, eye, stim labels) come from the `vocab_*` tables only. New values are added by the data steward.
- **Day 0** is one anchor procedure per animal. Timepoints are stored as day offsets.
  WET: whole-eye transplant. Amblyopia: first day of tarsorrhaphy. DOD / Glaucoma / mTOR-Rheb: TBD.
