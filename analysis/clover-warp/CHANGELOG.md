# Changelog

## 0.1.0.dev0 (unreleased)

Initial scaffold.

- Coordinate frames with four sphere/plane projections and explicit domain
  checks, so a projection that cannot represent a whole rat retina is refused
  rather than silently clipping the periphery.
- Similarity / affine / thin-plate-spline transforms with Jacobian
  determinants for fold detection.
- Manual path: Fiji BigWarp landmark CSVs -> per-petal TPS -> retinal polar
  coordinates -> ring and quadrant densities with spherical area correction.
- Automatic path: Frangi vesselness -> skeleton -> disc-rooted bifurcation
  graph -> rotation-invariant descriptors -> RANSAC consensus -> TPS.
- Angular sector prior from the clover's relief cuts. Without it the matcher
  mis-sectors petals: median synthetic error 309 px vs 4 px with it.
- Branch-point cluster merging and disc-bridging of fragmented components.
  Vesselness reliably breaks at the disc; before bridging, a largest-component
  filter discarded six of eight primary branches.
- Per-petal QC gates: landmark count, leave-one-out residual, warp Jacobian,
  landmark-hull coverage.
- Synthetic clover generator with matched ground truth, and a `selftest` CLI
  verb that scores recovery error.
- 45 tests covering algebra, invariances, and synthetic end-to-end recovery.

Not yet done: any validation on real tissue.
