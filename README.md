# Gokoffski Lab: code & workflows

One public repository for the Gokoffski lab's (UC Irvine, Gavin Herbert Eye Institute) software,
pipelines, SOPs and workflow documentation.

**Most lab members only need the docs site:** https://gokoffski-lab.github.io/lab/
(built from [`docs/`](docs/)). You can fix a typo or add a step in the browser; see
[Getting started](docs/getting-started.md). No git required.

> **This repo is public. Data never goes in it.** Raw and derived data live on CRSP
> ([Data Organization SOP](docs/sops/data-organization.md)). No PII, credentials or unpublished results
> ([decision 0004](docs/decisions/0004-public-repo.md)). CI blocks data file types and files over 5 MB.

## Map

| Folder | What | Status |
|---|---|---|
| [`docs/`](docs/) | SOPs, per-assay workflows, setup guides, decisions (MkDocs site) | ✅ |
| [`shared/`](shared/) | File-naming helpers (Python + MATLAB) and `vocab.json` used by every tool | ✅ |
| [`data-system/`](data-system/) | `lab.db` schema (SQLite), GLP audit triggers, migrations, Streamlit dashboard | ⏳ missing code |
| [`acquisition/`](acquisition/) | **Runs at the rig** | |
| ↳ [`behavior-video/`](acquisition/behavior-video/) | PDCT (Pole Descent Cliff Task) acquisition GUI + DeepLabCut analysis | ✅ |
| ↳ [`stimuli/web/`](acquisition/stimuli/web/) | iPad rat visual stimulus, live at [`/stimuli/`](https://gokoffski-lab.github.io/lab/stimuli/) | ✅ |
| ↳ [`stimuli/ptb/`](acquisition/stimuli/ptb/) | Psychtoolbox-3 stimuli for ephys | ⏳ missing code |
| ↳ [`ephys/`](acquisition/ephys/) | Plexon `.pl2` → `.mat`, recording summaries | ⏳ missing code |
| ↳ [`erg/`](acquisition/erg/) | Celeris/Espion marker-table parsing (fVEP, pERG, PhNR) | ⏳ to build |
| [`analysis/`](analysis/) | **Runs on recorded data** | |
| ↳ [`rbpms-count/`](analysis/rbpms-count/) | Automated RBPMS⁺ RGC counting (Fiji) | ⏳ missing code |
| ↳ [`sholl/`](analysis/sholl/) | RGC dendrite Sholl analysis (SNT) | ⏳ missing code |
| ↳ [`imaris/`](analysis/imaris/) | Imaris processing | ⏳ missing code |
| ↳ [`hpc3/`](analysis/hpc3/) | UCI HPC3 SLURM templates | ⏳ to build |
| [`templates/`](templates/) | Starters for new subprojects (Python, MATLAB, CI) | ✅ |

What's still missing and where it goes: [`docs/migration.md`](docs/migration.md).

## Adding code

Read [Working in the monorepo](docs/contributing/monorepo.md) (summary in [CONTRIBUTING.md](CONTRIBUTING.md)):
copy a folder from `templates/` into `acquisition/` or `analysis/`, give it its own environment and tests,
branch → pull request → CI → merge.

```bash
git clone https://github.com/Gokoffski-Lab/lab.git
```

## Lab-wide rules

1. No data, PII, credentials or unpublished results in git.
2. The experimental group never appears in paths or file names (blinding).
3. ML train/test splits are by animal, never by frame/slice/session.
4. Raw files are never edited; every fix lives in code.
5. File names come from `shared/` helpers. Eye codes are **OD / OS / OU**.
6. New vocab values are added by the data steward.
