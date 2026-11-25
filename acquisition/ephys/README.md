# ephys: Plexon recording processing

> **Status:** ✅ active · **Owner:** @winstonaluk · **Language:** MATLAB (+ Plexon MATLAB Offline Files SDK) ·
> **Runs on:** analysis PC / laptop · **Docs:** [Ephys .pl2 conversion](https://gokoffski-lab.github.io/lab/workflows/ephys-pl2-conversion/)

| File | What it does |
|---|---|
| `pl2_to_mat.m` | Batch `.pl2` → `.mat`. Asks for a top-level folder; converts every subfolder whose name starts with a 4-digit animal ID; writes to `data/mat/` under the current folder (outside the repo, or gitignored) |

## Run
```matlab
% Plexon "MatlabOfflineFilesSDK" folder must be in the current folder (the script addpaths ./MatlabOfflineFilesSDK)
pl2_to_mat
```

## Still to do
- This is the 2025 version saved from the lab desktop. The renaming-from-metadata-CSV version (LE/RE names) wasn't on that machine. If it's on another computer, commit it here.
- Build output names with `shared/matlab/lab_filename.m` (eye codes OD/OS/OU; `lab_eye_code` converts LE/RE).
- `summarize_recording_duration_triggers.m`: still missing.
- `examples/metadata_example.csv`: header + fake rows (`R000`), once the CSV-driven version is here.

Ferret NeuroShank / NeuroGrid code goes in `ferret/` here when it exists.
