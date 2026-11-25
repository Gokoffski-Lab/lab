# Optic nerve axon density (axq)

**Owner:** Winston · **Projects:** WET, DOD, GCR (optic nerve CTB after crush) ·
**Code:** [`analysis/axq/`](https://github.com/Gokoffski-Lab/lab/tree/main/analysis/axq)

## What it produces
CTB-labelled axon signal and axon counts at set distances past the crush site (250–2000 µm), along
whole-mounted, cleared optic nerves. Output is one run folder per nerve, and `axq aggregate` combines them into one table.
Successor to AxonQuantifier (Peng et al. 2023).

## Before you start
- `conda env create -f environment.yml` in `analysis/axq/` (napari panel included)
- Raw `.czi` / `.tif` nerve stacks from CRSP, copied to a local working folder (never into the repo)

## Steps
1. `napari` → open the stack → **Plugins › axq quantification › Quantify**.
2. **Suggest**: the nerve is found and straightened, and the Crush / Pre / Background / distance lines are proposed.
3. Check and adjust the lines. If the outline swallows neighbouring tissue, draw a centerline guide.
4. **Run**, then check the counted-axon points layer.

Command-line equivalents and known limitations: see the subproject README.

## QC: how to tell it worked
- The suggested crush band sits on the visible crush. Confirm it by eye on every nerve.
- Dense nerves are undercounted (overlapping axons), so treat counts there as a lower bound.

## Ground truth
Hand annotations made with `fiji/AxonQuantifier_v2.ijm` are scored against the automatic pipeline (`tests/compare_manual.py`).
