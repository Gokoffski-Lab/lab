# Migration status

## Repos

| Source | Destination | Status |
|---|---|---|
| `winstonaluk/dlc-acquisition` | `acquisition/behavior-video/` | ✅ imported with history (19 commits); archive old repo |
| `winstonaluk/fUS_VisualStim` | `acquisition/stimuli/web/` | ✅ imported with history (14 commits); redirect old Pages URL, then archive |
| `winstonaluk/ptb-visualstim` | `acquisition/stimuli/ptb/` | ✅ imported (README only); **commit the PTB script**; archive |
| `winstonaluk/imaris-pipeline` | `analysis/imaris/` | ✅ nothing to import (empty); delete or archive |
| `Gokoffski-Lab/rbpms-count` | `analysis/rbpms-count/` | ⏳ import with `git subtree add` (or keep separate until rollout) |

## Code that only exists locally

- [ ] `lab.db` repo (`db/`, `tests/`, `demo/`, `docs/erd/`) → `data-system/`
- [ ] `pl2_to_mat.m`, `summarize_recording_duration_triggers.m` → `acquisition/ephys/`
- [ ] PTB-3 stimulus script → `acquisition/stimuli/ptb/`
- [ ] Sholl / SNT preprocessing + sweep code → `analysis/sholl/`
- [ ] Imaris scripts (if any) → `analysis/imaris/`
- [ ] HPC3 job scripts → `analysis/hpc3/`
- [ ] ERG marker-table templates → `acquisition/erg/templates/`

## Docs

- [ ] Paste final Data Organization SOP into `docs/sops/data-organization.md`
- [ ] Move SOPs and training docs from Google Docs into `docs/`
- [ ] Fill every page marked **TODO**
- [ ] Decide eye coding (OD/OS/OU vs LE/RE) and the PDCT expansion

## After pushing

- [ ] Settings → Pages → Source: **GitHub Actions**
- [ ] Settings → Branches: protect `main` (require PR + review for CODEOWNERS paths)
- [ ] Archive old repos (Settings → Archive), after replacing each README with a pointer
- [ ] Update iPad stimulus bookmarks
