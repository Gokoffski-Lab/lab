# sholl: RGC dendrite Sholl analysis

> **Status:** ⏳ missing code · **Owner:** @winstonaluk · **Language:** Python + Fiji/SNT ·
> **Runs on:** analysis PC (GPU for Cellpose) / HPC3 · **Docs:** [Sholl analysis](https://gokoffski-lab.github.io/lab/workflows/sholl-snt/)

## Missing code
From the local `sholl-playground` / `dendritic-trees` project:

| Piece | Notes |
|---|---|
| Preprocessing (dendrite enhancement, 3×3×3 binning) | macro or Python |
| Cellpose 3D soma segmentation → SNT seed labels image | |
| SNT auto-trace + 3D Sholl (step 0, channel C=2) | script, not GUI clicks |
| Parameter sweep vs. ground truth (incl. Dryad mole-rat surrogate) | |
| `environment.yml` or `pyproject.toml` | pin Cellpose and SNT versions |

Commit code and small fake/synthetic test stacks only. Images, `.traces`, seeds and outputs stay on CRSP
(`.gitignore` blocks `.tif`/`.ims`). Download the Dryad data with a script instead of committing it.
