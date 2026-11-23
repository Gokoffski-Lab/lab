# shared/

File-naming helpers used by every tool in the lab. See [docs/sops/file-naming.md](../docs/sops/file-naming.md).

```
shared/
├── vocab.json            # allowed eye + modality values (data steward edits only)
├── python/labnaming.py   # build_filename / parse_filename / is_valid
├── python/test_labnaming.py
└── matlab/lab_filename.m # MATLAB builder, same rules
```

Use from Python: add `shared/python` to `PYTHONPATH` (or `sys.path`), then `from labnaming import build_filename`.
Use from MATLAB: `addpath(fullfile(labRoot,'shared','matlab'))`.

Tests: `cd shared/python && python -m pytest -q`.

Changing `vocab.json` changes what every tool accepts, so it needs a pull request (see CODEOWNERS).
