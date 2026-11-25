# clover-warp

> **Status:** 🧪 experimental · **Owner:** @winstonaluk · **Language:** Python ≥3.10 · **License:** MIT ·
> **Runs on:** analysis PC / HPC3 (`scripts/hpc3_register.slurm`) · **Docs:** [Clover flatmount reconstruction](https://gokoffski-lab.github.io/lab/workflows/clover-warp/)
>
> Imported from a local, never-committed project (2026-11-24). Example dataset names are placeholders (`example`).
> Tests: `pip install -e ".[dev]" && pytest -q`.

Reconstruct retinal clover flatmounts by registering each petal's vasculature
to the **same eye's in vivo angiogram**, then report every counted cell in real
retinal coordinates.

## The idea

A clover flatmount has been cut and flattened, so its geometry no longer
matches the eye it came from. Petals are rotated, radially stretched, and
sometimes torn. Existing tools reconstruct the sphere from the *outline and cut
geometry* alone — [Retistruct](https://github.com/davidcsterratt/retistruct)
morphs a traced outline back onto a sphere, which is elegant but has nothing to
say about where any individual cell originally sat beyond what the outline
implies.

If you have an in vivo fundus photograph or fluorescein angiogram of that eye,
you have something much stronger: a picture of that retina's vascular tree
**intact, uncut and unstretched**. So don't try to match the petals' cut edges
to each other. Register each petal independently to the angiogram, using vessel
bifurcations as correspondences. Two things then fall out at once:

1. **The clover is reassembled.** Every petal now sits in one common frame.
   Reassembly is a consequence of the registration, not a separate step, and
   crucially no error accumulates petal-to-petal the way it does when you chain
   seam matches around the clover.
2. **Every cell gets a real retinal position.** Eccentricity from the disc and
   meridian angle, on the sphere, comparable between animals and between eyes
   of different size.

The angiogram is the reference frame. That is the whole design.

## Status

Early. The manual-landmark path works and is the one to use. The automatic
vessel-matching path runs end to end and recovers synthetic positions to a few
pixels, but has not been validated on real tissue. Nothing here has been
compared against a biological ground truth, because none exists — see
[Validation](#validation).

## Install

```bash
git clone https://github.com/Gokoffski-Lab/clover-warp
cd clover-warp
pip install -e ".[dev]"
cloverwarp selftest          # synthetic round-trip; should print a few px
```

Python ≥ 3.10. Core dependencies are numpy/scipy/scikit-image/networkx/pandas.
Vendor microscope formats (`.lif`, `.czi`) need `pip install -e ".[vendor]"`, or
convert to OME-TIFF first, which is better anyway:

```bash
bfconvert -series 0 flatmount.lif flatmount.ome.tiff
```

## Start here: the manual path

Do this before writing any new code. It needs ~15 minutes per retina and it
produces the result that every automated version must be measured against.

1. Open the FA image and the flatmount in **Fiji → BigWarp** (FA as *fixed*,
   one petal as *moving*).
2. Click matched vessel bifurcations — aim for 15–25 per petal, spread to the
   petal tip, not clustered near the disc.
3. Export landmarks (`File → Export landmarks`) as `L1.csv`, `L2.csv`, …
4. Run it:

```bash
cloverwarp init-config config/example.yaml --dataset example --species rat
# fill in fa_image, centroid_table, fa_disc_xy, fa_rim_radius_px
cloverwarp manual config/example.yaml \
    --landmarks L1=landmarks/L1.csv \
    --landmarks L2=landmarks/L2.csv \
    --landmarks L3=landmarks/L3.csv \
    --landmarks L4=landmarks/L4.csv
```

You get:

| file | what it is |
|---|---|
| `*_cells_retinal.csv` | every cell with `fa_x/y`, `eccentricity_rad/mm`, `meridian_rad`, `quadrant` |
| `*_ring_density.csv` | cells/mm² in concentric eccentricity rings, areas computed on the sphere |
| `*_quadrants.csv` | per-quadrant counts and densities |
| `*_qc.csv` | one row per petal: landmark count, fit and leave-one-out residuals, warp Jacobian, coverage, pass/fail |
| `*_landmarks.csv` | all correspondences, editable and re-runnable |
| `*_config_used.yaml` | the resolved config, so the result is reproducible |

Cell counts come from whatever you already use — Imaris Spots statistics,
`rbpms-count`, a Fiji Results table. `read_centroids` sniffs the column names.
Set `centroid_scale_to_px` to `1/µm_per_px` for an Imaris export, since Imaris
writes microns and the images are indexed in pixels.

## The automatic path

```bash
cloverwarp auto config/example.yaml
```

Same outputs, same QC. The landmark clicking is replaced by:

```
tissue mask → split petals at the relief cuts → vessel segmentation (both
modalities) → skeleton → bifurcation graph rooted at the disc → descriptors →
candidate proposal → RANSAC geometric consensus → TPS on the verified inliers
```

Petals that fail the QC gates are reported with their inlier counts, so the
normal workflow is mixed: automatic for the clean petals, hand-clicked for the
two that tore.

### Why it is built this way

**Graphs, not pixels.** Intensity-based registration cannot work here: an FA
and a confocal isolectin channel share no intensity relationship. What they
share is *topology*. A bifurcation is identifiable across modalities by its
place in the tree — how many branch points lie between it and the disc, how the
daughters split, their calibre ratio — and those survive flattening, fixation
and a change of imaging modality.

**Rotation-invariant descriptors.** Branch angles are measured relative to the
direction back toward the disc, never in image coordinates. A petal is rotated
by an unknown amount when mounted, so absolute angles differ for the *same*
anatomical bifurcation. Getting this wrong made the matcher useless, and it was
not obvious from looking at the output — only from scoring against synthetic
ground truth.

**Descriptors propose, geometry decides.** Descriptors alone cannot
disambiguate the many near-identical bifurcations in a vascular tree, and
geometry alone cannot get started. So stage 1 is permissive (~20–25% of its
proposals are correct) and stage 2 — RANSAC over 4-DOF similarity models —
decides. The inlier count after stage 2 is the number worth reporting.

**The sector prior is not optional.** A tree with N similar primary branches is
rotationally ambiguous. Without a prior, the matcher finds a perfectly
self-consistent consensus one sector over: the fit residual looks *fine* and
the positions are wrong by hundreds of microns. This is the worst kind of
failure, because it is invisible in every statistic except ground-truth error.
A clover removes the ambiguity for free, since the relief cuts tell you roughly
which sector each petal came from. On the synthetic benchmark:

| | median error | p90 |
|---|---|---|
| with sector prior | **4 px** | 31 px |
| without | 309 px | 711 px |

**The disc holds the tree together.** Vesselness filters reliably drop out at
the optic disc, exactly where many large vessels converge and ridge structure
breaks down. Left alone, the "tree" fragments into one island per primary
branch, `depth` and `path_length` become meaningless, and most of the retina
gets discarded by a largest-component filter. So each component is bridged to a
node at the disc, which is anatomically true — every retinal vessel enters
there. Bridged edges are counted in `graph.meta` so QC can report how much
connectivity was assumed rather than observed.

**Projections have domains.** A rat retina extends past 100° from the disc.
Gnomonic and orthographic projections fold or blow up at 90°, so they *cannot*
describe a whole clover; the frame refuses to be built rather than silently
clipping your periphery. Use `azimuthal_equidistant` (default) or
`stereographic`.

**Area correction.** Ring and map densities divide by area **on the sphere**,
not in the projected plane. Without this, peripheral RGC densities — the part
of the retina a clover mount exists to reach — are systematically wrong.

## Validation

There is no biological ground truth. The retina was cut and flattened before
anyone measured anything, so no one knows where a given cell truly sat. The
only defensible accuracy claim comes from synthetic data where the answer is
known by construction:

```bash
cloverwarp selftest --out results/selftest
cloverwarp selftest --no-sector-prior   # see the failure the prior prevents
```

`cloverwarp.synth` builds a vascular tree, projects it to a synthetic FA, cuts
it into petals, flattens each with a *known* warp, and scores the recovered
positions. Report its **median and p90 together**: a matcher that nails three
petals and loses the fourth has a fine median and a terrible p90, which is
exactly the failure clover geometry invites.

Then, on real data, in this order:

1. **Manual landmarks on 3–5 retinas.** This is the reference standard. Its
   leave-one-out residual is the accuracy floor for everything else.
2. **Automatic vs manual on the same retinas.** The automatic path is
   believable only to the extent it reproduces the manual result. Report
   per-petal agreement, not a pooled average.
3. **Re-click reliability.** Have two people landmark the same retina. If
   inter-observer spread exceeds the automatic path's error, stop optimising
   the automatic path.
4. **Biological positive control.** Something with a known spatial signature —
   a localised lesion, a focal injection site, the dorsal-ventral opsin
   gradient. If the pipeline cannot recover a gradient you know is there, the
   coordinates are not yet usable.

Calibrate the QC gates in `config.gates` against step 1 and write the measured
numbers into config. Do not loosen them to make a batch pass.

## QC gates, and what each catches

| field | catches |
|---|---|
| `n_landmarks` | too few correspondences; a TPS will interpolate confidently through nonsense |
| `rmse_px` vs `loo_rmse_px` | a warp memorising its landmarks instead of describing the tissue. With zero smoothing the in-sample RMSE is ~0 by construction and means nothing |
| `min_jacobian` | the warp folded the petal over itself — never real |
| `jacobian_p99` | extreme local stretch; real flattening is ~1.0–1.4× |
| `coverage_frac` | fraction of petal inside the landmark convex hull. TPS *extrapolation* diverges, so cells outside it should be flagged, not reported |

Look at `qc.overlay_figure` for every retina. It catches in one glance the two
things numbers describe poorly: a petal registered into the wrong sector, and a
petal whose landmarks all sit in one corner.

## What this does not do

- **No in vivo ↔ ex vivo cell matching.** Petals are registered to the FA, so
  in vivo and ex vivo measures land in one frame; identifying the *same cell*
  in both is a different and much harder problem.
- **No 3-D / depth registration.** Everything is a 2-D surface problem. Layer
  assignment stays with your confocal analysis.
- **No tear or fold repair.** A petal that folded under itself during mounting
  will fail QC, and should. Re-mount it.
- **No vessel-type classification.** Arteriole/venule labelling would sharpen
  the descriptors considerably and is the most promising unexplored direction.
- **No learned segmentation.** `vessels.segment_learned` is a deliberate
  `NotImplementedError`. Fundus-trained vessel networks transfer poorly to
  rodent FA and not at all to confocal flatmounts. Fine-tune on your own images
  only once Frangi is the *measured* bottleneck.

## Known weak points

Ranked by how likely they are to bite:

1. **Disc localisation.** Everything downstream is eccentricity from the disc.
   The distance-transform estimate is often off by enough to matter. Measure it
   on the vessel convergence point and put it in config.
2. **Rim calibration.** `fa_rim_radius_px` sets the angular scale. Inferring it
   from a tissue-mask percentile is a convenience, not a measurement.
3. **`rim_eccentricity_deg`.** The defaults in `frames.py` are literature
   order-of-magnitude values, not measurements from your colony.
4. **Petal splitting.** Geometric and simple; it will fail on a badly torn
   retina. Check the overlay every time.
5. **Vessel stain.** The whole automatic path depends on a vessel channel good
   enough to skeletonise. If the lab is not already staining vasculature
   (isolectin GS-IB4, collagen IV, CD31) in these flatmounts, add it before
   building anything else here.

## Layout

```
src/cloverwarp/
  frames.py      coordinate frames; sphere <-> plane projections and their domains
  warp.py        similarity / affine / thin-plate spline, with Jacobians
  landmarks.py   BigWarp and native landmark CSVs
  petals.py      tissue mask, disc estimate, clover -> petal split
  vessels.py     Frangi vesselness segmentation (+ learned hook)
  graph.py       skeleton -> rooted bifurcation graph; invariant descriptors
  match.py       descriptor proposal, RANSAC consensus, sector prior
  points.py      centroid transfer, ring / quadrant / map densities
  qc.py          per-petal gates, leave-one-out, overlays
  synth.py       synthetic clovers with ground truth
  pipeline.py    the two entry points
  cli.py         init-config / manual / auto / selftest
tests/           unit tests plus synthetic end-to-end
scripts/         HPC3 batch submission
docs/METHOD.md   assumptions, derivations, failure modes
```

## Roadmap

- [x] Coordinate frames, projections, warps, QC gates
- [x] Manual BigWarp path end to end
- [x] Synthetic validation harness
- [x] Automatic matching that passes the synthetic benchmark
- [ ] Manual-path results on the Weston clovers — **do this next**
- [ ] Automatic vs manual agreement on the same retinas
- [ ] Measured `rim_eccentricity_deg` and disc protocol for the colony
- [ ] Arteriole/venule labelling in the descriptors
- [ ] Multi-retina pooling and group isodensity maps
- [ ] Retistruct interop: export spherical coordinates in its format

## License

MIT.
