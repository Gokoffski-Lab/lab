"""Axons crossing each measurement line, counted like a person counts them by hand.

For each line and each included slice, the raw image is sampled along the line with a band that averages along
the axons (perpendicular to the line), and each peak rising more than peak_k x the profile's own noise above its
surroundings is one axon. The noise is measured on the averaged profile, so it needs no Background ROI and is not
affected by the background threshold.
Axons closer together than min_sep_um, or overlapping in the projection, count as one; near the crush, where
axons pile up, counts are therefore a lower bound.
"""

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from ...core.annotations import Shape
from .measure import line_profile


def _noise_sd(profile: np.ndarray) -> float:
    """Robust noise SD of a profile from its point-to-point differences (axon peaks barely move the median)."""
    d = np.diff(profile)
    return float(1.4826 * np.median(np.abs(d - np.median(d))) / np.sqrt(2)) if d.size else 0.0


def line_crossings(plane: np.ndarray, xy: np.ndarray, band_px: int, min_sep_px: float, peak_k: float):
    """Peak positions (x, y) along one straight line on one slice.

    The line is extended by 2 x min_sep at each end: an axon lying on the end of a line drawn edge to edge would
    otherwise be the profile's last sample, which can never be a peak.
    """
    xy = np.asarray(xy, float)
    u = xy[1] - xy[0]
    u = u / max(np.hypot(*u), 1e-9)
    ext = 2 * max(min_sep_px, 1)
    xy = np.array([xy[0] - ext * u, xy[1] + ext * u])
    prof = line_profile(plane, xy, band_px)
    prom = peak_k * _noise_sd(prof)
    if prom <= 0:
        return np.zeros((0, 2))
    idx, _ = find_peaks(prof, prominence=prom, distance=max(1, min_sep_px))
    (x1, y1), (x2, y2) = xy
    t = idx / max(len(prof), 1)
    return np.stack([x1 + t * (x2 - x1), y1 + t * (y2 - y1)], axis=-1)


def crossing_counts(stack, lines: list[Shape], inc_lines, um_per_px, dist, length, p):
    """Return (counts table, per-slice counts [z, line], overlay shapes)."""
    pw = um_per_px[0]
    nz = stack.shape[0]
    band_px = max(1, int(round(p.count_band_um / pw)))
    min_sep_px = p.min_sep_um / pw
    per_slice = np.zeros((nz, len(lines)), int)
    overlays = []
    for z in range(nz):
        for j, s in enumerate(lines):
            if not inc_lines[z, j]:
                continue
            pts = line_crossings(stack[z], s.xy, band_px, min_sep_px, p.peak_k)
            per_slice[z, j] = len(pts)
            if len(pts):
                overlays.append(Shape(f"Axons_{s.name}_z{z + 1}", "points", pts))
    n_inc = inc_lines.sum(axis=0)
    total = (per_slice * inc_lines).sum(axis=0)
    mean = np.where(n_inc > 0, total / np.maximum(n_inc, 1), 0.0)
    per_mm = mean / (length / 1000)
    table = pd.DataFrame(
        {"roi": [s.name for s in lines], "distance_um": dist, "line_length_um": length, "slices_counted": n_inc,
         "axons_mean_per_slice": mean, "axons_total": total, "axons_per_mm_width": per_mm}
    )
    if p.section_thickness_um > 0:
        # Leon et al. 2000: axons per nerve = pi r^2 x (axons per mm of width) / section thickness
        r_mm = length / 2000
        table["sigma_ad"] = np.pi * r_mm**2 * per_mm / (p.section_thickness_um / 1000)
    return table, per_slice, overlays
