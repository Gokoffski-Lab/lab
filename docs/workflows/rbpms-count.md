# RBPMS counting (automated RGC counts)

**Owner:** @winstonaluk · **Projects:** WET-Rat, WET-Pig, DOD (flatmount RBPMS) ·
**Code:** [`analysis/rbpms-count/`](https://github.com/Gokoffski-Lab/lab/tree/main/analysis/rbpms-count) ·
**Last verified:** 2026-11-25

## What it produces
Turns retinal flat-mount images (`.czi`, `.lif`, `.nd2`, `.tif`, and other Bio-Formats containers) in `data/<retina>/` into per-image and per-animal RGC counts, densities, and QC figures in `output/results/`. Non-TIFF inputs are normalized into single-channel 2D `.tif` files, large images are tiled into smaller `.tif` segments with non-overlapping cores, each tile is counted with the Simple RGC method, and tile results fold back into one unified record per original image.

## Before you start
- **Fiji** with the `RBPMS-Count` update site (`https://sites.imagej.net/Gokoffski-Lab/`) or `python scripts/rbpms.py install-review-tool`.
- **JupyterLab Desktop** (or conda: `conda env create -f analysis/rbpms-count/environment.yml`).
- Raw images stay on CRSP or local `data/<retina>/`; never commit images, `output/`, or `tracking/` logs.

## Steps
1. **Inspect inputs** (`rbpms.inspect` or `python scripts/rbpms.py inspect`): scans `data/` with Bio-Formats without loading pixels, writes `output/counts/images.csv` with detected format, series, dimensions, pixel size (`um_per_px`), planned tile count, and any unreadable-file errors.
2. **Normalize, tile, and count** (`rbpms.count` or `python scripts/rbpms.py count --tile-px 2048`):
   - Normalizes each readable image series (selected channel, `t=0`, Z max-projected) into `output/normalized/<retina>/<image>.tif` plus a `.json` provenance sidecar without modifying `data/`.
   - Splits images larger than `tile_px` into overlapping `.tif` tiles under `output/tiles/<retina>/<image>/` using a derived margin (`derive_margin_px`) so boundary cells are segmented intact.
   - Runs Simple RGC on each tile individually, keeping only detections whose centroid falls inside that tile's half-open core, crops `output/counted/<retina>/<tile>.tif` to the core, writes per-cell local and parent coordinates to `output/rois/<retina>/<tile>_rois.csv`, and writes a downsampled parent overview `.jpg` for tiled images.
   - Folds `output/counts/tiles.csv` into one row per original image in `output/counts/auto_counts.csv` with exact summed counts, total `core_px`, `area_mm2`, and `cells_per_mm2`.
3. **Manual review** (Fiji: **Plugins › RGC › Review Counts**): opens core-cropped `.tif` fields under `output/counted/<retina>/`, writes `output/counts/tile_manual_counts.csv`, and updates each `.tif` overlay. `rbpms.counts()` and `rbpms.review_status()` fold completed tile reviews into `output/counts/manual_counts.csv`.
4. **Analysis** (notebook Step 3): calls `rbpms.counts(OUTPUT_FOLDER)` and writes `counts_per_image.csv`, `counts_per_eye.csv`, `counts_per_animal.csv`, and `results/figures/`.

## Outputs

| Artifact | Location | Purpose |
|---|---|---|
| Normalized TIFF + sidecar | `output/normalized/<retina>/<image>.tif` | Single-channel 2D calibrated copy of source |
| Padded tiles | `output/tiles/<retina>/<image>/<tile>.tif` | Smaller `.tif` segments with `TileSpec` metadata |
| Review TIFFs and JPEGs | `output/counted/<retina>/<tile>.tif` | Core-cropped overlays (plus `<image>.jpg` parent overview) |
| Per-cell ROIs | `output/rois/<retina>/<tile>_rois.csv` | Local and parent-image cell coordinates and contrast |
| Tile and image ledgers | `output/counts/tiles.csv`, `auto_counts.csv` | Per-tile rows folded to one unified row per image |
| Analysis tables and plots | `output/results/` | Final counts, densities, and figures |

## QC and verification
- In Step 1, check `output/counts/images.csv` for non-empty `problem` rows and check the overview `.jpg` (magenta outlines are counted, cyan outlines were rejected for low contrast).
- Automated tests use synthetic images only (`python -m unittest discover -s analysis/rbpms-count/tests -v` runs unit and ledger checks anywhere, and exercises full normalize, tile, count, resume, and simulated review in headless Fiji when Fiji is installed).
- Real `.czi`, `.lif`, and `.nd2` datasets on CRSP are validated separately against lab images because proprietary microscope binaries are not synthesized in CI.

## Tracking log
The per-animal log is **not** stored in git (the repo is public). Keep it in a shared folder on CRSP and point the notebook at it with `RBPMS_TRACKING`. `update_log` compares whole counted images against source image series, never tile counts.

## History
Moved from `Gokoffski-Lab/rbpms-count`, code only. Whole-image tiling and non-TIFF normalization were integrated into the main pipeline on `rbpms-count/segment-tifs`.
