"""Per-slice background removal shared by all tools."""

from typing import Literal

import numpy as np
from skimage import filters
from skimage.draw import polygon as draw_polygon

from .annotations import Shape

Method = Literal["background", "auto", "manual"]
Below = Literal["subtract", "hard"]

AUTO_METHODS = {
    "triangle": filters.threshold_triangle,
    "otsu": filters.threshold_otsu,
    "li": filters.threshold_li,
    "yen": filters.threshold_yen,
    "mean": filters.threshold_mean,
}


def shape_mask(shape: Shape, hw: tuple[int, int]) -> np.ndarray:
    rr, cc = draw_polygon(shape.xy[:, 1], shape.xy[:, 0], shape=hw)
    mask = np.zeros(hw, bool)
    mask[rr, cc] = True
    return mask


def slice_thresholds(
    stack: np.ndarray,
    method: Method,
    background: Shape | None = None,
    k: float = 2.0,
    auto_method: str = "triangle",
    manual: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (threshold, bg_mean, bg_sd) per slice."""
    n = stack.shape[0]
    bg_mean = np.zeros(n)
    bg_sd = np.zeros(n)
    if background is not None:
        m = shape_mask(background, stack.shape[1:])
        vals = stack[:, m]
        bg_mean = vals.mean(axis=1)
        bg_sd = vals.std(axis=1, ddof=1)
    if method == "background":
        if background is None:
            raise ValueError("background threshold needs a Background shape")
        thr = bg_mean + k * bg_sd
    elif method == "auto":
        fn = AUTO_METHODS[auto_method.lower()]
        thr = np.array([fn(s) for s in stack], dtype=float)
    else:
        thr = np.full(n, float(manual))
    return thr, bg_mean, bg_sd


def remove_background(stack: np.ndarray, thr: np.ndarray, below: Below = "subtract") -> np.ndarray:
    t = thr[:, None, None].astype(np.float32)
    if below == "subtract":
        return np.maximum(stack - t, 0)
    return np.where(stack >= t, stack, 0).astype(np.float32)
