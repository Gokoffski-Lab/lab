# analysis/

Code that runs **on recorded data** (analysis PC, laptops or HPC3), never at the rig.

| Subproject | What | Language | Status |
|---|---|---|---|
| [`rbpms-count/`](rbpms-count/) | Automated RBPMS⁺ RGC counting in flatmounts, with manual review in Fiji | Fiji (Groovy) + Python notebook | ✅ active |
| [`axq/`](axq/) | Optic nerve CTB axon density after crush (napari panel, CLI, Fiji v2 macro) | Python | 🧪 experimental |
| [`clover-warp/`](clover-warp/) | Reconstruct clover flatmounts by registering petals to the in vivo angiogram | Python | 🧪 experimental |
| [`sholl/`](sholl/) | RGC dendrite Sholl analysis (SNT, Cellpose 3D seeds) | Python / Fiji | ⏳ missing code |
| [`imaris/`](imaris/) | Imaris processing (flatmount counts, filaments) | Python / MATLAB | ⏳ missing code |
| [`hpc3/`](hpc3/) | UCI HPC3 SLURM job templates | Bash / SLURM | ⏳ to build |
| [`simple-rgc/`](simple-rgc/) | First Simple RGC counting workflow | Fiji + Bash | 🗄️ retired (→ rbpms-count) |

Behavior-video analysis (DeepLabCut) lives with its acquisition app in
[`../acquisition/behavior-video/analysis/`](../acquisition/behavior-video/analysis/), because the two share a schema.
