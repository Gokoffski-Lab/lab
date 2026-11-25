"""QC: the part that decides whether a registration is usable.

A registration pipeline that cannot tell you when it has failed is worse
than no pipeline, because its failures look like biology. Every function
here answers one question about one petal, and :func:`petal_report` collects
them into a row that can be read at a glance and sorted.

The gates, and why each one exists:

``n_landmarks``
    Too few correspondences and a TPS will interpolate confidently through
    nonsense. Below ~8 verified inliers, send the petal to manual
    landmarking.
``rmse_px`` / ``loo_rmse_px``
    Fit residual, and leave-one-out residual. The gap between them is the
    thing to watch: a small RMSE with a large LOO error means the warp is
    memorising its landmarks, not describing the tissue.
``min_jacobian``
    Negative anywhere means the warp folded the petal over itself. That is
    never real and invalidates every coordinate in that region.
``jacobian_p99 / jacobian_p01``
    Extreme local stretch. Real flattening stretch is maybe 1.0-1.4; a
    factor of 5 is a landmark error.
``coverage_frac``
    Fraction of the petal's area that lies inside the convex hull of its
    landmarks. Outside the hull a TPS extrapolates, and TPS extrapolation
    diverges. Cells out there should be flagged, not reported.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .landmarks import LandmarkSet
from .warp import Transform, fit, rmse

__all__ = ["PetalQC", "leave_one_out_rmse", "coverage_fraction", "petal_report", "gate"]


@dataclass
class PetalQC:
    petal: str
    n_landmarks: int
    rmse_px: float
    loo_rmse_px: float
    min_jacobian: float
    jacobian_p01: float
    jacobian_p99: float
    coverage_frac: float
    passed: bool
    notes: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def leave_one_out_rmse(
    ls: LandmarkSet, model: str = "tps", smoothing: float = 0.0
) -> float:
    """Refit without each landmark in turn and measure error at the held-out one.

    This is the honest accuracy estimate. The in-sample RMSE of a TPS with
    zero smoothing is ~0 by construction and says nothing at all.
    """
    n = len(ls)
    if n < 5:
        return float("nan")
    errs = []
    for i in range(n):
        keep = np.ones(n, dtype=bool)
        keep[i] = False
        try:
            T = fit(ls.petal_xy[keep], ls.fa_xy[keep], model=model, smoothing=smoothing)
        except ValueError:
            continue
        pred = T(ls.petal_xy[i : i + 1])
        errs.append(np.sqrt(((pred - ls.fa_xy[i : i + 1]) ** 2).sum()))
    return float(np.sqrt(np.mean(np.square(errs)))) if errs else float("nan")


def coverage_fraction(ls: LandmarkSet, petal_mask: np.ndarray | None) -> float:
    """Fraction of petal pixels inside the landmark convex hull."""
    if petal_mask is None or len(ls) < 3:
        return float("nan")
    try:
        from matplotlib.path import Path as MplPath
        from scipy.spatial import ConvexHull
    except ImportError:  # pragma: no cover
        return float("nan")
    pts = ls.petal_xy
    if len(np.unique(pts, axis=0)) < 3:
        return float("nan")
    try:
        hull = ConvexHull(pts)
    except Exception:
        return float("nan")
    poly = MplPath(pts[hull.vertices])
    ys, xs = np.nonzero(np.asarray(petal_mask, dtype=bool))
    if xs.size == 0:
        return float("nan")
    if xs.size > 50_000:  # subsample; this is a fraction, not a census
        sel = np.random.default_rng(0).choice(xs.size, 50_000, replace=False)
        xs, ys = xs[sel], ys[sel]
    inside = poly.contains_points(np.column_stack([xs, ys]))
    return float(inside.mean())


def jacobian_stats(T: Transform, petal_mask: np.ndarray | None, ls: LandmarkSet):
    """Jacobian determinant statistics over the petal (or over landmarks)."""
    if petal_mask is not None:
        ys, xs = np.nonzero(np.asarray(petal_mask, dtype=bool))
        if xs.size == 0:
            pts = ls.petal_xy
        else:
            step = max(1, xs.size // 20_000)
            pts = np.column_stack([xs[::step], ys[::step]]).astype(float)
    else:
        pts = ls.petal_xy
    if len(pts) == 0:
        return float("nan"), float("nan"), float("nan")
    j = T.jacobian_determinant(pts)
    j = j[np.isfinite(j)]
    if j.size == 0:
        return float("nan"), float("nan"), float("nan")
    return float(j.min()), float(np.percentile(j, 1)), float(np.percentile(j, 99))


def gate(
    qc: PetalQC,
    min_landmarks: int = 8,
    max_loo_px: float = 25.0,
    max_stretch: float = 3.0,
    min_coverage: float = 0.75,
) -> tuple[bool, str]:
    """Apply the thresholds. Returns ``(passed, reason)``.

    The defaults are starting points, not measured values. Calibrate
    ``max_loo_px`` against the synthetic-clover recovery error
    (:func:`cloverwarp.synth.recovery_error`) for your own imaging, then
    write the calibrated numbers into config and never silently loosen them
    to make a batch pass.
    """
    problems = []
    if qc.n_landmarks < min_landmarks:
        problems.append(f"{qc.n_landmarks} landmarks < {min_landmarks}")
    if np.isfinite(qc.loo_rmse_px) and qc.loo_rmse_px > max_loo_px:
        problems.append(f"LOO rmse {qc.loo_rmse_px:.1f}px > {max_loo_px}")
    if np.isfinite(qc.min_jacobian) and qc.min_jacobian <= 0:
        problems.append("warp folds (negative Jacobian)")
    if np.isfinite(qc.jacobian_p99) and qc.jacobian_p99 > max_stretch:
        problems.append(f"local stretch {qc.jacobian_p99:.1f}x > {max_stretch}x")
    if np.isfinite(qc.coverage_frac) and qc.coverage_frac < min_coverage:
        problems.append(f"only {qc.coverage_frac:.0%} inside landmark hull")
    return (not problems), "; ".join(problems)


def petal_report(
    ls: LandmarkSet,
    T: Transform,
    petal_mask: np.ndarray | None = None,
    model: str = "tps",
    smoothing: float = 0.0,
    **gate_kwargs,
) -> PetalQC:
    """Full QC row for one petal."""
    jmin, j01, j99 = jacobian_stats(T, petal_mask, ls)
    qc = PetalQC(
        petal=ls.petal,
        n_landmarks=len(ls),
        rmse_px=rmse(T, ls.petal_xy, ls.fa_xy),
        loo_rmse_px=leave_one_out_rmse(ls, model=model, smoothing=smoothing),
        min_jacobian=jmin,
        jacobian_p01=j01,
        jacobian_p99=j99,
        coverage_frac=coverage_fraction(ls, petal_mask),
        passed=False,
    )
    qc.passed, qc.notes = gate(qc, **gate_kwargs)
    return qc


def overlay_figure(
    fa_image: np.ndarray,
    landmark_sets,
    transforms: dict,
    out_path,
    title: str = "",
):
    """Save a diagnostic overlay: FA image, landmarks, and per-petal residuals.

    Look at this for every retina. It catches in one glance the two failures
    the numbers describe poorly: a petal registered into the wrong sector
    (rotationally confused by the clover's near-symmetry), and a petal whose
    landmarks all sit in one corner.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if isinstance(landmark_sets, dict):
        landmark_sets = list(landmark_sets.values())
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(np.asarray(fa_image), cmap="gray")
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    for i, ls in enumerate(landmark_sets):
        col = colors[i % 10]
        T = transforms.get(ls.petal)
        ax.scatter(
            ls.fa_xy[:, 0], ls.fa_xy[:, 1], s=18, facecolors="none",
            edgecolors=[col], linewidths=1.2, label=f"petal {ls.petal}",
        )
        if T is not None:
            pred = T(ls.petal_xy)
            for (x0, y0), (x1, y1) in zip(pred, ls.fa_xy, strict=True):
                ax.plot([x0, x1], [y0, y1], color=col, linewidth=0.8, alpha=0.9)
    ax.set_title(title or "petal -> FA registration")
    ax.legend(fontsize=7, loc="lower right", framealpha=0.6)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
