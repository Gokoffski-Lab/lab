# templates: starting points for new subprojects

Copy one, rename it, fill in the placeholders marked `<…>`. See [docs/contributing/monorepo.md](../docs/contributing/monorepo.md).

| Template | Use for |
|---|---|
| [`subproject-python/`](subproject-python/) | Python pipelines and tools (own `pyproject.toml`, `pytest`) |
| [`subproject-matlab/`](subproject-matlab/) | MATLAB scripts/functions (`runtests`) |
| [`ci-subproject.yml`](ci-subproject.yml) | Path-filtered CI. Copy it to `.github/workflows/<name>.yml` |

```bash
cp -r templates/subproject-python analysis/<name>         # macOS/Linux/Git Bash
```
```powershell
Copy-Item -Recurse templates\subproject-python analysis\<name>   # Windows PowerShell
```
