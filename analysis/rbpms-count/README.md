# rbpms-count: automated RGC counting

> **Status:** ⏳ missing code · **Owner:** @winstonaluk · **Language:** Fiji (Java / macro) ·
> **Runs on:** lab Windows PCs via the Fiji update site · **Docs:** [RBPMS counting](https://gokoffski-lab.github.io/lab/workflows/rbpms-count/)

## Missing code
The whole folder, from `Gokoffski-Lab/rbpms-count`. Import it with its history:
```bash
git subtree add --prefix=analysis/rbpms-count https://github.com/Gokoffski-Lab/rbpms-count.git main
```
Then replace that repo's README with a link to this folder, and archive it.
The Fiji update site doesn't change: keep uploading through the Fiji updater as before.
Fine to wait until the lab rollout settles.

Also bring the install/usage instructions from the lab presentation into `docs/workflows/rbpms-count.md`,
and decide where the master count log lives. Not in git: counts are data.
