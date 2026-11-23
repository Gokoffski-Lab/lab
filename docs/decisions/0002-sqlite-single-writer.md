# 0002 — SQLite, single writer

**Status:** Accepted

## Context
CRSP is network storage reached over SSH/VPN. POSIX file locking doesn't work reliably over network
filesystems (CRSP, Box, NFS, SSHFS), so several clients writing a shared SQLite file would corrupt it.

## Decision
One data-entry app writes a **local** `lab.db` and pushes snapshots to CRSP `registry/`.
Dashboards read pulled copies or exported snapshots only.

## Consequences
- Simple, no server to run, and fits the lab's IT setup.
- Only one machine can do data entry at a time. If several people need to enter data at once,
  revisit with a small server database.
