# data-system/

Lab metadata registry: `lab.db` (SQLite) schema v0.2, GLP audit triggers, migrations, and the Streamlit dashboard.

**Status: ⏳ to import.** The code is in Winston's local `lab.db` repo, which isn't on GitHub yet.

Expected layout after import:
```
data-system/
├── db/schema.sql               # 29 tables, views, GLP audit triggers (section 10)
├── db/gen_audit_triggers.py    # re-run after ANY table change
├── db/seed_from_diagram.sql
├── tests/test_schema.py        # pytest -q, must pass before a schema change lands
├── demo/                       # static demo dashboard + sample JSON
├── docs/erd/build_erd.py
└── scripts/                    # profiling / cleaning / migration
```

Import (keeps history, if the local folder is a git repo):
```bash
git subtree add --prefix=data-system /path/to/local/lab-db-repo main
```
If it isn't a git repo, copy the files in and commit.

`data/raw/` (original lab `.xlsx`) is **never committed**. The root `.gitignore` blocks `.xlsx`, `.db` and `data/`.
