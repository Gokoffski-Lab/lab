# CRSP access

CRSP is UCI's research storage. It is **storage only** (no compute) and is the lab's canonical archive.

- Requires the **campus network or UCI VPN**, plus **Duo** two-factor.
- Lab data goes in the lab **`share/`** area, never in personal folders.
- Don't run databases or write SQLite files directly on a CRSP mount (see [decision 0002](../decisions/0002-sqlite-single-writer.md)).

!!! note "TODO"
    Add the lab's share path, the mount steps for Windows (lab PCs) and macOS, and who to ask for an account.

## Layout

```
share/
├── sourcedata/   raw instrument files (write-once)
├── derivatives/  processed outputs, one folder per pipeline
└── registry/     lab.db snapshots
```

!!! note "TODO"
    Confirm against the real CRSP layout and the Data Organization SOP.
