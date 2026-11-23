# File naming

BIDS-style, built by code (never by hand):

```
sub-<id>_ses-<YYYYMMDD>[_eye-<eye>][_stim-<label>][_run-<NN>]_<modality>.<ext>
```

| Part | Rule | Example |
|---|---|---|
| `sub` | animal ID, letters/digits only | `sub-R042` |
| `ses` | session date | `ses-20261123` |
| `eye` | optional, from vocab | `eye-OD` |
| `stim` | optional, letters/digits only | `stim-10Hz` |
| `run` | optional, 2 digits | `run-01` |
| modality | from vocab | `fvep` |

Example: `sub-R042_ses-20261123_eye-OD_stim-flash_run-01_fvep.txt`

Never put the experimental group, treatment arm or initials in a name.

## Helpers

The allowed values live in one file, [`shared/vocab.json`](https://github.com/Gokoffski-Lab/lab/blob/main/shared/vocab.json),
read by both helpers.

=== "Python"

    ```python
    from labnaming import build_filename, parse_filename
    build_filename("R042", "2026-11-23", "fvep", "txt", eye="OD", stim="flash", run=1)
    # 'sub-R042_ses-20261123_eye-OD_stim-flash_run-01_fvep.txt'
    parse_filename("sub-R042_ses-20261123_fvep.txt")
    ```

=== "MATLAB"

    ```matlab
    addpath(fullfile(labRoot, 'shared', 'matlab'))
    name = lab_filename('R042', '2026-11-23', 'fvep', 'txt', 'eye', 'OD', 'run', 1);
    ```

!!! warning "Open decision"
    Eye coding: the schema uses `OD/OS/OU`, but `pl2_to_mat.m` output names use `LE/RE`.
    `vocab.json` follows the schema (`OD/OS/OU`) until this is decided. Changing it means one edit to `vocab.json`.

## Legacy names

Existing ephys `.mat` files use `brainregion_LE/RE_Light_StimFreq_StimAmplitude_File<N>.mat`
(from `pl2_to_mat.m`). Keep them as-is in `sourcedata/`. The migration script maps them to the new
scheme in `lab.db` instead of renaming files.
