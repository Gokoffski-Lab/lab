# data-system: lab metadata registry

> **Status:** ✅ active, in a **private** repo · **Owner:** @winstonaluk ·
> **Code:** [`Gokoffski-Lab/internal-dashboard`](https://github.com/Gokoffski-Lab/internal-dashboard) (private) ·
> **Docs:** [Data organization](https://gokoffski-lab.github.io/lab/sops/data-organization/) · [Decision 0002](../docs/decisions/0002-sqlite-single-writer.md)

The `lab.db` schema (SQLite, GLP audit triggers), migrations from the lab spreadsheets, and the Streamlit
dashboard (Google Calendar sync, Quartzy ordering, nightly CRSP backups) live in **`Gokoffski-Lab/internal-dashboard`**.

## Why it isn't in this public repo
It's a deployed internal app: it names lab members (user allowlist and tests), and its docs profile
the real lab spreadsheets. Under [decision 0004](../docs/decisions/0004-public-repo.md) it stays private.

To move it here later, first:
1. Move the user allowlist and any UCInetIDs out of the code and tests, into `secrets.toml` and fake IDs.
2. Remove or anonymize `docs/phase1/profile_report.md`.
3. Confirm with the PI that publishing the schema and app is OK.

Then import it with `git subtree add --prefix=data-system https://github.com/Gokoffski-Lab/internal-dashboard.git main`.

## Branches to review there
- `wip/desktop-899eacn-2026-11-24`: ERD docs (`docs/erd/`, `tests/test_erd.py`) and `CLAUDE.md` / overview edits saved from the lab desktop before it was wiped. It also contains commit `c47c9fb` (skeleton system overview), which existed only on that desktop.
