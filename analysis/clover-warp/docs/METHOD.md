# Method notes

What the pipeline assumes, where the numbers come from, and how it fails.
Read this before quoting any coordinate from it.

## 1. Assumptions, and what breaks if each is wrong

| # | Assumption | If it is wrong |
|---|---|---|
| A1 | The retina lies on a sphere of radius `retinal_radius_mm`. | Eccentricities are wrong by a smooth radial factor. Counts and ring *ordering* survive; absolute densities and cross-species comparison do not. |
| A2 | The FA image is a projection of that sphere centred on the optic disc. | If the camera axis is not through the disc, the error is an asymmetric radial bias — larger on one side than the other. Visible as a systematic left/right asymmetry in ring density. |
| A3 | `projection` names the right projection for the camera. | A few percent radially near the disc, much worse at the petal tips. This is why the periphery is the part to distrust. |
| A4 | The vascular tree is topologically unchanged by dissection. | Vessels are not cut *through* by relief cuts in a well-made clover, so this mostly holds. A cut that crosses a major vessel severs the tree and changes `depth` for everything beyond it — which the matcher will quietly absorb into wrong correspondences. |
| A5 | Each petal's sector is roughly known. | The sector prior is what prevents rotational mismatch (see §4). If petals were separated and shuffled before imaging, the prior is unavailable and the automatic path should not be trusted. |
| A6 | Flattening distortion is smooth and modest. | TPS absorbs smooth stretch. A fold or an overlap is not smooth, and produces a negative Jacobian, which the QC gate rejects. |
| A7 | Cell centroids are in the same pixel frame as the flatmount vessel channel. | A scale error (µm vs px) yields plausible-looking coordinates that are wrong by a constant factor. `centroid_scale_to_px` is recorded in the output for exactly this reason. |

## 2. Coordinate frames

Three frames, and the conversions between them.

```
petal pixels  --T_petal-->  FA pixels  --RetinalFrame-->  (eccentricity, meridian)
                                                              |
                                                              v
                                                     3-D points on the sphere (mm)
```

- **petal** — pixels in the confocal flatmount. One frame per petal, because
  each petal was flattened independently. `T_petal` is the fitted warp.
- **FA** — pixels in the in vivo angiogram. The common 2-D frame; this is the
  reference everything registers *into*.
- **retinal** — `eccentricity` (great-circle angle from the disc, radians) and
  `meridian` (angle about the disc, radians, from the FA image +x axis). This
  is the frame in which counts are comparable across animals.

Quadrant indices from `RetinalFrame.quadrant` are **geometric, not
anatomical**. The code cannot know which way up the retina was mounted. Map
0–3 onto dorsal/ventral/nasal/temporal from the orientation marks yourself and
record the mapping with the dataset.

## 3. Calibration — the two numbers that matter most

`RetinalFrame` needs the disc position and the angular scale.

**Disc (`fa_disc_xy`).** Every eccentricity is measured from here, so a disc
error is a bias on every cell. Use the vessel convergence point in the FA.
`petals.disc_from_mask` (the distance-transform maximum) is a convenience for a
first look, not a measurement.

**Scale (`fa_rim_radius_px`).** Calibrated via `RetinalFrame.from_rim`: if the
retinal rim sits `r_rim` pixels from the disc and the rim is at angular
eccentricity `e_rim`, then

```
px_per_unit_radius = r_rim / f(e_rim)
```

where `f` is the projection's forward function. This makes `rim_eccentricity_deg`
a *calibration constant*, not a cosmetic bound — measure it for your colony
rather than trusting the literature default in `frames.py`.

## 4. Why the sector prior is load-bearing

A retinal vascular tree has N primary branches of broadly similar structure. A
bifurcation three branch points out along one primary branch is often
structurally near-identical to the corresponding bifurcation on its neighbour.

So the descriptor stage proposes both. RANSAC then searches for the largest
geometrically consistent subset — and a *whole petal* matched to the adjacent
sector is perfectly consistent, because it is related to the correct answer by
a rotation about the disc, which is exactly the kind of transform the
similarity model is built to find. The consensus is large, the residual is
small, and the answer is wrong by hundreds of microns.

This failure is invisible in every statistic the pipeline can compute without
ground truth. Hence:

