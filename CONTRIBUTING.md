# Contributing

Full guide: [docs/contributing/monorepo.md](docs/contributing/monorepo.md) (also on the
[docs site](https://gokoffski-lab.github.io/lab/contributing/monorepo/)).

The essentials:
1. New tool → copy a folder from `templates/` into `acquisition/` (runs at the rig) or `analysis/` (runs on recorded data).
2. Every subproject has a README with the standard header, its own environment, tests, and a CI workflow.
3. Subprojects don't import from each other. Shared code goes in `shared/`.
4. File names come from `shared/` helpers. Eye codes are OD/OS/OU.
5. Branch → pull request → CI passes → merge. Commit messages start with the subproject: `ephys: …`.
6. **This repo is public.** No data, no PII, no credentials, no unpublished results.
