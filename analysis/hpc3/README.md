# hpc3: UCI HPC3 job templates

> **Status:** ⏳ to build · **Owner:** @winstonaluk · **Language:** Bash / SLURM ·
> **Runs on:** UCI HPC3 · **Docs:** [UCI HPC3](https://gokoffski-lab.github.io/lab/setup/hpc3/)

One folder per job type, each with `job.sbatch` + a README saying what goes in and what comes out:
```
hpc3/
├── flatmount-merge/     3D merge of ON + retina flatmounts (.lif)
├── pose-finetune/       DeepLabCut / Lightning Pose GPU fine-tuning
└── _common/             module loads, CRSP → scratch staging helpers
```
Jobs call code from elsewhere in the repo (`analysis/sholl/`, `acquisition/behavior-video/analysis/`) instead of copying it.

## Missing code
Any SLURM scripts you've already written on HPC3 (`~/` on the login node).

**No account names, allocation IDs or usernames in committed files**, because the repo is public.
Read them from environment variables instead.
