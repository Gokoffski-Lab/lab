# data-system: lab metadata registry

> **Status:** ⏳ missing code · **Owner:** @winstonaluk · **Language:** SQL (SQLite), Python (Streamlit) ·
> **Runs on:** one data-entry machine (single writer), snapshots to CRSP `registry/` ·
> **Docs:** [Data organization](https://gokoffski-lab.github.io/lab/sops/data-organization/) · [Decision 0002](../docs/decisions/0002-sqlite-single-writer.md)

`lab.db` schema v0.2 (29 tables, views, GLP audit triggers), migrations from the lab spreadsheets, and the Streamlit dashboard.

## Missing code
The whole folder. It's the local `lab.db` repo described in the project handoff. Import it with its history:
```bash
git subtree add --prefix=data-system /path/to/local/lab-db-repo main
```

| File | Purpose |
|---|---|
| `db/schema.sql` | schema v0.2, GLP audit triggers in section 10 |
| `db/gen_audit_triggers.py` | regenerates section 10. **Re-run after any table change** |
| `db/seed_from_diagram.sql` | vocab + projects + one smoke-test rat |
| `tests/test_schema.py` | `pytest -q`, must pass before a schema change lands |
| `demo/` | static demo dashboard + sample JSON (**fake data only**, the repo is public) |
| `docs/erd/build_erd.py` | ER diagram generator |
| `scripts/` | profiling / cleaning / migration (to build) |

**Never commit** `data/raw/` (original lab `.xlsx`) or any `lab.db`. The root `.gitignore` and the
`repo-hygiene` CI check block them. After importing, delete the old repo's own `.gitignore` entries
only if they duplicate the root ones.

After import: add `.github/workflows/data-system.yml` (copy `shared.yml`, change the paths, run `pytest -q` in `data-system/`).
