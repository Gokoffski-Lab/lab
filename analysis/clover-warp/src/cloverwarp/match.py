"""Match petal bifurcations to FA bifurcations, then verify geometrically.

Two stages, deliberately separated:

1. **Descriptor proposal.** For each petal bifurcation, find the ``k`` FA
   bifurcations with the most similar tree-structural descriptor. This stage
   is permissive and produces many wrong pairs; that is fine and expected.
2. **Geometric consensus.** Find the largest subset of proposals that a
   single smooth transform can explain, by RANSAC over similarity models.
   This is the stage that actually decides correctness.

The order matters. Descriptors alone cannot disambiguate the many
near-identical bifurcations in a vascular tree; geometry alone cannot get
started without candidate pairs. Neither stage is trustworthy on its own, and
the inlier count after stage 2 is the number to report in QC -- a petal with
fewer than ~8 geometric inliers should be sent to manual landmarking rather
than trusted.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .landmarks import LandmarkSet
from .warp import SimilarityTransform, fit, rmse

__all__ = [
    "MatchParams",
    "MatchResult",
    "propose",
    "ransac_similarity",
    "match_petal",
    "sector_mask",
    "refine_nonrigid",
]


def sector_mask(
    fa_xy: np.ndarray,
    disc_xy,
    lo_rad: float,
    hi_rad: float,
    pad_rad: float = 0.35,
) -> np.ndarray:
    """Which FA bifurcations lie in a petal's angular sector about the disc.

    This is the single most valuable prior available, and it is free. A
    vascular tree with N near-identical primary branches is rotationally
    ambiguous: descriptors alone will happily match a petal's bifurcations to
    the structurally-identical branch one sector over, and RANSAC will then
    find a perfectly self-consistent consensus that is simply in the wrong
    place. The resulting error is large, smooth, and looks like a successful
    registration -- the worst kind of failure.

    A clover removes the ambiguity, because the relief cuts tell you roughly
    which sector each petal came from. Pass the petal's sector (from
    :attr:`cloverwarp.petals.PetalSplit.cut_angles`) with a generous ``pad``
    for the rotation introduced by mounting.

    Angles wrap, so a sector spanning 0 is handled correctly.
    """
    fa_xy = np.asarray(fa_xy, dtype=float).reshape(-1, 2)
    disc = np.asarray(disc_xy, dtype=float).reshape(2)
    ang = np.arctan2(fa_xy[:, 1] - disc[1], fa_xy[:, 0] - disc[0]) % (2 * np.pi)
    lo = (lo_rad - pad_rad) % (2 * np.pi)
    hi = (hi_rad + pad_rad) % (2 * np.pi)
    span = (hi_rad + pad_rad) - (lo_rad - pad_rad)
    if span >= 2 * np.pi:
        return np.ones(len(fa_xy), dtype=bool)
    if lo <= hi:
        return (ang >= lo) & (ang <= hi)
    return (ang >= lo) | (ang <= hi)  # wraps through 0


@dataclass
class MatchParams:
    """Knobs for the two matching stages.

    ``feature_weights``
        Per-descriptor-dimension weights, same order as
        :func:`cloverwarp.graph.bifurcation_descriptors`. Radius-derived
        dimensions should be down-weighted when the two modalities have very
        different pixel sizes, because radius in pixels is not scale-free.
    ``k``
        Candidates kept per petal bifurcation.
    ``ransac_threshold_px``
        Inlier distance in FA pixels. Set it from how well you expect a
        *similarity* model to fit a flattened petal -- not from the accuracy
        you want in the end. A petal has real non-rigid stretch, so this has
        to be generous (tens of pixels) or RANSAC will find nothing; the TPS
        fitted afterwards is what delivers the final accuracy.
    ``min_inliers``
        Below this, declare failure rather than return a bad transform.
    """

    feature_weights: tuple[float, ...] = (
        1.5,  # depth
        0.3,  # log radius (pixel-size dependent -- keep low)
        0.8,  # n_branches
        0.8,  # sin a1, relative to the root-ward direction
        0.8,  # cos a1
        0.8,  # sin a2
        0.8,  # cos a2
        0.5,  # log daughter radius ratio
        1.5,  # normalised path length from the disc
        2.5,  # normalised radial distance from the disc
    )
    k: int = 5
    ransac_threshold_px: float = 40.0
    ransac_iterations: int = 2000
    min_inliers: int = 8
    seed: int | None = 0


@dataclass
class MatchResult:
    """Outcome of matching one petal."""

    petal: str
    landmarks: LandmarkSet
    n_proposed: int
    n_inliers: int
    inlier_rmse_px: float
    transform: SimilarityTransform | None
    ok: bool
    reason: str = ""


def propose(
    petal_feats: np.ndarray,
    fa_feats: np.ndarray,
    params: MatchParams | None = None,
    fa_allowed: np.ndarray | None = None,
) -> np.ndarray:
    """Candidate index pairs ``(i_petal, j_fa)``, shape (M, 2).

    Weighted Euclidean distance in descriptor space, z-scored per dimension
    using the pooled spread so that a feature with a large numeric range does
    not dominate purely by units.

    ``fa_allowed`` is an optional boolean mask over FA bifurcations --
    normally from :func:`sector_mask` -- restricting which FA nodes this
    petal may match to. Returned indices are always into the *full* FA
    arrays, so the caller does not have to undo any subsetting.
    """
    params = params or MatchParams()
    if len(petal_feats) == 0 or len(fa_feats) == 0:
        return np.zeros((0, 2), dtype=int)

    if fa_allowed is not None:
        allowed_idx = np.flatnonzero(np.asarray(fa_allowed, dtype=bool))
        if allowed_idx.size == 0:
            return np.zeros((0, 2), dtype=int)
        fa_feats = fa_feats[allowed_idx]
    else:
        allowed_idx = None

    w = np.asarray(params.feature_weights, dtype=float)
    d = petal_feats.shape[1]
    if len(w) != d:
        w = np.resize(w, d)
    pooled = np.vstack([petal_feats, fa_feats])
    scale = pooled.std(axis=0)
    scale[scale < 1e-9] = 1.0
    a = (petal_feats / scale) * w
    b = (fa_feats / scale) * w
    dist = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(-1))
    k = int(min(params.k, dist.shape[1]))
    nn = np.argsort(dist, axis=1)[:, :k]
    if allowed_idx is not None:
        nn = allowed_idx[nn]
    pairs = [(i, int(j)) for i, row in enumerate(nn) for j in row]
    return np.asarray(pairs, dtype=int)


def ransac_similarity(
    src: np.ndarray,
    dst: np.ndarray,
    params: MatchParams | None = None,
) -> tuple[np.ndarray, SimilarityTransform | None]:
    """RANSAC a similarity transform over candidate pairs.

    Returns ``(inlier_mask, transform)``. A similarity (not affine, not TPS)
    is used on purpose: it has only four degrees of freedom, so two random
    pairs determine it and it cannot contort itself to fit a wrong
    correspondence set. Richer models are fitted only *after* the inliers are
    known.
    """
    params = params or MatchParams()
    src = np.asarray(src, dtype=float).reshape(-1, 2)
    dst = np.asarray(dst, dtype=float).reshape(-1, 2)
    n = len(src)
    if n < 2:
        return np.zeros(n, dtype=bool), None

    rng = np.random.default_rng(params.seed)
    best_mask = np.zeros(n, dtype=bool)
    best_err = np.inf
    best_T: SimilarityTransform | None = None
    thr = float(params.ransac_threshold_px)

    for _ in range(int(params.ransac_iterations)):
        idx = rng.choice(n, size=2, replace=False)
        if np.allclose(src[idx[0]], src[idx[1]]) or np.allclose(
            dst[idx[0]], dst[idx[1]]
        ):
            continue
        try:
            T = SimilarityTransform.estimate(src[idx], dst[idx])
        except (ValueError, np.linalg.LinAlgError):
            continue
        if not np.isfinite(T.scale) or T.scale <= 0:
            continue
        resid = np.sqrt(((T(src) - dst) ** 2).sum(1))
        mask = resid < thr
        count = int(mask.sum())
        if count < 2:
            continue
        err = float(resid[mask].mean())
        if count > best_mask.sum() or (count == best_mask.sum() and err < best_err):
            best_mask, best_err, best_T = mask, err, T

    # one refit on the consensus set
    if best_mask.sum() >= 2:
        try:
            T = SimilarityTransform.estimate(src[best_mask], dst[best_mask])
            resid = np.sqrt(((T(src) - dst) ** 2).sum(1))
            refined = resid < thr
            if refined.sum() >= best_mask.sum():
                best_mask, best_T = refined, T
        except (ValueError, np.linalg.LinAlgError):  # pragma: no cover
            pass
    return best_mask, best_T


def match_petal(
    petal: str,
    petal_xy: np.ndarray,
    petal_feats: np.ndarray,
    fa_xy: np.ndarray,
    fa_feats: np.ndarray,
    params: MatchParams | None = None,
    fa_allowed: np.ndarray | None = None,
) -> MatchResult:
    """Full match for one petal: propose, then verify.

    One-to-one is enforced after RANSAC by keeping, for each FA bifurcation,
    only the petal bifurcation with the smallest residual. Without this a
    single well-placed FA node can absorb several petal nodes and the TPS
    fitted downstream will tear.

    Pass ``fa_allowed`` (see :func:`sector_mask`) whenever the petal's rough
    sector is known. Without it, expect rotational mismatches on any retina
    whose primary branches are similar to one another -- which is most of
    them.
    """
    params = params or MatchParams()
    pairs = propose(petal_feats, fa_feats, params, fa_allowed=fa_allowed)
    if len(pairs) == 0:
        empty = LandmarkSet(petal, np.zeros((0, 2)), np.zeros((0, 2)))
        return MatchResult(petal, empty, 0, 0, float("nan"), None, False, "no proposals")

    src = petal_xy[pairs[:, 0]]
    dst = fa_xy[pairs[:, 1]]
    mask, T = ransac_similarity(src, dst, params)

    if T is None or mask.sum() == 0:
        empty = LandmarkSet(petal, np.zeros((0, 2)), np.zeros((0, 2)))
        return MatchResult(
            petal, empty, len(pairs), 0, float("nan"), None, False, "no consensus"
        )

    resid = np.sqrt(((T(src) - dst) ** 2).sum(1))
    keep: dict[int, int] = {}
    for row in np.flatnonzero(mask):
        j = int(pairs[row, 1])
        if j not in keep or resid[row] < resid[keep[j]]:
            keep[j] = int(row)
    rows = np.array(sorted(keep.values()), dtype=int)

    ls = LandmarkSet(
        petal=petal,
        petal_xy=src[rows],
        fa_xy=dst[rows],
        labels=[f"auto{r:04d}" for r in rows],
    )
    n_in = len(rows)
    err = float(np.sqrt((resid[rows] ** 2).mean())) if n_in else float("nan")
    ok = n_in >= params.min_inliers
    return MatchResult(
        petal=petal,
        landmarks=ls,
        n_proposed=len(pairs),
        n_inliers=n_in,
        inlier_rmse_px=err,
        transform=T,
        ok=ok,
        reason="" if ok else f"only {n_in} inliers (need {params.min_inliers})",
    )


def refine_nonrigid(result: MatchResult, model: str = "tps", smoothing: float = 1e-3):
    """Fit the final transform on the verified inliers.

    Returns ``(transform, rmse_px)``. Kept separate from :func:`match_petal`
    so the consensus set can be inspected, hand-edited and re-fitted without
    re-running the search.
    """
    ls = result.landmarks
    T = fit(ls.petal_xy, ls.fa_xy, model=model, smoothing=smoothing)
    return T, rmse(T, ls.petal_xy, ls.fa_xy)
