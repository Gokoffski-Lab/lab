"""CTB signal along a straightened nerve (Python port of fiji/AxonQuantifier_v2.ijm)."""

import numpy as np
import pandas as pd
from scipy.ndimage import map_coordinates, uniform_filter1d

from ...core.annotations import Shape, find
from ...core.image import Image
from ...core.threshold import remove_background, slice_thresholds
from ...core.tool import Result


def line_profile(plane: np.ndarray, xy: np.ndarray, width_px: int) -> np.ndarray:
    """Band-averaged profile along a straight line, sampled like ImageJ getProfile (n = round(length))."""
    (x1, y1), (x2, y2) = xy
    d = np.array([x2 - x1, y2 - y1])
    length = float(np.hypot(*d))
    n = max(int(round(length)), 1)
    t = np.arange(n) / n
    px = x1 + t * d[0]
    py = y1 + t * d[1]
    normal = np.array([-d[1], d[0]]) / max(length, 1e-9)
    offs = np.arange(width_px) - (width_px - 1) / 2
    xs = px[None, :] + offs[:, None] * normal[0]
    ys = py[None, :] + offs[:, None] * normal[1]
    vals = map_coordinates(plane, [ys.ravel(), xs.ravel()], order=1, mode="nearest").reshape(xs.shape)
    return vals.mean(axis=0)


def _slice_selection(p, per_slice: np.ndarray, col_z: np.ndarray, pre_col: int) -> tuple[np.ndarray, np.ndarray]:
    """Which z-slices count, for each line [z, line] and each curve column [z, x].

    auto: per position, keep slices holding >= z_frac of that position's best slice. A whole nerve is rarely
          flat, so the slices that hold it at the Pre line are not the ones that hold it 2 mm further on.
    pre:  v2 macro rule; slices chosen from the Pre line alone and applied everywhere.
    """
    nz = per_slice.shape[0]

    def per_position(v):
        top = v.max(axis=0, keepdims=True)
        return (top > 0) & (v >= p.z_frac * top)

    if p.z == "auto":
        return per_position(per_slice), per_position(col_z)
    if p.z == "all":
        keep = np.ones(nz, bool)
    elif p.z == "manual":
        z = np.arange(1, nz + 1)
        keep = (z >= p.z_first) & (z <= (p.z_last if p.z_last > 0 else nz))
    elif p.z == "pre":
        keep = per_position(per_slice[:, [pre_col]])[:, 0]
    else:
        raise ValueError(f"unknown z selection {p.z!r}")
    return (np.repeat(keep[:, None], per_slice.shape[1], 1), np.repeat(keep[:, None], col_z.shape[1], 1))


def measure(img: Image, shapes: list[Shape], p) -> Result:
    pre, crush = find(shapes, "Pre"), find(shapes, "Crush")
    if pre is None or crush is None or pre.kind != "line" or crush.kind != "line":
        raise ValueError("annotations must include straight lines named Pre and Crush")
    bg = find(shapes, "Background")
    pw, ph = img.um_per_px
    stack = img.data
    nz, h, w = stack.shape

    thr, bg_mean, bg_sd = slice_thresholds(stack, p.threshold, bg, p.k, p.auto_method, p.manual_threshold)
    work = remove_background(stack, thr, p.below)

    crush_x = crush.midpoint[0]
    sgn = 1.0 if pre.midpoint[0] < crush_x else -1.0
    lines = sorted((s for s in shapes if s.kind == "line"), key=lambda s: (s.midpoint[0] - crush_x) * sgn)
    names = [s.name for s in lines]
    dist = np.array([(s.midpoint[0] - crush_x) * sgn * pw for s in lines])
    length = np.array([np.hypot((s.xy[1, 0] - s.xy[0, 0]) * pw, (s.xy[1, 1] - s.xy[0, 1]) * ph) for s in lines])
    pre_col = names.index("Pre")

    band_px = max(1, int(round(p.band_um / pw)))
    per_slice = np.array([[line_profile(work[z], s.xy, band_px).sum() * pw for s in lines] for z in range(nz)])

    col_z = work.sum(axis=1) * ph  # [z, x]: signal integrated across the nerve, per slice and position
    inc_lines, inc_cols = _slice_selection(p, per_slice, col_z, pre_col)
    include = inc_lines[:, pre_col]
    tot = (per_slice * inc_lines).sum(axis=0)
    if tot[pre_col] <= 0:
        raise ValueError("Pre signal is zero after thresholding; check threshold settings")
    pct = 100 * tot / tot[pre_col]

    col = (col_z * inc_cols).sum(axis=0)
    col_dist = (np.arange(w) + 0.5 - crush_x) * sgn * pw
    half = band_px // 2
    px = int(round(pre.midpoint[0]))
    pre_ref = col[max(0, px - half) : min(w - 1, px + half) + 1].mean()
    frac = col / pre_ref if pre_ref > 0 else np.zeros_like(col)
    smooth = uniform_filter1d(frac, size=2 * half + 1, mode="nearest")

    in_auc = (col_dist >= p.auc_min_um) & (col_dist <= p.auc_max_um)
    metrics = {f"auc_{p.auc_min_um:g}_{p.auc_max_um:g}_um": float(frac[in_auc].sum() * pw)}
    for f in p.reach:
        hit = col_dist[(col_dist > 0) & (smooth >= f)]
        metrics[f"reach_um_at_{f:g}_of_pre"] = float(hit.max()) if hit.size else 0.0
    metrics["max_measurable_um"] = float(col_dist.max())
    metrics["slices_included"] = int(include.sum())
    metrics["slices_total"] = int(nz)
    for name, d, v in zip(names, dist, pct):
        if name not in ("Pre",):
            metrics[f"pct_pre_{name}"] = float(v)

    per_slice_df = pd.DataFrame(per_slice, columns=names)
    overlays = []
    counts = None
    if p.count:
        from .count import crossing_counts

        counts, n_slice, overlays = crossing_counts(stack, lines, inc_lines, img.um_per_px, dist, length, p)
        per_slice_df = pd.concat([per_slice_df, pd.DataFrame(n_slice, columns=[f"axons_{n}" for n in names])], axis=1)
        for name, v in zip(names, counts["axons_mean_per_slice"]):
            if name != "Pre":
                metrics[f"axons_{name}"] = float(v)

    tables = {
        "lines": pd.DataFrame(
            {
                "roi": names,
                "distance_um": dist,
                "line_length_um": length,
                "integrated_signal": tot,
                "signal_per_um_of_line": tot / length,
                "percent_of_pre": pct,
            }
        ),
        "per_slice": pd.concat(
            [
                pd.DataFrame(
                    {"slice": np.arange(1, nz + 1), "included": include.astype(int), "threshold": thr,
                     "bg_mean": bg_mean, "bg_sd": bg_sd}
                ),
                per_slice_df,
            ],
            axis=1,
        ),
        "curve": pd.DataFrame(
            {"x_px": np.arange(w), "distance_um": col_dist, "integrated_signal": col,
             "fraction_of_pre": frac, "fraction_of_pre_smoothed": smooth}
        ),
    }
    if counts is not None:
        tables["counts"] = counts
    return Result(tables, metrics, overlays)
