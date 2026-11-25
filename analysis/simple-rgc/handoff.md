# Handoff: automated RGC counting (Simple RGC + folder watcher, Windows)

## Context
•	RGCs are labelled in retinal flatmounts and imaged as widefield epifluorescence.
•	The goal is automatic counting whenever a .tif or .lif file lands in a folder on a Windows PC.
•	In an earlier comparison on a sample field, a pretrained StarDist model (2D_versatile_fluo) counted 355 cells and a classic threshold/watershed pipeline counted 419.
o	StarDist separated touching cells better but missed some dim cells.
o	The threshold pipeline merged neighbouring cells and over-split others.
o	Median soma area was about 570 px (diameter about 27 px).

## Current approach: Simple RGC (Cross et al. 2021, JORS 9:15)
•	Source: https://github.com/sonjoonho/SimpleRGC. Update site: https://sites.imagej.net/Sonjoonho/
•	Pipeline: Niblack local threshold → optional axon removal → Gaussian blur → Otsu threshold → watershed → size filter by diameter.
•	The RGC Counter menu command opens dialogs (MessageDialog, GenericDialog), which fail when Fiji runs headless. The workaround calls `simplergc.services.CellSegmentationService.extractCells(ImagePlus, CellDiameterRange, Int radius, Double sigma, Boolean removeAxons)` directly from Groovy.

## Files (attached to the original chat)
•	`simple_rgc_count.groovy`: Fiji script that runs headless.
o	Opens each image with Bio-Formats, including every series of a .lif.
o	Splits out the morphology channel and max-projects Z-stacks.
o	Writes `rgc_counts.csv` (count and density per mm²), `_rois.zip` and `_overlay.png`.
•	`watch_rgc.sh`: Git Bash polling watcher.
o	Uses find and grep against the `.processed.txt` ledger.
o	Checks that file size is stable before processing.
o	Runs `ImageJ-win64.exe --headless --console --run`.
o	Has a `--once` mode for Task Scheduler.
•	`README.md`: setup and test command.
•	`RGC_StarDist_batch.ijm` and `count.py`: the earlier StarDist alternatives.

## Status and open issues
•	The watcher logic was tested with a stub standing in for Fiji. The Groovy script has not been run in real Fiji yet.
•	First test on Windows: run the single-file command in README.md on one .lif file.
•	Possible failure points:
o	Newer Fiji builds use `fiji-windows-x64.exe` instead of `ImageJ-win64.exe`.
o	The `#@ simplergc.services.CellSegmentationService` injection line may not resolve.
•	Parameters (diameter, radius, sigma) still need tuning with RGC Counter's Preview mode, then checking against manual counts.
