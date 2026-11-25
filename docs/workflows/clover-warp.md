# Clover flatmount reconstruction (clover-warp)

**Owner:** Winston · **Projects:** retina flatmount RGC counts (RBPMS + CTB) ·
**Code:** [`analysis/clover-warp/`](https://github.com/Gokoffski-Lab/lab/tree/main/analysis/clover-warp)

## What it produces
Each counted cell's position in real retinal coordinates. It gets these by registering every petal of a clover flatmount to the same
eye's in vivo angiogram, using the vasculature, instead of guessing geometry from the cut outline.
Method and assumptions: `docs/METHOD.md` in the subproject.

## Before you start
- `pip install -e ".[dev,vendor]"` in `analysis/clover-warp/` (`vendor` adds `.lif`/`.czi` readers)
- Per dataset: a config copied from `config/example.yaml`. **Measure retinal radius and rim eccentricity for your colony**, since the defaults are literature values.
- Large datasets: `scripts/hpc3_register.slurm` (set `--account` from your allocation; don't commit it).

## Steps
!!! note "TODO"
    Add the operator steps (init-config → landmarks → `cloverwarp auto`/`manual`) and where outputs go on CRSP.

## Outputs
The resolved config is written next to each result as `<dataset>_config_used.yaml`. A result without it isn't reproducible.
