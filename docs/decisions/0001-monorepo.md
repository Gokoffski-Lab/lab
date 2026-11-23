# 0001 — One lab monorepo

**Status:** Accepted · **Date:** 2026-11-23

## Context
Lab code was spread across personal GitHub repos (`dlc-acquisition`, `fUS_VisualStim`, `ptb-visualstim`,
an empty `imaris-pipeline`), one org repo (`rbpms-count`), and scripts that existed only on laptops
(`pl2_to_mat.m`, the `lab.db` schema, Sholl code). SOPs lived in Google Docs. Naming conventions were
written separately in several tools.

## Decision
One repo, `Gokoffski-Lab/lab`, with `docs/` (MkDocs site), `data-system/`, `shared/`, `acquisition/`, `analysis/`.
Old repos are imported **with history** (`git subtree add`) and then archived with a pointer README.

## Consequences
- One place to look; docs and code change together; one set of naming helpers.
- Each subproject keeps its own environment; CI is path-filtered.
- Tools other labs might reuse can be split out later with `git subtree split`.
- `rbpms-count` may stay separate until its Fiji update-site rollout settles.
