# Gokoffski Lab — code & workflows

One repository for the Gokoffski lab's (UC Irvine, Gavin Herbert Eye Institute) software,
pipelines, SOPs and workflow documentation.

**Most lab members only need the docs site:** https://gokoffski-lab.github.io/lab/
(rendered from [`docs/`](docs/)). You can fix a typo or add a step from the browser — see
[Getting started](docs/getting-started.md). No git required.

> **Data never goes in this repo.** Raw and derived data live on CRSP (see the
> [Data Organization SOP](docs/sops/data-organization.md)). `.gitignore` blocks common data
> formats (`.pl2`, `.mat`, `.tif`, `.ims`, `.lif`, `.mp4`, `.xlsx`, `.db`, …).

## Map

| Folder | What | Status |
|---|---|---|
| [`docs/`](docs/) | SOPs, per-assay workflows, setup guides, design decisions (MkDocs site) | ✅ |
| [`data-system/`](data-system/) | `lab.db` schema (SQLite), audit triggers, migrations, Streamlit dashboard | ⏳ to import |
| [`shared/`](shared/) | File-naming helpers (Python + MATLAB) and controlled vocab used by every tool | ✅ v0 |
| [`acquisition/behavior-video/`](acquisition/behavior-video/) | PDCT multi-camera acquisition GUI + DeepLabCut analysis pipeline | ✅ imported |
| [`acquisition/stimuli/web/`](acquisition/stimuli/web/) | iPad rat visual stimulus (flicker / drifting grating), served at `/stimuli/` | ✅ imported |
| [`acquisition/stimuli/ptb/`](acquisition/stimuli/ptb/) | Psychtoolbox-3 visual stimulus scripts (ephys sessions) | ⏳ script to add |
| [`acquisition/ephys/`](acquisition/ephys/) | Plexon `.pl2` → `.mat` conversion + renaming, recording summaries | ⏳ to import |
| [`acquisition/erg/`](acquisition/erg/) | Diagnosys Celeris/Espion export + marker-table parsing (fVEP, pERG, PhNR) | ⏳ to build |
| [`analysis/rbpms-count/`](analysis/rbpms-count/) | Automated RBPMS⁺ RGC counting (Fiji) | ⏳ to import |
| [`analysis/sholl/`](analysis/sholl/) | RGC dendrite Sholl analysis (Fiji/SNT) | ⏳ to import |
| [`analysis/imaris/`](analysis/imaris/) | Imaris processing | ⏳ to import |
| [`analysis/hpc3/`](analysis/hpc3/) | UCI HPC3 SLURM templates (flatmount merging, model fine-tuning) | ⏳ to build |

Migration progress is tracked in [`docs/migration.md`](docs/migration.md).

## For developers

```bash
git clone https://github.com/Gokoffski-Lab/lab.git
cd lab
```

- Each subproject keeps **its own environment** (its own `pyproject.toml` /
  `requirements.txt` or MATLAB path). Don't install the whole repo at once. Read the
  subproject's README (and `CLAUDE.md`, if present) first.
- CI runs only the tests for the folders you changed (`.github/workflows/`).
- Changes to `data-system/` and `shared/` need a pull request and review
  ([CODEOWNERS](.github/CODEOWNERS)); WET-Pig is GLP, so the schema has an audit trail.
- File names come from `shared/` helpers, not hand-built strings.

## Lab-wide rules (short version)

1. No data, no PII, no credentials in git.
2. The experimental group never appears in paths or file names (blinding).
3. ML train/test splits are by animal, never by frame/slice/session.
4. Raw files are never edited; every fix lives in code.
5. New vocab values (modalities, eye codes, stim labels) are added by the data steward.
