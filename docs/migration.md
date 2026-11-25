# Migration status

## Imported ✅
| Source | Now at | Notes |
|---|---|---|
| `winstonaluk/dlc-acquisition` | `acquisition/behavior-video/` | full history |
| `winstonaluk/fUS_VisualStim` | `acquisition/stimuli/web/` | full history; served at `/stimuli/` |
| `winstonaluk/ptb-visualstim` | `acquisition/stimuli/ptb/` | README only (script missing) |
| `Gokoffski-Lab/rbpms-count` (main) | `analysis/rbpms-count/` | **code only**: old repo stays private (history has verified counts). Tracking log now local / CRSP |
| Lab desktop: `Axonquantifier` fork (`axq`) | `analysis/axq/` | code only; upstream `legacy/` macros excluded (no upstream license) |
| Lab desktop: `clover-warp` | `analysis/clover-warp/` | was never in git |
| Lab desktop: `SimpleRGC` | `analysis/simple-rgc/` | retired; scripts only (group assignments, reports, kits, data excluded) |
| Lab desktop: `MATLAB/pl2_to_mat.m` | `acquisition/ephys/` | 2025 version, no CSV renaming |
| `winstonaluk/imaris-pipeline` | n/a | was empty |

## Kept private on purpose 🔒
| Repo | Why | Pending branches |
|---|---|---|
| `Gokoffski-Lab/internal-dashboard` (`lab.db` + dashboard) | deployed internal app; names lab members; profiles real spreadsheets | `wip/desktop-899eacn-2026-11-24` (ERD docs + commit `c47c9fb`) |
| `Gokoffski-Lab/rbpms-count` | history contains verified counts and tracking log | `feature/lif-mosaic-counting`, `wip/desktop-899eacn-2026-11-24` (notebook edits), `autocount-v2`, `fix/java-heap-size` |

## Missing code ⏳
| # | What | Destination | Likely location |
|---|---|---|---|
| 1 | CSV-renaming `pl2_to_mat.m`, `summarize_recording_duration_triggers.m` | `acquisition/ephys/` | another ephys computer / Mac |
| 2 | PTB-3 stimulus script | `acquisition/stimuli/ptb/` | Mac used for ephys stimulus |
| 3 | Sholl / SNT code (`sholl-playground` / `dendritic-trees`) | `analysis/sholl/` | Mac or another analysis PC (not on desktop-899eacn) |
| 4 | Imaris XTensions / parameter files (clover counts) | `analysis/imaris/` | Imaris workstation |
| 5 | HPC3 SLURM scripts | `analysis/hpc3/` | HPC3 home directory |
| 6 | ERG marker-table templates | `acquisition/erg/templates/` | analysis PC |

**Possibly exists:** Blackfly ↔ Plexon sync → `acquisition/camera-sync/` · ferret NeuroShank/NeuroGrid → `acquisition/ephys/ferret/` ·
OptoDrum tools → `acquisition/optodrum/` · QuPath scripts (sections) → `analysis/retina-sections/`.

## Not lab code (backed up, not imported)
Local edits to third-party repos on the desktop, saved as patches in the 2026-11-24 backup:
`Matisse` (atsu-kotani/Matisse: retinal model edits), `rgcode` (NCDRlab: environment file).

## Docs to fill
- [ ] Paste the final Data Organization SOP into `docs/sops/data-organization.md`
- [ ] Move SOPs and training docs from Google Docs into `docs/`
- [ ] Every page marked **TODO**

## Repo admin
- [x] Push to `Gokoffski-Lab/lab`, set public · [x] Claude GitHub App installed
- [ ] Settings → Pages → Source: **GitHub Actions**
- [ ] Settings → Branches: protect `main` (require PR, passing CI, CODEOWNERS review)
- [ ] Choose a license (see [decision 0004](decisions/0004-public-repo.md)); `clover-warp` is already MIT; `axq` has none
- [ ] Archive `dlc-acquisition`, `fUS_VisualStim`, `ptb-visualstim`, `imaris-pipeline`
- [ ] Update iPad stimulus bookmarks to `https://gokoffski-lab.github.io/lab/stimuli/`
- [ ] Tell the lab: rbpms-count now lives at `analysis/rbpms-count` in this repo

## Decided
- PDCT = Pole Descent Cliff Task · eye codes OD/OS/OU (legacy LE→OS, RE→OD) · repo is public
