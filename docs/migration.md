# Migration status

## Imported ✅
| Source | Now at | Notes |
|---|---|---|
| `winstonaluk/dlc-acquisition` | `acquisition/behavior-video/` | full history; build notes moved to `notes/` |
| `winstonaluk/fUS_VisualStim` | `acquisition/stimuli/web/` | full history; page now `index.html`, served at `/stimuli/` |
| `winstonaluk/ptb-visualstim` | `acquisition/stimuli/ptb/` | README only (script missing, see below) |
| `winstonaluk/imaris-pipeline` | n/a | was empty |

## Missing code ⏳

Code that exists on lab computers but isn't in the repo yet. Each destination folder's README lists the exact files and how to import them.

| # | What | Destination | Likely location | How |
|---|---|---|---|---|
| 1 | `lab.db` repo (`db/`, `tests/`, `demo/`, `docs/erd/`, `scripts/`) | `data-system/` | Winston's Mac | `git subtree add` (it's a git repo) |
| 2 | `pl2_to_mat.m`, `summarize_recording_duration_triggers.m` + fake example metadata CSV | `acquisition/ephys/` | ephys analysis computer | copy |
| 3 | PTB-3 stimulus script | `acquisition/stimuli/ptb/` | Mac used for ephys stimulus | copy |
| 4 | `Gokoffski-Lab/rbpms-count` | `analysis/rbpms-count/` | GitHub (private org repo) | `git subtree add` |
| 5 | Sholl / SNT: preprocessing, Cellpose seeds, tracing, parameter sweep | `analysis/sholl/` | analysis PC (`sholl-playground` / `dendritic-trees`) | copy (or subtree if git) |
| 6 | Imaris XTensions / batch scripts / parameter `.xml` (e.g. clover counts) | `analysis/imaris/` | Imaris workstation | copy, or document GUI steps |
| 7 | HPC3 SLURM scripts | `analysis/hpc3/` | HPC3 home directory | copy, strip account names |
| 8 | ERG marker-table templates (fVEP, pERG, PhNR) | `acquisition/erg/templates/` | analysis PC | copy, fake IDs |

**Possibly exists. Add it if it does:**
- Blackfly S ↔ Plexon GPIO sync code → `acquisition/camera-sync/`
- Ferret NeuroShank / NeuroGrid processing → `acquisition/ephys/ferret/`
- OptoDrum tracking fixes or export parsers → `acquisition/optodrum/`
- QuPath / ImageJ scripts for RGC + bipolar counts in sections → `analysis/retina-sections/`
- Spreadsheet profiling / cleaning scripts for `lab.db` → `data-system/scripts/`

## Docs to fill
- [ ] Paste the final Data Organization SOP into `docs/sops/data-organization.md`
- [ ] Move SOPs and training docs from Google Docs into `docs/`
- [ ] Every page marked **TODO**

## Repo admin
- [x] Push to `Gokoffski-Lab/lab`, set public
- [ ] Settings → Pages → Source: **GitHub Actions**
- [ ] Settings → Branches: protect `main` (require PR, passing CI, CODEOWNERS review)
- [ ] Choose a license (see [decision 0004](decisions/0004-public-repo.md))
- [ ] Install the Claude GitHub App on the org (lets Claude push branches and open PRs)
- [ ] Archive `dlc-acquisition`, `fUS_VisualStim`, `ptb-visualstim`, `imaris-pipeline` (pointer README first)
- [ ] Update iPad stimulus bookmarks to `https://gokoffski-lab.github.io/lab/stimuli/`

## Decided
- PDCT = Pole Descent Cliff Task
- Eye codes OD/OS/OU in all code (legacy LE→OS, RE→OD)
- Repo is public
