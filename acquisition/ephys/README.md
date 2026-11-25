# ephys: Plexon recording processing

> **Status:** ⏳ missing code · **Owner:** @winstonaluk · **Language:** MATLAB (+ Plexon PL2 SDK) ·
> **Runs on:** analysis PC / laptop · **Docs:** [Ephys .pl2 conversion](https://gokoffski-lab.github.io/lab/workflows/ephys-pl2-conversion/)

## Missing code
| File | What it does | When adding it |
|---|---|---|
| `pl2_to_mat.m` | batch `.pl2` → `.mat`, renames output from a metadata CSV | Build names with `lab_filename.m` and eye codes with `lab_eye_code.m` (old CSVs with LE/RE still work) |
| `summarize_recording_duration_triggers.m` | duration + trigger count per file → CSV | consider writing these during conversion instead |
| `examples/metadata_example.csv` | header + 1–2 rows with **fake IDs** (`R000`) | the repo is public: no real animal data |

Ferret NeuroShank / NeuroGrid code goes in `ferret/` here when it exists.

## Run (once added)
```matlab
addpath('acquisition/ephys'); addpath('shared/matlab');   % from repo root
```
