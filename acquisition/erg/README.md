# erg: Diagnosys Celeris / Espion export

> **Status:** ⏳ to build · **Owner:** @winstonaluk · **Language:** Python ·
> **Runs on:** analysis PC · **Docs:** [ERG / VEP export](https://gokoffski-lab.github.io/lab/workflows/erg-export/)

Parses analyst-placed Espion **Marker Table** exports into one tidy table per protocol (fVEP P1/N1,
pERG, PhNR a/b-wave + PhNR), with an inter-analyst consistency check.

## Missing code
| File | Notes |
|---|---|
| `templates/fvep_markers.csv`, `templates/perg_markers.csv`, `templates/phnr_markers.csv` | one real export per protocol, with animal IDs replaced by fakes |
| Firebird / Espion extraction notes or scripts, if any | from the Celeris setup work on the analysis PC |

The parser isn't written yet. Start it as `erg/` with its own `pyproject.toml` (see `templates/subproject-python/` at the repo root).
