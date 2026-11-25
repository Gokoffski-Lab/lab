"""Thin shims over scikit-image APIs that moved between 0.24 and 0.26.

Kept in one place so the science modules read cleanly and so there is exactly
one spot to delete when the minimum supported scikit-image catches up.
"""

from __future__ import annotations

import numpy as np
from skimage import morphology

__all__ = ["binary_closing", "remove_small_objects"]


def binary_closing(mask: np.ndarray, footprint) -> np.ndarray:
    """``morphology.closing`` on a boolean image, across versions."""
    try:
        return morphology.closing(mask, footprint).astype(bool)
    except TypeError:  # pragma: no cover - very old scikit-image
        return morphology.binary_closing(mask, footprint)


def remove_small_objects(mask: np.ndarray, min_px: int) -> np.ndarray:
    """Drop connected components smaller than ``min_px`` pixels.

    scikit-image renamed ``min_size`` to ``max_size`` and changed the
    comparison from ``<`` to ``<=``; ``min_px - 1`` keeps the old semantics
    (strictly smaller than ``min_px`` is removed) on the new API.
    """
    if min_px <= 0:
        return np.asarray(mask, dtype=bool)
    try:
        return morphology.remove_small_objects(mask, max_size=min_px - 1).astype(bool)
    except TypeError:
        return morphology.remove_small_objects(mask, min_size=min_px).astype(bool)
