# shared: lab-wide naming helpers

> **Status:** ✅ active · **Owner:** @winstonaluk (changes need review) · **Language:** Python + MATLAB ·
> **Docs:** [File naming](https://gokoffski-lab.github.io/lab/sops/file-naming/)

Every tool in the lab builds file names through these helpers. They all read one vocab file.

```
shared/
├── vocab.json                  allowed eye + modality values, legacy LE/RE → OS/OD map
├── python/labnaming.py         build_filename, parse_filename, is_valid, normalize_eye
├── python/test_labnaming.py
├── matlab/lab_filename.m       same rules as the Python builder
├── matlab/lab_eye_code.m       canonical eye code (OD/OS/OU), maps legacy LE/RE
└── matlab/tests/test_lab_naming.m
```

## Use
Python: add `shared/python` to `PYTHONPATH`, then `from labnaming import build_filename`.

MATLAB: `addpath(fullfile(labRoot,'shared','matlab'))`, then `lab_filename('R042','2026-11-23','fvep','txt','eye','OD')`.

## Test
```bash
cd shared/python && python -m pytest -q
```
```matlab
addpath('shared/matlab'); runtests('shared/matlab/tests')   % from repo root
```
CI runs both (`.github/workflows/shared.yml`).

## Changing the vocab
Edit `vocab.json` **and** add a test for the new value in both languages, in the same pull request.
Every tool picks up the change, so the data steward reviews it.