1. the sector prior (`match.sector_mask`), using the clover's own cut geometry;
2. the synthetic benchmark, which is the only thing that detects the failure;
3. `qc.overlay_figure`, where a mis-sectored petal is instantly obvious to a
   human eye and nearly invisible to a threshold.

Measured on `cloverwarp selftest`, seed 0: median 4 px with the prior, 309 px
without.

## 5. Descriptor design

Per bifurcation (`graph.DESCRIPTOR_NAMES`):

| feature | invariant to | note |
|---|---|---|
| `depth` | rotation, scale, stretch | branch points to the disc; most discriminative single feature |
| `log_radius_px` | rotation | **not** scale-invariant; weighted low by default |
| `n_branches` | everything | |
| `sin/cos_a1_rel`, `sin/cos_a2_rel` | rotation | angles **relative to the direction back toward the disc** |
| `log_daughter_radius_ratio` | rotation, scale | |
| `path_length_frac` | scale | normalised by the graph's own maximum path |
| `radial_frac` | rotation, scale | normalised eccentricity from the disc |

Absolute image position (x, y) is excluded: including it lets the matcher
confirm its own initial guess. `radial_frac` is included because, unlike x and
y, it is rotation-invariant and genuinely comparable between modalities.
*Angular* position is what the matcher must discover, so it is supplied only as
the coarse sector prior, never as a descriptor.

The relative-angle choice was not a refinement. With absolute angles the
matcher produced zero correct proposals out of 225 on synthetic data — and the
output still looked like a successful registration.

## 6. Transform ladder

| stage | model | DOF | why |
|---|---|---|---|
| consensus | similarity | 4 | two pairs determine it; cannot contort to fit a wrong correspondence |
| final | TPS | 2N+6 | absorbs the real non-rigid radial stretch of flattening |

TPS smoothing (`warp_smoothing`): use `0.0` only for hand-placed, trusted
landmarks. Use a small positive value (`1e-3`–`1e-2`) for automatic
correspondences, where a handful will be wrong. The lambda is scaled internally
by the mean squared landmark spacing, so the same config value behaves the same
on a 512 px and a 20 000 px image.

## 7. Density, and the area correction

Planar density is not retinal density. A ring between eccentricities `e0` and
`e1` has area on the sphere

```
A = 2 pi R^2 (cos e0 - cos e1)
```

while its area in the projected plane is `s^2 f(e) f'(e)` per unit solid angle.
The ratio, `RetinalFrame.area_element_mm2`, is

```
R^2 sin(e) / (s^2 f(e) f'(e))      ->  R^2 / s^2   as e -> 0
```

`points.ring_density` uses the spherical zone area directly;
`points.density_map` applies the per-bin correction. Without this, the far
periphery — the region a clover mount exists in order to reach — reads
systematically wrong.

## 8. Failure modes, ranked

1. **Mis-sectored petal.** Large smooth positional error, small residual.
   Caught only by the sector prior, ground truth, or looking at the overlay.
2. **Disc mislocalised.** Radial bias on everything. Caught by comparing
   eccentricity distributions between fellow eyes.
3. **Fragmented vessel segmentation.** Collapses `depth` and `path_length`.
   Caught by `graph.meta["n_components_raw"]` and `bridged_edges`.
4. **TPS extrapolation.** Cells outside the landmark hull get coordinates that
   diverge. Caught by `coverage_frac`.
5. **Landmarks clustered near the disc.** Good residual, unconstrained
   periphery. Caught by `coverage_frac` and the overlay.
6. **Centroid unit mismatch.** Constant scale error. Caught only by checking
   `centroid_scale_to_px` against the image metadata.
7. **Wrong projection for the camera.** Peripheral radial bias. Caught by a
   known-geometry positive control.

## 9. Reporting

State all of: the number of petals that passed QC and how many were excluded;
the per-petal leave-one-out residual in **microns on the retina**, not pixels;
the synthetic recovery median *and* p90 for the configuration used; whether
landmarks were manual or automatic, per petal; the disc and rim calibration
method; and the quadrant-to-anatomy mapping.

Never report a pooled mean residual across petals. The distribution is
bimodal — petals either register well or fail — and a mean describes neither
mode.
