# Ephys: `.pl2` → `.mat` conversion

**Owner:** Winston · **Code:** [`acquisition/ephys/`](https://github.com/Gokoffski-Lab/lab/tree/main/acquisition/ephys) (pending import)

## What it produces
- `pl2_to_mat.m` batch-converts Plexon `.pl2` recordings to `.mat` (MATLAB 5.0 format) and renames them
  from a metadata CSV. Current output names: `brainregion_LE/RE_Light_StimFreq_StimAmplitude_File<N>.mat`.
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
- Planned: build output names with `shared/matlab/lab_filename.m`. Needs the OD/OS vs LE/RE decision first.
