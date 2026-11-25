"""Find the tissue, split the clover into petals, locate the disc corner.

A clover flatmount is one connected sheet of tissue with relief cuts that do
not quite reach the centre, so the petals stay joined at the optic disc. That
has a useful consequence and an awkward one:

* useful -- the point where all petals meet *is* the optic disc, giving one
  free, unambiguous landmark per petal;
* awkward -- the petals are not separate connected components, so splitting
  them needs the cut geometry, not just ``label()``.

The approach here is geometric and intentionally simple: find the tissue
mask, find its centre (the disc), and cut along the angular minima of the
radial tissue extent, which is where the relief cuts are. It will fail on a
badly torn retina, so :func:`split_petals` reports what it did and the
pipeline writes an overlay for every retina. Check the overlays. Treat this
module as assistive, not authoritative -- a wrong petal split is cheap to fix
by hand and expensive to discover later.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi
from skimage import filters, measure, morphology

from ._compat import binary_closing, remove_small_objects

__all__ = ["TissueMask", "PetalSplit", "tissue_mask", "disc_from_mask", "split_petals"]


@dataclass
class TissueMask:
    mask: np.ndarray
    area_px: int
    n_components: int


def tissue_mask(
    image: np.ndarray,
    smooth_px: float = 8.0,
    min_frac: float = 0.02,
    close_px: int = 15,
) -> TissueMask:
    """Segment tissue from background on any bright-tissue channel.

    Use a channel that fills the whole retina: a nuclear counterstain, or the
    sum of all channels. Do *not* use the RGC channel -- RBPMS labels nothing
    outside the ganglion cell layer and the mask will be patchy in exactly
    the damaged regions you care about.
    """
    img = np.asarray(image, dtype=float)
    if img.ndim == 3:
        img = img.mean(axis=-1)
    if smooth_px > 0:
        img = filters.gaussian(img, sigma=smooth_px, preserve_range=True)
    thr = filters.threshold_otsu(img)
    mask = img > thr
    if close_px > 0:
        mask = binary_closing(mask, morphology.disk(close_px))
    mask = ndi.binary_fill_holes(mask)
    min_px = int(min_frac * mask.size)
    if min_px > 0:
        mask = remove_small_objects(mask, min_px)
    lbl, n = ndi.label(mask)
    if n > 1:  # keep the largest piece, but say so
        sizes = ndi.sum(mask, lbl, range(1, n + 1))
        mask = lbl == (int(np.argmax(sizes)) + 1)
    return TissueMask(mask, int(mask.sum()), int(n))


def disc_from_mask(mask: np.ndarray) -> np.ndarray:
    """Estimate the optic disc as the point deepest inside the tissue.

    The maximum of the distance transform sits where the petals converge,
    because that is the only place far from a background edge in every
    direction. Returns ``(x, y)``.

    This is an estimate. If the flatmount has a visible disc -- the vessel
    convergence point in the vessel channel, or the bright CTB-filled stump
    -- prefer that, and pass it in explicitly. A disc error propagates into
    every eccentricity you report.
    """
    mask = np.asarray(mask, dtype=bool)
    if not mask.any():
        raise ValueError("empty tissue mask")
    dist = ndi.distance_transform_edt(mask)
    r, c = np.unravel_index(int(np.argmax(dist)), dist.shape)
    return np.array([float(c), float(r)])


@dataclass
class PetalSplit:
    """Result of splitting a clover.

    ``labels`` is an int image, 0 = background, 1..n = petals.
    ``cut_angles`` are the angles (radians, FA/image +x axis) of the relief
    cuts that were used. ``radial_profile`` is kept so a QC plot can show
    whether the minima were convincing or marginal.
    """

    labels: np.ndarray
    disc_xy: np.ndarray
    cut_angles: np.ndarray
    radial_profile: np.ndarray
    n_petals: int


def split_petals(
    mask: np.ndarray,
    disc_xy=None,
    n_petals: int | None = 4,
    n_angles: int = 720,
    smooth_bins: int = 9,
) -> PetalSplit:
    """Split a clover tissue mask into petals by angular sector.

    ``n_petals=None`` lets the number be inferred from the number of clear
    minima in the radial extent profile, which is worth using once you trust
    the profile; pass an explicit count while validating. Eight-petal and
    five-petal mounts are handled the same way.
    """
    mask = np.asarray(mask, dtype=bool)
    disc = (
        disc_from_mask(mask) if disc_xy is None else np.asarray(disc_xy, dtype=float)
    )

    ys, xs = np.nonzero(mask)
    dx, dy = xs - disc[0], ys - disc[1]
    ang = np.arctan2(dy, dx) % (2 * np.pi)
    rad = np.hypot(dx, dy)

    bins = np.linspace(0, 2 * np.pi, n_angles + 1)
    which = np.clip(np.digitize(ang, bins) - 1, 0, n_angles - 1)
    profile = np.zeros(n_angles)
    np.maximum.at(profile, which, rad)

    # circular smoothing, so the wrap-around is not a false minimum
    if smooth_bins > 1:
        k = np.ones(smooth_bins) / smooth_bins
        profile = np.convolve(np.r_[profile, profile, profile], k, mode="same")[
            n_angles : 2 * n_angles
        ]

    centres = 0.5 * (bins[:-1] + bins[1:])
    if n_petals is None:
        inv = profile.max() - profile
        from scipy.signal import find_peaks

        peaks, _ = find_peaks(
            np.r_[inv, inv], distance=n_angles // 12, prominence=0.1 * inv.ptp()
        )
        peaks = sorted({int(p % n_angles) for p in peaks})
        cut_idx = np.asarray(peaks, dtype=int)
        n_found = max(len(cut_idx), 1)
    else:
        # the deepest minimum anchors the phase, the rest are evenly spaced;
        # a clover is cut by hand but the cuts are near-symmetric by intent
        step = n_angles // n_petals
        scores = np.array(
            [profile[(np.arange(n_petals) * step + s) % n_angles].sum() for s in range(step)]
        )
        phase = int(np.argmin(scores))
        cut_idx = (np.arange(n_petals) * step + phase) % n_angles
        n_found = n_petals

    cut_angles = np.sort(centres[cut_idx])
    sector = np.searchsorted(cut_angles, ang, side="right") % max(len(cut_angles), 1)
    labels = np.zeros(mask.shape, dtype=np.int32)
    labels[ys, xs] = sector + 1

    # a sector that caught only a sliver is not a petal; fold it into its
    # larger neighbour rather than emitting a degenerate petal
    for lab in range(1, int(labels.max()) + 1):
        if (labels == lab).sum() < 0.01 * mask.sum():
            labels[labels == lab] = 0

    present = [int(v) for v in np.unique(labels) if v > 0]
    remap = {old: new for new, old in enumerate(present, start=1)}
    out = np.zeros_like(labels)
    for old, new in remap.items():
        out[labels == old] = new

    return PetalSplit(
        labels=out,
        disc_xy=disc,
        cut_angles=cut_angles,
        radial_profile=profile,
        n_petals=len(present) or n_found,
    )


def petal_regions(split: PetalSplit):
    """Per-petal region properties, for cropping and for QC tables."""
    return measure.regionprops(split.labels)
