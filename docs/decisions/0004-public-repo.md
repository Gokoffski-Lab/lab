# 0004 — The repo is public

**Status:** Accepted · **Date:** 2026-11-24

## Decision
`Gokoffski-Lab/lab` is public, so the docs site (GitHub Pages) and MATLAB CI are free.

## Consequences: what never goes in
Anyone on the internet can read every commit, **including history**. Deleting a file later doesn't remove it.

- **No data**: raw or processed, images, video, spreadsheets, `lab.db`. Data stays on CRSP.
- **No unpublished results**: figures, counts or summary tables from ongoing studies.
- **No PII**: cadaver donor details, staff personal info.
- **No credentials or access details**: passwords, tokens, VPN configs, CRSP hostnames with usernames, IP addresses of lab machines.
- **No GLP raw records or signed forms** (WET-Pig).
- **No protocol details you wouldn't publish**: IACUC protocol numbers and unpublished surgical methods stay in internal docs.

Example metadata files in the repo use fake IDs (`R000`, `TEST01`).

CI (`repo-hygiene.yml`) fails a pull request that adds data-type files or any file over 5 MB.

If something sensitive is committed, tell the data steward immediately. Rotate any exposed credential first,
then the history can be rewritten (`git filter-repo`). Assume it was already copied.

## Open
- **License.** Without one, others can read the code but not legally reuse it. MIT is common for lab tools; check with the PI / UCI first.
