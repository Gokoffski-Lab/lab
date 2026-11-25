# RBPMS counting (automated RGC counts)

**Owner:** Winston · **Projects:** WET-Rat, WET-Pig, DOD (flatmount RBPMS) ·
**Code:** [`analysis/rbpms-count/`](https://github.com/Gokoffski-Lab/lab/tree/main/analysis/rbpms-count)

Three steps, all from one notebook (`rbpms_count.ipynb`), with no programming needed:

| Step | What happens | Where |
|---|---|---|
| 1. Automated count | Fiji counts cells in every image (Simple RGC method) | notebook |
| 2. Manual review | add missed cells, remove wrong ones | Fiji: **Plugins › RGC › Review Counts** |
| 3. Analysis | tables and figures per image, eye and animal | notebook |

## Install (once)
1. Fiji, plus the lab update site: **Help › Update › Manage Update Sites › Add Unlisted Site**, name `RBPMS-Count`, URL `https://sites.imagej.net/Gokoffski-Lab/`.
2. JupyterLab Desktop (or conda: `conda env create -f environment.yml`).
3. Get the lab repo (Download ZIP or GitHub Desktop) and open the **`analysis/rbpms-count`** folder in JupyterLab.

Full instructions, troubleshooting and update-site publishing: the subproject README.

## Tracking log
The per-animal log is **not** stored in git (the repo is public). Keep it in a shared folder on CRSP and point
the notebook at it with `RBPMS_TRACKING`. Counts and images stay on CRSP too.

## History
Moved from `Gokoffski-Lab/rbpms-count`, code only. That repo stays **private**: its history contains verified counts.
Its unmerged branches (`feature/lif-mosaic-counting`: whole-retina `.lif` mosaics; `autocount-v2`: ML trials;
`fix/java-heap-size`) are still there. Bring them over with a pull request here once they're ready.
