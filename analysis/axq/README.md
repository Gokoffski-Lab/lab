# axq: lab image quantification

> **Status:** 🧪 experimental · **Owner:** @winstonaluk · **Language:** Python ≥3.11 (+ napari panel, Fiji macro) ·
> **Runs on:** analysis PC / laptop · **Docs:** [Optic nerve axon density](https://gokoffski-lab.github.io/lab/workflows/axon-density/)
>
> Moved from a local fork of [Axonquantifier/Axonquantifier](https://github.com/Axonquantifier/Axonquantifier) (Peng et al. 2023).
> The upstream macros (`legacy/`) are **not** included, because upstream has no license; get them from the upstream repo.
> Nerve IDs in the notes below are anonymized (nerve A–F). Tests: `pip install -e ".[test]" && pytest -q`.

One interface for the lab's image measurements. The first tool is **axon_density**: CTB-labelled axon regeneration along whole-mounted, cleared optic nerves after crush (successor to AxonQuantifier, Peng et al. 2023). RGC counting and other internal tools plug into the same interface.

## Install
```bash
conda env create -f environment.yml
conda activate axq
```
After editing `environment.yml`, run `conda env update -f environment.yml --prune`.

## Use
**napari (recommended).** Run `napari`, open the nerve stack, then choose Plugins › axq quantification › Quantify.
1. Pick the tool and the image, then click **Suggest**. The nerve is found, straightened along its centerline, and the Crush, Pre, Background and post-crush lines are proposed.
2. Move, delete or draw lines in the annotations layer. Every straight line other than Pre and Crush is measured.
3. Click **Run**. Results go to a run folder. The metrics appear in the panel along with a plot of signal and axon counts against distance, and the counted axons are added as a points layer so you can check each one.

When Suggest goes wrong:
- **The nerve outline swallows neighbouring tissue or a second nerve.** Add a Shapes layer on the raw image, draw a path with a few clicks along the nerve, eye end first. Pick that layer as **centerline guide** and Suggest again.
- **The eye end is on the wrong side.** Tick `flip_direction` and Suggest again.

**Command line**
```bash
axq list                                                        # installed tools and their parameters
axq run axon_density nerve.tif --out runs                       # fully automatic
axq suggest axon_density nerve.tif --out review                 # straightened TIFF + RoiSet.zip to check in Fiji
axq run axon_density review/nerve_straight.tif --roiset review/nerve_straight_RoiSet.zip --out runs
axq run axon_density nerve.tif --out runs --set band_um=30 distances_um=250,500,1000
axq aggregate runs --groups groups.csv -o cohort.csv            # one long table across nerves and tools
```
A hand-straightened TIFF plus a RoiSet.zip from the Fiji v2 macro works as input too, with `--roiset`.

Also available:
- `--hints guide.zip`: a RoiSet holding a Fiji segmented line along the nerve, used as the centerline guide.
- `--um-per-px 0.624`: for TIFFs without calibration. Fiji's Straighten output loses it, and axq warns when it is missing.
- `--set z=auto`: chooses slices per position, for nerves that are not flat in z. The default `z=pre` is the v2 macro rule.

## Run folder (same for every tool)
`runs/<tool>/<image>_<timestamp>/`
- `tables/*.csv`: for axon_density, `lines`, `per_slice`, `curve` and `counts`
- `metrics.json`
- `RoiSet.zip`: the exact annotations used; opens in Fiji
- `overlays.zip`: what the tool found, for checking by eye; for axon_density, one point per counted axon (`Axons_<line>_z<slice>`)
- `params.json`: pass it back with `--params` to repeat the run
- `provenance.json`: axq version, git commit, input SHA-256, pixel size

## Axon counts
Besides signal as % of Pre, axon_density counts the axons crossing every line (`tables/counts.csv`, metrics `axons_<line>`). Counts do not depend on where Pre is drawn, and they are what most crush papers report.

How it counts: on each included slice, the raw image is sampled along the line with a 10 µm band that averages along the axons. Each peak rising more than `peak_k` (8) times the profile's own noise is one axon, and peaks closer than `min_sep_um` (3 µm) merge. `axons_mean_per_slice` is the headline number. `axons_total` sums over slices and can count one axon twice if it spans two slices.

What to expect:
- Synthetic nerves: exact on straight nerves, and within 3 axons per line after automatic straightening of a curved nerve.
- Real nerves (the 7 annotated ones, no manual counts yet):
  - Plausible where axons are sparse. nerve A at 2 mm has 2 counted for the 3 fibres visible.
  - Distal stretches with no visible axons give a floor of 1 to 4 per line.
  - **Dense nerves are undercounted.** Overlapping axons don't dip apart in the profile, so on nerve B the count stays near 10 to 15 per line while more fibres are visible. Single-plane projections make this worse than the z-stack does.
  - Near the crush, counts are a lower bound.
  - Treat counts as relative until manual counts (`counts.csv`, below) calibrate them.
- `section_thickness_um` > 0 adds `sigma_ad`, the Leon et al. (2000) estimate of axons per nerve, πr² × (axons per mm of width) / thickness. It assumes sections of that thickness, so leave it at 0 for whole mounts and projections.

MF_Axon_Count (GigerLab, Finneran; doi:10.5281/zenodo.10650619) was reviewed and not ported. Its object counting uses fixed pixel and section-thickness constants for 14 µm sections, and it merges neighbouring axons.

## Adding a tool (RGC counting, or anything else)
A tool is a class with `name`, a `Params` dataclass, `suggest(img, params)` and `run(img, shapes, params) -> Result` (see `src/axq/core/tool.py`). `run` must be pure: no UI and no file I/O.

Register it under the `axq.tools` entry point, in this repo's `pyproject.toml` or in **any other package's**:
```toml
[project.entry-points."axq.tools"]
rgc_count = "my_lab_tools.rgc:RgcCount"
```
Once installed, it shows up in `axq list`, in `axq run`, and in the napari panel with a parameter form built from its dataclass. Preprocessing (bit depth, scaling, contrast) belongs in `Params`, so it is recorded with every run. `tests/test_cli_and_registry.py` proves this with a throwaway tool.

## Layout
```
src/axq/core/            Image, Shape (+ ImageJ RoiSet I/O), thresholds, run folders, tool registry
src/axq/tools/axon_density/  measure.py (port of the v2 macro), count.py (axon crossings), straighten.py (auto centerline)
src/axq/napari_plugin/   the Quantify panel; holds no analysis
src/axq/cli.py
tests/synth/             synthetic nerves with known regeneration (straight and curved)
tests/golden/            v2 Fiji macro outputs on the synthetic nerve; make_goldens.py regenerates them
fiji/AxonQuantifier_v2.ijm   Fiji macro, kept until axq is validated on real nerves
legacy/                  v1 macro (3Macro_v1.ijm) and the unrelated 2016 DRG explant tool (legacy/drg)
```
The project website lives on the `gh-pages` branch.

## Validation status
Synthetic nerves (automated tests):
- The Python port matches the v2 Fiji macro to within 0.01 percentage points (`z=pre`), and matches the known regeneration within 3 points.
- Curved nerve: crush within 25 µm of truth, and post-crush values within 3 points of the straight nerve, both automatically and from a rough 300 µm-spaced guide.
- A nerve that is not flat in z gives the known values with `z=auto` (per position). The default v2 Pre-line rule undercounts it. On real nerves `z=auto` adds a distal level of 2-10% of unknown source, so it is opt-in.

Real nerves (7 CZIs plus one hand-straightened TIFF; visual QC with `tests/qc_real.py`, no ground truth yet):
- The nerve outline (Otsu on the log mean projection) covers the dim distal nerve. The centerline follows straight, S-shaped and U-shaped nerves without folding.
- Needs a guide: nerves touching other tissue or a second nerve (nerve B, nerve C).
- The crush suggestion still needs a human check. Some nerves have more than one candidate band (nerve D). On a nerve labelled along its whole length (nerve F), the true crush is unclear.
- Open methods question: on nerves with strong tissue autofluorescence (nerve E), the background measured outside the nerve leaves tissue signal counted as axons.
- **Before relying on numbers**, compare against hand-annotated v2 runs (RoiSet.zip) on a few nerves.

## Annotating nerves for validation
Hand annotations made with the v2 macro are the ground truth that the automatic pipeline is scored against. For each nerve, make a folder `data/annotations/<nerve>`, named so the raw file starts with it (`ON_000` for `data/ON_000_YYMMDD.czi`).

1. In Fiji, open the raw `.czi` and straighten it as usual: Segmented Line, then Edit › Selection › Straighten, processing the whole stack.
2. Save the result as `straightened.tif` in the nerve's folder. Fiji's Straighten drops the pixel size, so set it first (Image › Properties, 0.624 µm for these scans), or put a file `um_per_px.txt` containing `0.624` next to it.
3. Run `fiji/AxonQuantifier_v2.ijm` on it. Draw Pre, Crush and Background where you judge them to be, and fix the generated post-crush lines. Copy `RoiSet.zip` from the macro's output folder into the nerve's folder.
4. Optional but most valuable: `counts.csv` with columns `distance_um,count`, holding your manual axon counts at each distance (as in Peng et al. 2023). Only counts can show which threshold and slice rule are right.

Then run:
```bash
python tests/compare_manual.py data/annotations --raw data --out compare
```
It reports four things for each nerve and distance:
- the crush error: automatic suggestion on your straightened image minus your Crush line, in µm
- % of Pre with your lines (v2 rule, and per-position `z=auto`)
- % of Pre from the fully automatic run on the raw file
- axons crossing your lines, and crossing the automatic lines on the raw file
- correlation of each of these with your counts, when given

## Tests
```bash
python -m pytest -q
```
