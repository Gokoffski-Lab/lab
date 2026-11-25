# Automated RGC counting with manual review (Simple RGC, Fiji)

> **Status:** 🗄️ retired · **Owner:** @winstonaluk · **Language:** Fiji (Groovy) + Bash + Python ·
> **Replaced by:** [`analysis/rbpms-count/`](../rbpms-count/)
>
> The first Simple RGC–based counting workflow, kept for reproducibility of counts made with it. Imported from a
> local folder (2026-11-24): scripts, handoff notes and the install-kit builder only. Sample group assignments
> (`config/`), generated reports (`share/`), built kits, images and results were **not** imported (blinding / data).
> `scripts/` expects `config/sample_groups.csv` locally; never commit it.

Counts EGFP-labelled RGC somata in 20x widefield flat-mount fields. The workflow has three steps:

1. **Automated count.** The Simple RGC pipeline (Cross et al. 2021, JORS 9:15) runs headless in Fiji on every image.
2. **Manual review.** Each field is opened in Fiji on its original image, with one point on every counted cell. A person adds the cells it missed and removes the false detections.
3. **Analysis.** Densities come from the reviewed counts. A project's analysis is written only once every field of every retina in it has been reviewed.

## Run

```bash
scripts/run_analysis.sh
```

This counts any new images, then writes the review status. Then, in Fiji (normal window), run
**Plugins > RGC > Review Counts Full**, choose `results/simple_rgc`, and enter your initials.
Run `scripts/run_analysis.sh` again after reviewing. When a project is fully reviewed, its report appears in
`results/simple_rgc/summary/<project>/`.

Other options:
- `OVERWRITE=true scripts/run_analysis.sh` recounts everything. Manual reviews are kept, but if the settings changed, the outlines and points no longer match, so review again.
- `PRELIMINARY=true scripts/run_analysis.sh` also writes analyses for projects that are not fully reviewed, from the automated counts, marked PRELIMINARY.
- Settings are environment variables: `RADIUS`, `SIGMA`, `MIN_D`, `MAX_D`, `MIN_CONTRAST`, `BG_RADIUS`, `CHANNEL`, `AXONS`, `DATA_DIR`, `OUT_DIR`.
- Summary only: `python scripts/summarize_counts.py results/simple_rgc [--preliminary]`.

Requirements:
- Fiji at `C:/Users/<you>/Documents/Fiji`. For another location, set `FIJI_DIR`.
- Python 3 with pandas, scipy, matplotlib and statsmodels.
- The review tool is installed by copying `scripts/review_counts.groovy` to `Fiji/scripts/Plugins/RGC/Review_Counts_Full.groovy` and restarting Fiji.
  The Simple RGC plugin itself is not needed.

## Reviewing a field

The review window shows the original image (display contrast only is stretched):
- magenta outline: counted automatically
- cyan outline: detected but rejected as too dim
- yellow point: one per counted cell; these are what you correct

| Action | What it does |
|---|---|
| Click on a cell | adds a missed cell |
| Alt + click on a point | removes a point that is not a cell |
| Drag a point | moves it |
| Save and next | stores the field and opens the next one |
| Skip this field | leaves it unreviewed |
| Stop reviewing | ends the session; progress is kept |

A note can be added to each field. "Review fields that are already reviewed again" reopens fields, starting from their saved points.

## Samples and projects

`config/sample_groups.csv` lists every retina with its `project`, `animal`, `eye` and `group`.
- Right eyes are controls (`group = control`). Left-eye conditions must come from the surgery records, not from sample names.
- List planned retinas before they are imaged. A project's analysis waits until all of its listed retinas are counted and reviewed.
- When both eyes of an animal are present, the report adds a left-vs-right comparison (L as % of R, paired t-test).

## Layout

```
data/<sample>/<sample>_20x_<quadrant a-d><position 1-3>.czi   raw images (never modified)
config/sample_groups.csv          sample -> project, animal, eye, group
scripts/
  fiji_headless.sh                runs a Fiji script headless through Fiji's bundled Java
  simple_rgc_count.groovy         automated count, per-cell measurements, review TIFFs, QC overlays
  review_counts.groovy            manual review in Fiji (installed as Plugins > RGC > Review Counts Full)
  summarize_counts.py             review status, automated-vs-manual agreement, project analyses
  run_analysis.sh                 runs counting and summary
results/simple_rgc/
  counts/field_counts.csv         automated count per field (raw Simple RGC and brightness-filtered)
  cells/<sample>/*_cells.csv      every detected object: position, size, shape, intensity, contrast
  rois/<sample>/*_rois.zip        ImageJ ROI sets of the automated outlines
  review/<sample>/*.tif           original image + calibration + outlines (+ final points once reviewed)
  manual/manual_counts.csv        one row per reviewed field: automated, removed, added, final, reviewer
  manual/<sample>/*_points.csv    every reviewed point (auto_kept, added, removed)
  overlays/<sample>/*.jpg         quick-look JPEGs of the automated result
  summary/review/                 REVIEW_STATUS.md, agreement, brightness cut-off calibration
  summary/<project>/              REPORT.md, tables, statistics, figures (reviewed counts only)
  archive/                        earlier outputs kept for reference
results/parameter_tuning/         Niblack radius x blur sweep on 5 fields
```

## Why review TIFFs instead of converting the .czi files

Counting reads the .czi files directly with Bio-Formats, so converting them is not needed, and the .czi files stay
the untouched originals with all microscope metadata. The review TIFF in `review/` is the converted copy used for
checking: the same pixel values, the pixel size, and the outlines and points stored as an ImageJ overlay, so the
counts live on the image. Opening one in Fiji shows exactly what was counted. Each is about 6 MB.

## Method

1. **Input.** Bio-Formats opens every series. The morphology channel is selected and Z-stacks are max-projected.
   Current data: single-plane EGFP, 1936 x 1460 px at 0.227 µm/px, 0.1457 mm² per field.
2. **Simple RGC `extractCells`.** The same steps as `CellSegmentationService.kt`: 8-bit, Niblack local threshold,
   optional axon removal, Gaussian blur, Otsu threshold, EDM watershed, size filter.
3. **Parameters.** Niblack radius 60 px, sigma 8, diameter 35-130 px (8-30 µm). The plugin defaults (radius 20,
   sigma 3) fragment somata at this resolution. Sweep in `results/parameter_tuning/`.
4. **Brightness filter (added).** Object mean / rolling-ball background (radius 100 px) must be at least 1.15.
   Once fields are reviewed, `summary/review/cutoff_calibration.csv` shows which cut-off best reproduces the manual counts.
5. **Manual review.** Final count per field = automated points kept + points added.
6. **Analysis.** Density = final count / field area, averaged per retina; groups compared against `control`
   (Welch t-test, Mann-Whitney, mixed model with position), and left vs right per animal when both eyes exist.

## Limitations
- Watershed sometimes splits one large soma or merges a tight cluster; reviewers should fix these by removing or adding points.
- The field-code meaning (letter = quadrant, digit = position) is assumed.
- Recounting with new settings invalidates earlier reviews of those fields.

## Implementation notes
- `fiji-windows-x64.exe` hides output and exit codes, so `fiji_headless.sh` calls Fiji's bundled Java directly.
- `RoiManager` cannot be created headless, so outlines are collected from the ParticleAnalyzer overlay.
- Script parameters use `persist=false` so values from an earlier run are not reused silently.
- `review_counts.groovy` has a hidden `simulate` parameter used to test it headless.
