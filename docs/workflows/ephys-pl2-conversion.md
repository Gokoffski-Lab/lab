# Ephys: `.pl2` → `.mat` conversion

**Owner:** Winston · **Code:** [`acquisition/ephys/`](https://github.com/Gokoffski-Lab/lab/tree/main/acquisition/ephys) (pending import)

## What it produces
- `pl2_to_mat.m` batch-converts Plexon `.pl2` recordings to `.mat` (MATLAB 5.0 format) and renames them
  from a metadata CSV. Old output names: `brainregion_LE/RE_Light_StimFreq_StimAmplitude_File<N>.mat`
(legacy; new output follows [File naming](../sops/file-naming.md)).
- `summarize_recording_duration_triggers.m` writes the recording duration and trigger count for each file to a summary CSV.

## Before you start
- MATLAB + Plexon OmniPlex/PL2 SDK on the MATLAB path
- Metadata CSV with one row per recording. Its values must match the vocab exactly, including capitalization.

## Steps
!!! note "TODO"
    Add once the scripts are committed: where the metadata CSV comes from, how to run each script, and where outputs go on CRSP.

## Notes
- MATLAB 5.0 `.mat` can't be partly read (`load`/`matfile` can't pull single struct-array fields). For speed,
  load only the variables and channels you need, and use `parfor` across files.
- Planned: write duration/trigger count during conversion so summaries don't reload waveforms.
- To do when importing: replace the hand-built names in `pl2_to_mat.m` with `shared/matlab/lab_filename.m`.
  Eye codes are OD/OS/OU. `LE`/`RE` values in old metadata CSVs are converted automatically (`LE`→`OS`, `RE`→`OD`).
