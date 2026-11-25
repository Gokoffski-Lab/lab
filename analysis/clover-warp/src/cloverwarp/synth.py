"""Synthetic clovers: the only ground truth this pipeline can ever have.

There is no way to know the true retinal position of a cell in a real
flatmount -- the retina was cut and flattened before anyone measured
anything. So correctness has to be established on data where the answer is
known by construction:

1. generate (or take) an intact vascular tree on a sphere;
2. project it to make a synthetic "FA" image;
3. cut it into petals and flatten each one with a *known* warp, adding the
   stretch, rotation and tear that real flattening introduces;
4. run the pipeline;
5. compare the recovered retinal coordinates to the ones you started from.

The number that comes out of step 5 -- median positional error in microns on
the retina -- is the only defensible accuracy claim this repo can make. Run
it before believing any result on real tissue, and re-run it whenever the
matcher changes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["SynthConfig", "SynthClover", "make_tree", "make_clover", "render"]


@dataclass
class SynthConfig:
    """Parameters of a synthetic retina.

    Defaults produce a rat-scale four-petal clover at a plausible FA
    resolution. Push ``stretch`` and ``tear_px`` up to find where the matcher
    breaks -- that boundary, not the best case, is the useful result.
    """

    size_px: int = 1024
    n_petals: int = 4
    n_primary: int = 8
    branch_depth: int = 5
    rim_radius_px: float = 440.0
    #: per-petal radial stretch applied during "flattening", as a fraction
    stretch: float = 0.12
    #: per-petal rotation about the disc, radians, drawn uniformly
    rotation: float = 0.10
    #: random translation of each petal, pixels
    tear_px: float = 6.0
    vessel_width_px: float = 3.0
    seed: int = 0


@dataclass
class SynthClover:
    """A synthetic dataset with its own answer key.

    ``fa_points`` and ``petal_points`` are matched row for row: row *i* of
    ``petal_points`` is the same anatomical point as row *i* of
    ``fa_points``, which is what makes error measurement possible.
    ``petal_id`` says which petal each row belongs to.
    """

    fa_image: np.ndarray
    petal_image: np.ndarray
    fa_points: np.ndarray
    petal_points: np.ndarray
    petal_id: np.ndarray
    disc_xy: np.ndarray
    config: SynthConfig

    def truth_for(self, petal: str | int) -> tuple[np.ndarray, np.ndarray]:
        m = self.petal_id == int(petal)
        return self.petal_points[m], self.fa_points[m]


def make_tree(cfg: SynthConfig) -> tuple[np.ndarray, np.ndarray]:
    """Build a branching tree radiating from the disc.

    Returns ``(segments, nodes)``: segments is ``(M, 4)`` as
    ``x0, y0, x1, y1``; nodes is ``(N, 2)`` of branch points. The tree is
    crude -- recursive bifurcation with jittered angles -- but it has the one
    property that matters for testing the matcher: a distinctive, non-uniform
    branch topology.
    """
    rng = np.random.default_rng(cfg.seed)
    c = cfg.size_px / 2.0
    disc = np.array([c, c])
    segs, nodes = [], [disc.copy()]

    def grow(origin, angle, length, depth):
        if depth <= 0 or length < 6:
            return
        end = origin + length * np.array([np.cos(angle), np.sin(angle)])
        if np.hypot(*(end - disc)) > cfg.rim_radius_px:
            return
        segs.append([origin[0], origin[1], end[0], end[1]])
        nodes.append(end.copy())
        spread = rng.uniform(0.25, 0.6)
        split = rng.uniform(0.35, 0.65)
        grow(end, angle - spread * split, length * rng.uniform(0.6, 0.8), depth - 1)
        grow(end, angle + spread * (1 - split), length * rng.uniform(0.6, 0.8), depth - 1)

    base = cfg.rim_radius_px / (cfg.branch_depth * 0.55)
    for i in range(cfg.n_primary):
        a = 2 * np.pi * i / cfg.n_primary + rng.uniform(-0.12, 0.12)
        grow(disc, a, base * rng.uniform(0.9, 1.1), cfg.branch_depth)

    return np.asarray(segs, dtype=float), np.asarray(nodes, dtype=float)


def _petal_warp(pts, disc, petal_idx, cfg, rng):
    """Apply a known, invertible-ish flattening distortion to one petal."""
    v = pts - disc
    r = np.hypot(v[:, 0], v[:, 1])
    a = np.arctan2(v[:, 1], v[:, 0])
    # radial stretch that grows toward the tip: this is the dominant real
    # distortion, since flattening a spherical cap stretches the periphery
    r2 = r * (1.0 + cfg.stretch * (r / max(cfg.rim_radius_px, 1.0)))
    a2 = a + rng.uniform(-cfg.rotation, cfg.rotation)
    out = disc + np.column_stack([r2 * np.cos(a2), r2 * np.sin(a2)])
    out = out + rng.uniform(-cfg.tear_px, cfg.tear_px, size=2)
    return out


def render(segments: np.ndarray, size_px: int, width_px: float = 3.0) -> np.ndarray:
    """Rasterise line segments into a float image in [0, 1]."""
    from skimage.draw import line_aa
    from skimage.filters import gaussian

    img = np.zeros((size_px, size_px), dtype=float)
    for x0, y0, x1, y1 in segments:
        rr, cc, val = line_aa(
            int(round(y0)), int(round(x0)), int(round(y1)), int(round(x1))
        )
        keep = (rr >= 0) & (rr < size_px) & (cc >= 0) & (cc < size_px)
        img[rr[keep], cc[keep]] = np.maximum(img[rr[keep], cc[keep]], val[keep])
    if width_px > 1:
        img = gaussian(img, sigma=width_px / 3.0, preserve_range=True)
        m = img.max()
        if m > 0:
            img = img / m
    return img


def make_clover(cfg: SynthConfig | None = None) -> SynthClover:
    """Generate a matched FA image / clover-flatmount image pair."""
    cfg = cfg or SynthConfig()
    segs, nodes = make_tree(cfg)
    disc = np.array([cfg.size_px / 2.0, cfg.size_px / 2.0])

    fa = render(segs, cfg.size_px, cfg.vessel_width_px)

    # assign every segment and node to a petal by angle about the disc
    def petal_of(pts):
        a = np.arctan2(pts[:, 1] - disc[1], pts[:, 0] - disc[0]) % (2 * np.pi)
        return (a / (2 * np.pi / cfg.n_petals)).astype(int) % cfg.n_petals

    mid = np.column_stack([(segs[:, 0] + segs[:, 2]) / 2, (segs[:, 1] + segs[:, 3]) / 2])
    seg_petal = petal_of(mid)
    node_petal = petal_of(nodes)

    warped_segs = np.empty_like(segs)
    truth_petal, truth_fa, truth_id = [], [], []
    for p in range(cfg.n_petals):
        sub_rng = np.random.default_rng(cfg.seed + 100 + p)
        m = seg_petal == p
        if m.any():
            a = _petal_warp(segs[m][:, :2], disc, p, cfg, sub_rng)
            # reuse the same rng draw for both endpoints by re-seeding
            sub_rng = np.random.default_rng(cfg.seed + 100 + p)
            b = _petal_warp(segs[m][:, 2:], disc, p, cfg, sub_rng)
            warped_segs[m] = np.hstack([a, b])
        nm = node_petal == p
        if nm.any():
            sub_rng = np.random.default_rng(cfg.seed + 100 + p)
            wn = _petal_warp(nodes[nm], disc, p, cfg, sub_rng)
            truth_petal.append(wn)
            truth_fa.append(nodes[nm])
            truth_id.append(np.full(nm.sum(), p))

    petal_img = render(warped_segs, cfg.size_px, cfg.vessel_width_px)

    return SynthClover(
        fa_image=fa,
        petal_image=petal_img,
        fa_points=np.vstack(truth_fa) if truth_fa else np.zeros((0, 2)),
        petal_points=np.vstack(truth_petal) if truth_petal else np.zeros((0, 2)),
        petal_id=np.concatenate(truth_id) if truth_id else np.zeros(0, dtype=int),
        disc_xy=disc,
        config=cfg,
    )


def recovery_error(
    clover: SynthClover,
    transforms: dict,
    px_per_mm: float | None = None,
) -> dict:
    """Error of recovered positions against the answer key.

    Returns median / 90th-percentile / max error, in pixels and -- if
    ``px_per_mm`` is given -- in microns on the retina. Report the median and
    the 90th percentile together: a matcher that is excellent on three petals
    and lost on the fourth has a fine median and a terrible p90, and that is
    exactly the failure the clover geometry invites.
    """
    errs, per_petal = [], {}
    for p in sorted(set(int(i) for i in clover.petal_id)):
        T = transforms.get(str(p)) or transforms.get(p)
        src, dst = clover.truth_for(p)
        if T is None or len(src) == 0:
            per_petal[p] = float("nan")
            continue
        e = np.sqrt(((T(src) - dst) ** 2).sum(1))
        per_petal[p] = float(np.median(e))
        errs.append(e)
    if not errs:
        return {"median_px": float("nan"), "p90_px": float("nan"), "per_petal": per_petal}
    all_e = np.concatenate(errs)
    out = {
        "n_points": int(all_e.size),
        "median_px": float(np.median(all_e)),
        "p90_px": float(np.percentile(all_e, 90)),
        "max_px": float(all_e.max()),
        "per_petal_median_px": per_petal,
    }
    if px_per_mm:
        out["median_um"] = out["median_px"] / px_per_mm * 1000.0
        out["p90_um"] = out["p90_px"] / px_per_mm * 1000.0
    return out
