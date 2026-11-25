# analysis/

Code that runs **on recorded data** (analysis PC, laptops or HPC3), never at the rig.

| Subproject | What | Language | Status |
|---|---|---|---|
| [`rbpms-count/`](rbpms-count/) | Automated RBPMS⁺ RGC counting | Fiji (Java/macro) | ⏳ missing code |
| [`sholl/`](sholl/) | RGC dendrite Sholl analysis (SNT, Cellpose 3D seeds) | Python / Fiji | ⏳ missing code |
| [`imaris/`](imaris/) | Imaris processing (flatmount counts, filaments) | Python / MATLAB | ⏳ missing code |
| [`hpc3/`](hpc3/) | UCI HPC3 SLURM job templates | Bash / SLURM | ⏳ to build |

Behavior-video analysis (DeepLabCut) lives with its acquisition app in
[`../acquisition/behavior-video/analysis/`](../acquisition/behavior-video/analysis/), because the two share a schema.
