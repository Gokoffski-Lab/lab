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

## Eye codes

**`OD` (right), `OS` (left), `OU` (both)**, everywhere, in Python and MATLAB.

The old `pl2_to_mat.m` names used `LE/RE`. Both builders still accept those codes and convert them
(`LE`→`OS`, `RE`→`OD`), so old metadata CSVs keep working. New names are always written with OD/OS/OU,
and the parser rejects `eye-LE`/`eye-RE`. To convert a single value, use `normalize_eye()` (Python)
or `lab_eye_code()` (MATLAB).

## Legacy names

Existing ephys `.mat` files use `brainregion_LE/RE_Light_StimFreq_StimAmplitude_File<N>.mat`
(from the old `pl2_to_mat.m`). Keep them as-is in `sourcedata/`, which is write-once. The migration
script records their new-scheme names in `lab.db` instead of renaming files. From now on, `pl2_to_mat.m`
should name its output with `lab_filename.m`.
