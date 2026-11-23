# Sholl analysis of RGC dendrites (Fiji / SNT)

**Owner:** Winston · **Projects:** GCR (Glaucoma) · **Code:** `analysis/sholl/` (pending import)

## Approach (current)
- 3D Sholl, step size 0 (continuous). Trace channel C=2 (RFP, 0-indexed Imaris channel).
- SNT auto-trace, seeded from somata. Somata are segmented with Cellpose 3D and imported into SNT as a
  labels image. Dendrites, not somata, are the region of interest.
- Ground truth: manual traces on preprocessed, 3×3×3-binned images. The public Dryad mole-rat RGC data
  (Imaris filament traces) is a stand-in ground truth for tuning preprocessing.
- Folder layout: `dendritic-trees/{images,seeds,traces}`.

!!! note "TODO"
    Commit the preprocessing macro / scripts and the parameter-sweep code, then add the run steps here.
