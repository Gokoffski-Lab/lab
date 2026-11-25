"""Point-set transforms: similarity, affine, and thin-plate spline.

All transforms map 2-D points (N, 2) in ``(x, y)`` order from a *source*
frame to a *target* frame. Fit with :func:`fit`, apply with ``T(points)``,
and inspect local area change with ``T.jacobian_determinant(points)``.

A petal that has been flattened from a sphere is stretched non-uniformly,
so the only transform family that can absorb that is non-rigid (TPS here).
Similarity and affine are kept because they are the right *initialisation*
and because comparing residuals across the three is the cheapest test of
whether a petal's correspondences are trustworthy at all.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "Transform",
    "SimilarityTransform",
    "AffineTransform",
    "ThinPlateSpline",
    "fit",
    "rmse",
    "MODELS",
]


def _as_points(a) -> np.ndarray:
    arr = np.asarray(a, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError(f"expected an (N, 2) array of (x, y) points, got {arr.shape}")
    return arr


class Transform:
    """Base class. Subclasses implement :meth:`__call__`."""

    #: minimum number of correspondences needed to fit
    min_points: int = 1

    def __call__(self, points: np.ndarray) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def jacobian_determinant(self, points: np.ndarray, eps: float = 1.0) -> np.ndarray:
        """Local area scale factor at each point, by central differences.

        ``eps`` is in source-frame units (pixels by default). Values far from
        1.0 mean the warp is locally stretching or folding the tissue; a
        *negative* value means the warp has folded over itself, which is
        never anatomically real and should fail QC.
        """
        p = _as_points(points)
        dx = np.array([[eps, 0.0]])
        dy = np.array([[0.0, eps]])
        fx = (self(p + dx) - self(p - dx)) / (2 * eps)
        fy = (self(p + dy) - self(p - dy)) / (2 * eps)
        return fx[:, 0] * fy[:, 1] - fx[:, 1] * fy[:, 0]


@dataclass
class SimilarityTransform(Transform):
    """Rotation, isotropic scale, translation. 2 points minimum."""

    scale: float = 1.0
    rotation: float = 0.0
    translation: np.ndarray = field(default_factory=lambda: np.zeros(2))
    min_points: int = 2

    def __call__(self, points: np.ndarray) -> np.ndarray:
        p = _as_points(points)
        c, s = np.cos(self.rotation), np.sin(self.rotation)
        R = np.array([[c, -s], [s, c]])
        return self.scale * (p @ R.T) + self.translation

    @classmethod
    def estimate(cls, src: np.ndarray, dst: np.ndarray) -> SimilarityTransform:
        src, dst = _as_points(src), _as_points(dst)
        if len(src) < 2:
            raise ValueError("similarity needs >= 2 correspondences")
        mu_s, mu_d = src.mean(0), dst.mean(0)
        a, b = src - mu_s, dst - mu_d
        # Umeyama / Kabsch with isotropic scale
        H = b.T @ a
        U, S, Vt = np.linalg.svd(H)
        d = np.sign(np.linalg.det(U @ Vt))
        D = np.diag([1.0, d])
        R = U @ D @ Vt
        var_s = (a**2).sum()
        scale = (S * np.array([1.0, d])).sum() / var_s if var_s > 0 else 1.0
        rot = float(np.arctan2(R[1, 0], R[0, 0]))
        return cls(
            scale=float(scale),
            rotation=rot,
            translation=mu_d - scale * (mu_s @ R.T),
        )


@dataclass
class AffineTransform(Transform):
    """Full 2x3 affine. 3 points minimum."""

    matrix: np.ndarray = field(default_factory=lambda: np.eye(3))
    min_points: int = 3

    def __call__(self, points: np.ndarray) -> np.ndarray:
        p = _as_points(points)
        h = np.hstack([p, np.ones((len(p), 1))])
        return (h @ self.matrix.T)[:, :2]

    @classmethod
    def estimate(cls, src: np.ndarray, dst: np.ndarray) -> AffineTransform:
        src, dst = _as_points(src), _as_points(dst)
        if len(src) < 3:
            raise ValueError("affine needs >= 3 correspondences")
        h = np.hstack([src, np.ones((len(src), 1))])
        sol, *_ = np.linalg.lstsq(h, dst, rcond=None)
        M = np.eye(3)
        M[:2, :] = sol.T
        return cls(matrix=M)


def _tps_kernel(r2: np.ndarray) -> np.ndarray:
    """U(r) = r^2 log(r), written in terms of r^2 to avoid a sqrt."""
    out = np.zeros_like(r2)
    nz = r2 > 0
    out[nz] = 0.5 * r2[nz] * np.log(r2[nz])
    return out


@dataclass
class ThinPlateSpline(Transform):
    """Thin-plate spline with optional regularisation.

    ``smoothing`` (lambda) trades exactness at the control points against
    bending energy. Use 0.0 only when the landmarks are hand-placed and
    trusted; use a small positive value when they come from automated
    vessel matching, where a handful will be wrong.
    """

    control: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    weights: np.ndarray = field(default_factory=lambda: np.zeros((0, 2)))
    affine: np.ndarray = field(default_factory=lambda: np.zeros((3, 2)))
    smoothing: float = 0.0
    min_points: int = 3

    def __call__(self, points: np.ndarray) -> np.ndarray:
        p = _as_points(points)
        if len(self.control) == 0:
            return p.copy()
        d2 = ((p[:, None, :] - self.control[None, :, :]) ** 2).sum(-1)
        K = _tps_kernel(d2)
        lin = np.hstack([np.ones((len(p), 1)), p])
        return K @ self.weights + lin @ self.affine

    @classmethod
    def estimate(
        cls, src: np.ndarray, dst: np.ndarray, smoothing: float = 0.0
    ) -> ThinPlateSpline:
        src, dst = _as_points(src), _as_points(dst)
        n = len(src)
        if n < 3:
            raise ValueError("TPS needs >= 3 correspondences")
        d2 = ((src[:, None, :] - src[None, :, :]) ** 2).sum(-1)
        K = _tps_kernel(d2)
        if smoothing > 0:
            # scale lambda by the mean squared landmark spacing so the same
            # config value behaves the same on a 512 px and a 20000 px image
            K = K + smoothing * d2[d2 > 0].mean() * np.eye(n)
        P = np.hstack([np.ones((n, 1)), src])
        L = np.zeros((n + 3, n + 3))
        L[:n, :n] = K
        L[:n, n:] = P
        L[n:, :n] = P.T
        rhs = np.zeros((n + 3, 2))
        rhs[:n] = dst
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sol, *_ = np.linalg.lstsq(L, rhs, rcond=None)
        return cls(
            control=src,
            weights=sol[:n],
            affine=sol[n:],
            smoothing=smoothing,
        )


MODELS = {
    "similarity": SimilarityTransform,
    "affine": AffineTransform,
    "tps": ThinPlateSpline,
}


def fit(
    src: np.ndarray,
    dst: np.ndarray,
    model: str = "tps",
    smoothing: float = 0.0,
) -> Transform:
    """Fit ``model`` mapping ``src`` -> ``dst``.

    Falls back to the richest model the correspondence count supports, so a
    petal with only two usable bifurcations still produces *something* and a
    loud warning rather than an exception mid-batch.
    """
    src, dst = _as_points(src), _as_points(dst)
    if len(src) != len(dst):
        raise ValueError("src and dst must have the same number of points")
    order = ["tps", "affine", "similarity"]
    if model not in MODELS:
        raise ValueError(f"unknown model {model!r}; choose from {sorted(MODELS)}")
    candidates = order[order.index(model) :] if model in order else [model]
    for name in candidates:
        cls = MODELS[name]
        if len(src) >= cls.min_points:
            if name != model:
                warnings.warn(
                    f"only {len(src)} correspondences: falling back from "
                    f"{model!r} to {name!r}",
                    stacklevel=2,
                )
            if name == "tps":
                return cls.estimate(src, dst, smoothing=smoothing)
            return cls.estimate(src, dst)
    raise ValueError(f"{len(src)} correspondences is not enough for any model")


def rmse(transform: Transform, src: np.ndarray, dst: np.ndarray) -> float:
    """Root-mean-square residual at the correspondences, in target units."""
    pred = transform(_as_points(src))
    return float(np.sqrt(((pred - _as_points(dst)) ** 2).sum(1).mean()))
