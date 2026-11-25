# rbpms-count: automated RGC counting

> **Status:** ✅ active · **Owner:** @winstonaluk · **Language:** Fiji (Groovy) + Python notebook ·
> **Runs on:** lab Windows PCs and Macs · **Docs:** [RBPMS counting](https://gokoffski-lab.github.io/lab/workflows/rbpms-count/)
>
> Part of the public lab monorepo (`analysis/rbpms-count/`). Moved from `Gokoffski-Lab/rbpms-count` (code only).
> That repo stays private because its history holds count data. **Images, results and the tracking log are never uploaded.**

Count retinal ganglion cells (RGCs) in retinal flat-mount images, check the counts by eye, and get tables and
figures of the results. Works on **Mac and Windows**.

You do not need to know how to program. Everything is run from one notebook, `rbpms_count.ipynb`, by clicking
through it from top to bottom. The work happens in three steps:

| Step | What happens | Where you do it |
|---|---|---|
| **1. Automated count** | Fiji counts the cells in every image and saves a copy with the counted cells outlined | the notebook |
| **2. Manual review** | You look at every image and fix the count: add cells that were missed, remove ones that are wrong | Fiji |
| **3. Analysis** | Spreadsheets (.csv) and figures of the counts per image, per eye and per animal | the notebook |

The counting uses the method of the Simple RGC plugin for Fiji
(Cross et al. 2021, *Journal of Open Research Software* 9:15; [github.com/sonjoonho/SimpleRGC](https://github.com/sonjoonho/SimpleRGC)).
You do not need to install that plugin.

---

## Before you start (one time only)

You need three free programs. Install them once; after that you only repeat "Every time" below.

### 1. Fiji (image analysis)
1. Download Fiji from **[fiji.sc](https://fiji.sc)** for your computer (Mac or Windows).
2. Unzip it.
   - **Mac:** drag `Fiji.app` into your **Applications** folder.
   - **Windows:** move the `Fiji.app` folder (sometimes just called `Fiji`) into your **Documents** folder.
3. Open Fiji once to check it works, then close it.
   - **Mac:** if you see "Fiji cannot be opened because the developer cannot be verified", right-click (or Control-click)
     `Fiji.app`, choose **Open**, then **Open** again. You only need to do this once.
4. Add the lab's **update site**, so Fiji installs the review tool and keeps it up to date:
   1. In Fiji, choose **Help > Update...** and wait for it to finish checking.
   2. Click **Manage Update Sites**, then **Add Unlisted Site**.
   3. In the new row, type `RBPMS-Count` as the **Name** and `https://sites.imagej.net/Gokoffski-Lab/` as the
      **URL**, and make sure its box is ticked.
   4. Click **Apply and Close**, then **Apply Changes**. Restart Fiji when it asks.
   5. Check that **Plugins > RGC > Review Counts** is now in the menu.

   From then on, when a new version of the review tool is published, Fiji says updates are available when it
   starts (or run **Help > Update...**): click **Apply Changes** and restart Fiji.

The notebook looks for Fiji in those places. If you put it somewhere else, you can tell the notebook where it is.

### 2. JupyterLab Desktop (runs the notebook)
1. Download **JupyterLab Desktop** from
   [github.com/jupyterlab/jupyterlab-desktop](https://github.com/jupyterlab/jupyterlab-desktop#installation)
   (scroll to "Installation" and pick the installer for your computer).
2. Install it like any other program. The first time it opens, let it install its Python environment if it asks.

If you already use Anaconda, Jupyter or VS Code, those work too.

**Conda users:** `conda env create -f environment.yml`, then pick the `rbpms-count` environment as the
notebook's kernel (VS Code: **Select Kernel** at the top right). See `environment.yml` if conda asks about Terms of Service.

### 3. This project
Get a copy of this project on your computer. Either:
- **Simplest:** go to [github.com/Gokoffski-Lab/lab](https://github.com/Gokoffski-Lab/lab), click the green **Code**
  button, then **Download ZIP**. Unzip it somewhere easy to find, such as your Documents folder.
- **Better if you will get updates or share changes:** install **[GitHub Desktop](https://desktop.github.com)**,
  sign in, choose **File > Clone repository**, and pick `Gokoffski-Lab/lab`. To get updates later, click
  **Fetch origin**, then **Pull origin**.

This project is the folder `analysis/rbpms-count` inside the lab repository. It contains `rbpms_count.ipynb`,
a `data` folder and a `scripts` folder. Open **that** folder in JupyterLab (not the top of the lab repository).

---

## Every time

### Put your images in the `data` folder
Make one folder per retina inside `data`, named after the retina, and put that retina's images in it:

```
rbpms-count/
  data/
    1001L/
      1001L_20x_a1.czi
      1001L_20x_a2.czi
      ...
    1001R/
      1001R_20x_a1.czi
      ...
```

- **Name each retina folder with the animal number and the eye**: `1001L` is animal 1001, left eye; `1001R` is
  the right eye. Extra text after it is fine (`1001L - XY`). The analysis uses these names to add up counts per animal.
- Image files can be `.czi`, `.lif`, `.nd2`, `.tif`, `.tiff`, `.btf`, `.oib`, `.oif`, `.oir`, `.lsm`, `.ims`, `.vsi`, `.ics`, `.zvi`, `.lei`, `.dv`, `.stk`, or `.nd`.
- Your images are never changed. The notebook inspects each file's format and metadata, normalizes non-TIFF images (and multi-channel or Z-stack images) into single-channel 2D `.tif` files under `output/normalized/`, and counts from those copies.
- Large `.tif` images wider or taller than `TILE_SIZE` (default `2048` px) are automatically split into overlapping `.tif` tiles under `output/tiles/`. Each tile is counted individually, and only cells whose centroid lies inside that tile's non-overlapping core are kept, so counts across all tiles sum to one exact total per original image without double-counting.
- Images can also stay where they are (for example on a shared drive): type that folder in the notebook's Settings box instead.

### Open the notebook
1. Open **JupyterLab Desktop** and choose **Open Folder...** (or **File > Open Folder**). Select the `rbpms-count` folder.
2. In the file list on the left, double-click **`rbpms_count.ipynb`**.
3. If asked to choose a kernel, choose the default **Python 3** one.

### Run it
The notebook is a list of boxes. Grey boxes contain code; the others are instructions.
**Click on a grey box and press Shift + Enter** to run it. Its result appears underneath. Go from top to bottom.
While a box runs, it shows `[*]` on its left.

1. **Settings box:** check the folder names, `TILE_SIZE`, and which animals to count (`COUNT_WHICH`).
2. **Set-up box:** it should print "Fiji found at: ...". If not, see "Something went wrong" below.
3. **Tracking log box:** shows which animals on the list are not mounted, waiting to be counted, or waiting for review
   (see "Tracking which animals are done").
4. **Inspect images box:** reads file headers without loading pixels and lists each image's detected format, size, pixel calibration, planned tile count, and any problem that would skip it.
5. **Step 1, automated count:** normalizes non-TIFFs to `.tif`, cuts large images into `.tif` tiles, counts each tile, and folds per-tile counts into one row per original image in `output/counts/auto_counts.csv`.
6. **Step 2, review:** review your images in Fiji (see below). Tiled images are reviewed tile by tile (cropped to each tile's core so no cell appears twice across tiles), and the notebook folds tile reviews back into one row per original image.
7. **Step 3, analysis:** run the remaining boxes. Your tables and figures are saved in `output/results`.
8. **Update the tracking log:** run the last box, then share the log (see "Tracking which animals are done").

You can close everything and come back later; nothing is lost. Tiles already counted are skipped on re-run,
and fields already reviewed stay reviewed.

---

## Step 2 in detail: reviewing in Fiji

1. Open Fiji. Choose **Plugins > RGC > Review Counts**.
   (If it is not in the menu, add the update site: see "Before you start", Fiji, step 4.)
2. When asked for a folder, choose the `output` folder inside `rbpms-count`. Type your initials.
3. Each image opens with the counted cells outlined in **magenta** and a **yellow dot** on each one.
   **Cyan** outlines were found but left out as too dim; some of them may be real cells.
   Make it so that **every RGC has exactly one dot**:

| To | Do this |
|---|---|
| add a cell that was missed | click on it |
| remove a dot that is not a cell | **Windows:** hold **Alt** and click the dot. **Mac:** hold **Option** and click the dot |
| move a dot | drag it |
| zoom in / out | press **+** / **-** |
| move around when zoomed in | hold the space bar and drag |
| make the image brighter (display only) | **Image > Adjust > Brightness/Contrast** |

4. Click **Save and next**. **Skip this image** leaves it for later. **Stop reviewing** ends the session.
   Every image is saved as soon as you click Save, so you can stop at any time.

Your corrections are also saved onto the image itself (green dots). Opening a `.tif` from `output/counted` in Fiji
later shows exactly what was counted.

---

## What you get

Everything is in the `output` folder:

| File or folder | What it is |
|---|---|
| `normalized/<retina>/<image>.tif` | single-channel 2D `.tif` normalized from the original image, plus `.json` provenance |
| `tiles/<retina>/<image>/<tile>.tif` | padded `.tif` tiles for images larger than `TILE_SIZE` |
| `counted/<retina>/<tile>.tif` | core-cropped `.tif` with counted cells outlined; open it in Fiji |
| `counted/<retina>/<tile>.jpg` | a picture of the same, for a quick look (`<image>.jpg` shows the full tiled overview) |
| `rois/<retina>/<tile>_rois.csv` | per-cell measurements with both local tile and parent image coordinates |
| `counts/images.csv` | survey of input files: detected format, dimensions, pixel size, problems |
| `counts/plan.json` | tile grid and core/margin plan used for the run |
| `counts/tiles.csv` | per-tile automated counts, core bounds, and core pixel areas |
| `counts/auto_counts.csv` | one row per original image (summed across tiles) |
| `counts/tile_manual_counts.csv` | per-tile review rows saved by Fiji's review tool |
| `counts/manual_counts.csv` | one reviewed row per original image (folded once all tiles are reviewed) |
| `results/counts_per_image.csv` | one row per image: automated count, removed, added, final count, `area_mm2`, `cells_per_mm2` |
| `results/counts_per_eye.csv` | total count for each retina, and the mean per image |
| `results/counts_per_animal.csv` | left eye, right eye and both together for each animal |
| `results/figures/` | figures of the counts per image, per animal, and automated vs reviewed |

The .csv files open in Excel, Numbers or Google Sheets.

**About totals and densities:** a retina total is the sum over that retina's original images, and each image total is the exact sum over its non-overlapping tile cores. `area_mm2` and `cells_per_mm2` in `counts/auto_counts.csv` and `results/counts_per_image.csv` are computed from each image's calibrated pixel size (`um_per_px`) and total core pixel area (`core_px`). If an image lacks valid microscope calibration (including plain 72-dpi TIFFs), those columns remain blank rather than guessing `0.146 mm²`.

The notebook also warns you about folder names it cannot read (no animal number, or no L/R), files that look like
copies (`... (2).czi`), and an eye that appears in two folders.

---

## Tracking which animals are done

The tracking log lives in the `tracking` folder. **It is never uploaded to GitHub**, because the lab repository is public
and the log lists animal numbers. To start, copy `tracking/animals.example.csv` to `tracking/animals.csv`.

| File | Who changes it | What it is |
|---|---|---|
| `tracking/animals.csv` | **you** | the animals to process: animal number, eyes (`L R`), priority (for example `today`), date requested, notes |
| `tracking/STATUS.md` | the notebook | where every retina stands; GitHub shows it as a readable table |
| `tracking/status.csv` | the notebook | the same as a spreadsheet, including retinas that are not on the list |

**To add animals,** open `tracking/animals.csv` in Excel (or Numbers or Google Sheets), add one row per animal, and save
it as CSV. Use the priority to mark what is urgent; in the notebook's Settings, `COUNT_WHICH = "today"` then counts
only the animals marked `today`.

**To update the log,** run the "Tracking log" box near the top of the notebook, or the last box at the bottom.
It looks at the images folder and the results and gives each retina (animal + eye) one of these stages.
The log shows left eyes only while `LOG_EYES = "L"` in the notebook's Settings; set it to `"L R"` to show both eyes.
Folders whose name has no L or R (for example `1003`) are always shown, with eye `?`.

| Stage | Meaning |
|---|---|
| not mounted (no images) | no images of this eye in the images folder yet |
| imaged, not counted | images are there; run step 1 |
| counting | some images counted; run step 1 again |
| counted, review not started | step 1 done; review in Fiji (step 2) |
| reviewing | some images reviewed |
| reviewed, run step 3 | all images reviewed; run step 3 |
| done | reviewed and included in the results |

**To share the log,** keep the tracking folder somewhere everyone can reach, such as the lab's CRSP share, and
point the notebook at it: set the environment variable `RBPMS_TRACKING` to that folder before opening JupyterLab
(or, in the notebook's first box, `import os; os.environ["RBPMS_TRACKING"] = r"<path to shared tracking folder>"`).
Everyone who uses the same folder sees the same log.

Note that the stages describe the images and results on the computer that updated the log.

---

## Changing the settings

The counting settings are in the notebook's Settings box. They were chosen for **20x widefield images at
0.227 micrometres per pixel**. If your images were taken differently (another objective, camera or stain), check the
example image after step 1 before reviewing everything:

- **Most real cells are cyan (left out):** the brightness filter is too strict for these images. Lower `min_contrast`
  (for example to `1.05`), or set it to `1.0` to switch it off.
- **Outlines on empty background:** raise `min_contrast` a little.
- **Cells cut into pieces, or neighbouring cells joined:** change `radius` and `sigma`; ask for help if unsure.
- **Wrong colour channel counted:** change `channel`.

To count images again with new settings, choose a new `OUTPUT_FOLDER` (or delete the `output` folder) and run step 1 again.
Counting again after reviewing means the review has to be done again, so settle the settings first.

---

## Something went wrong?

| Problem | What to do |
|---|---|
| "Could not find Fiji" | In the Settings box, set `FIJI_FOLDER` to where Fiji is, e.g. `"/Applications/Fiji.app"` (Mac) or `r"C:\Users\yourname\Documents\Fiji.app"` (Windows). Run the Settings and Set-up boxes again. |
| Mac: a message that "java" cannot be opened | Open Fiji once with right-click > **Open** (see "Before you start"), then run the box again. If it still appears, go to **System Settings > Privacy & Security** and click **Open Anyway**. |
| "The images folder does not exist" | Check `DATA_FOLDER` in the Settings box. Images must be inside folders, one per retina. |
| "No module named ..." | Run the Set-up box again; it installs what is missing. |
| Plugins > RGC > Review Counts is missing | Add the update site ("Before you start", Fiji, step 4) and restart Fiji. Without internet, run the "install review tool" box in step 2 instead, then quit and restart Fiji. |
| Fiji's updater lists `Review_Counts.groovy` as "locally modified" | It was also installed by the notebook's box. In the updater, click that row, set its action to **Update It** (or **Install**), then **Apply Changes**. |
| Fiji stopped with an error in step 1 | Read the lines above the error. Often it is a damaged image file; move it out of the `data` folder and run again. |
| The notebook seems stuck | Check whether the box shows `[*]` (still running). Large batches take a while: about 1 minute per 40 images. |

---

## Saving your changes to GitHub

Your images, the `output` folder and the tracking log are never uploaded: the project is set up to ignore them.
Only the notebook and scripts are shared, and the lab repository is **public**, so never add images, counts or animal
lists. Before committing, check that GitHub Desktop lists only notebook or script changes. If you change the notebook and want to share it with the lab, open GitHub Desktop, choose **Branch > New branch**,
commit with a short summary starting with `rbpms-count:`, click **Publish branch**, then **Create Pull Request**.
Changes reach everyone after the pull request is reviewed and merged. If you are unsure, ask first.

---

## Publishing a new version of the review tool (update site maintainers)

The review tool is `scripts/review_counts.groovy` in this project. The update site
`https://sites.imagej.net/Gokoffski-Lab/` gives it to everyone's Fiji as `scripts/Plugins/RGC/Review_Counts.groovy`.
Only people with the site's upload account can publish. After changing the script on `main`:

1. Copy the new version into your own Fiji: run the notebook's "install review tool" box (or
   `python scripts/rbpms.py install-review-tool`).
2. In Fiji, choose **Help > Update...**, click **Advanced mode**, and choose **View locally modified files only**
   (the first time ever: **View local-only files**).
3. Select `scripts/Plugins/RGC/Review_Counts.groovy`, right-click it, and choose **Upload to Gokoffski-Lab**.
   Upload only this file.
4. Click **Apply Changes (upload)** and type the upload account's password when asked.
5. Check: choose **View files of the 'Gokoffski-Lab' site**; the file should be listed as up to date.

**One-time setup for a maintainer's Fiji:** in **Help > Update... > Manage Update Sites**, find the site's row and type
`webdav:` followed by the upload user name in its **Host** column, then **Apply and Close**.
The site and upload account were requested on the
[Image.sc Forum update-site thread](https://forum.image.sc/t/requests-for-creating-imagej-update-sites/40051/); password
resets are requested there too. See [imagej.net/update-sites/setup](https://imagej.net/update-sites/setup) for details.

---

## For people who use the terminal

The notebook calls `scripts/rbpms.py`, which can also be run directly:

```bash
python scripts/rbpms.py inspect                        # inspect input formats, sizes, and tile counts
python scripts/rbpms.py count                          # step 1: normalize, tile, count, fold into auto_counts.csv
python scripts/rbpms.py count --data /path/to/images --tile-px 2048 --min-contrast 1.0
python scripts/rbpms.py tile --data /path/to/images    # write padded .tif tiles without counting
python scripts/rbpms.py count --priority today        # only animals marked "today" in tracking/animals.csv
python scripts/rbpms.py install-review-tool            # step 2 set-up
python scripts/rbpms.py status                         # step 2 progress
python scripts/rbpms.py log --data /path/to/images     # update tracking/STATUS.md
python scripts/rbpms.py log --eyes L                   # the same, left eyes only
```

## Tests

Run the automated test suite with fake inputs only (no real lab images):

```bash
python -m unittest discover -s tests -v
```

`test_tiling.py` and `test_ledger.py` run in pure Python without Fiji. `test_pipeline_fiji.py` generates synthetic multi-channel TIFFs and non-TIFF `.ics` images in a temporary directory and runs the full normalize-tile-count-review-fold pipeline in headless Fiji when Fiji is installed (set `RBPMS_TEST_FIJI=1` to fail if Fiji is missing).

```
rbpms_count.ipynb              the notebook (inspect, steps 1, 2 and 3)
scripts/rbpms.py               finds Fiji, surveys inputs, runs counts, folds ledgers
scripts/tiling.py              tile grid geometry, core partition, auto/manual count folding
scripts/count_rgc.groovy       Bio-Formats inspection/normalization and SimpleRGC tile counting
scripts/review_counts.groovy   the review tool installed into Fiji
tests/                         unit, ledger, and synthetic Fiji end-to-end tests
tracking/                      the tracking log (animals.csv, STATUS.md, status.csv)
data/                          your images (not uploaded to GitHub)
output/                        normalized TIFFs, tiles, ROIs, counts, and results (not uploaded)
```
