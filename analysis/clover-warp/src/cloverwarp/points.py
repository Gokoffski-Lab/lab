"""Carry cell centroids through the warp and into retinal coordinates.

This is the module that produces the thing the lab actually wants: a table
of RGCs with a retinal position, and densities that are comparable between
animals. Everything upstream exists to make this table trustworthy.

Input is a centroid table from whatever counted the cells -- Imaris Spots
statistics export, an ``rbpms-count`` CSV, or a Fiji Results table. The
column names differ between all three, so :func:`read_centroids` sniffs
them rather than demanding one format.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .frames import RetinalFrame
from .warp import Transform

__all__ = [
    "read_centroids",
    "transfer",
    "density_map",
    "ring_density",
    "quadrant_summary",
]

# candidate column names, lowercased, in priority order
_X_KEYS = ("position x", "centroid_x", "center_x", "x_px", "xm", "x")
_Y_KEYS = ("position y", "centroid_y", "center_y", "y_px", "ym", "y")


def _pick(columns, keys) -> str | None:
    lut = {c.strip().lower(): c for c in columns}
    for k in keys:
        if k in lut:
            return lut[k]
    for k in keys:  # substring fallback, e.g. "Position X [um]"
        for low, orig in lut.items():
            if low.startswith(k):
                return orig
    return None


def read_centroids(
    path,
    petal: str | None = None,
    scale_to_px: float = 1.0,
) -> pd.DataFrame:
    """Read a centroid table and normalise it to ``petal, x, y`` in pixels.

    ``scale_to_px`` converts the file's units into image pixels. Imaris
    exports in microns by default, so this is ``1 / um_per_px`` for an Imaris
    table and ``1.0`` for a table already in pixels. Getting this wrong
    produces a result that looks plausible and is wrong by a constant factor,
    so the value used is recorded in the output metadata.
    """
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        # Imaris statistics CSVs carry preamble lines before the real header
        df = None
        for skip in range(0, 5):
            try:
                cand = pd.read_csv(path, skiprows=skip)
            except Exception:
                continue
            if _pick(cand.columns, _X_KEYS) and _pick(cand.columns, _Y_KEYS):
                df = cand
                break
        if df is None:
            raise ValueError(f"{path}: could not find x/y columns in the first 5 rows")

    xc, yc = _pick(df.columns, _X_KEYS), _pick(df.columns, _Y_KEYS)
    if xc is None or yc is None:
        raise ValueError(
            f"{path}: no x/y columns found; saw {list(df.columns)[:12]}"
        )
    out = pd.DataFrame(
        {
            "x": pd.to_numeric(df[xc], errors="coerce") * scale_to_px,
            "y": pd.to_numeric(df[yc], errors="coerce") * scale_to_px,
        }
    ).dropna()
    pc = _pick(df.columns, ("petal", "clover", "leaf"))
    out["petal"] = df[pc].astype(str).loc[out.index] if pc else (petal or path.stem)
    out.attrs["scale_to_px"] = scale_to_px
    out.attrs["source"] = str(path)
    return out.reset_index(drop=True)


def transfer(
    centroids: pd.DataFrame,
    transforms: dict[str, Transform],
    frame: RetinalFrame,
) -> pd.DataFrame:
    """Map centroids from petal pixels to FA pixels and retinal coordinates.

    Adds ``fa_x, fa_y, eccentricity_rad, meridian_rad, eccentricity_mm,
    quadrant, in_retina``. Petals with no transform are kept with NaN
    coordinates rather than dropped, so a count of unmapped cells appears in
    QC instead of silently vanishing.
    """
    df = centroids.copy()
    for col in ("fa_x", "fa_y"):
        df[col] = np.nan
    for petal, idx in df.groupby("petal").groups.items():
        T = transforms.get(str(petal))
        if T is None:
            continue
        pts = df.loc[idx, ["x", "y"]].to_numpy(dtype=float)
        mapped = T(pts)
        df.loc[idx, "fa_x"] = mapped[:, 0]
        df.loc[idx, "fa_y"] = mapped[:, 1]

    ok = df[["fa_x", "fa_y"]].notna().all(axis=1)
    df["eccentricity_rad"] = np.nan
    df["meridian_rad"] = np.nan
    if ok.any():
        ret = frame.to_retinal(df.loc[ok, ["fa_x", "fa_y"]].to_numpy(dtype=float))
        df.loc[ok, "eccentricity_rad"] = ret[:, 0]
        df.loc[ok, "meridian_rad"] = ret[:, 1]
        df.loc[ok, "quadrant"] = frame.quadrant(ret)
        df.loc[ok, "in_retina"] = frame.in_bounds(ret)
    df["eccentricity_mm"] = frame.eye.arclength_mm(df["eccentricity_rad"].to_numpy())
    df.attrs.update(centroids.attrs)
    return df


def ring_density(
    mapped: pd.DataFrame,
    frame: RetinalFrame,
    n_rings: int = 8,
) -> pd.DataFrame:
    """Cell density in concentric rings of equal eccentricity.

    Ring areas are computed **on the sphere**, not in the projected plane, so
    peripheral densities are not inflated. This is the output format that
    matches what RGCode+ reports, which makes the two directly comparable --
    worth having if ``rbpms-count`` is ever benchmarked against it.
    """
    df = mapped.dropna(subset=["eccentricity_rad"])
    df = df[df.get("in_retina", True).astype(bool)] if "in_retina" in df else df
    rim = frame.eye.rim_eccentricity
    edges = np.linspace(0.0, rim, n_rings + 1)
    R = frame.eye.retinal_radius_mm
    rows = []
    for i in range(n_rings):
        lo, hi = edges[i], edges[i + 1]
        n = int(((df["eccentricity_rad"] >= lo) & (df["eccentricity_rad"] < hi)).sum())
        # spherical zone area between two polar angles
        area = 2 * np.pi * R**2 * (np.cos(lo) - np.cos(hi))
        rows.append(
            {
                "ring": i,
                "ecc_lo_deg": np.rad2deg(lo),
                "ecc_hi_deg": np.rad2deg(hi),
                "ecc_mid_mm": R * 0.5 * (lo + hi),
                "n_cells": n,
                "area_mm2": area,
                "density_per_mm2": n / area if area > 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def quadrant_summary(mapped: pd.DataFrame, frame: RetinalFrame) -> pd.DataFrame:
    """Counts and densities per quadrant.

    Quadrant indices are geometric, not anatomical: label them
    dorsal/ventral/nasal/temporal yourself from the orientation marks, and
    record the mapping with the dataset. The code has no way to know how the
    retina was mounted.
    """
    df = mapped.dropna(subset=["eccentricity_rad"])
    if "in_retina" in df:
        df = df[df["in_retina"].astype(bool)]
    R = frame.eye.retinal_radius_mm
    rim = frame.eye.rim_eccentricity
    cap_area = 2 * np.pi * R**2 * (1 - np.cos(rim))
    rows = []
    for q in range(4):
        n = int((df["quadrant"] == q).sum())
        area = cap_area / 4
        rows.append(
            {
                "quadrant": q,
                "n_cells": n,
                "area_mm2": area,
                "density_per_mm2": n / area if area > 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def density_map(
    mapped: pd.DataFrame,
    frame: RetinalFrame,
    bin_px: float = 100.0,
    sigma_bins: float = 1.5,
):
    """Smoothed density image in FA space, corrected to cells/mm^2.

    Returns ``(density, extent)`` where ``extent`` is
    ``(x_min, x_max, y_min, y_max)`` in FA pixels for ``imshow``. The
    per-bin area correction from :meth:`RetinalFrame.area_element_mm2` is
    applied, which is what makes the far periphery of a clover comparable to
    the region beside the disc.
    """
    from scipy.ndimage import gaussian_filter

    df = mapped.dropna(subset=["fa_x", "fa_y"])
    if df.empty:
        raise ValueError("no mapped centroids to bin")
    x, y = df["fa_x"].to_numpy(), df["fa_y"].to_numpy()
    pad = 2 * bin_px
    xe = np.arange(x.min() - pad, x.max() + pad + bin_px, bin_px)
    ye = np.arange(y.min() - pad, y.max() + pad + bin_px, bin_px)
    counts, _, _ = np.histogram2d(y, x, bins=[ye, xe])
    counts = gaussian_filter(counts, sigma_bins)

    cy = 0.5 * (ye[:-1] + ye[1:])
    cx = 0.5 * (xe[:-1] + xe[1:])
    gx, gy = np.meshgrid(cx, cy)
    ret = frame.to_retinal(np.column_stack([gx.ravel(), gy.ravel()]))
    mm2_per_px = frame.area_element_mm2(ret).reshape(gy.shape)
    area = mm2_per_px * (bin_px**2)
    with np.errstate(divide="ignore", invalid="ignore"):
        dens = np.where(area > 0, counts / area, np.nan)
    return dens, (xe[0], xe[-1], ye[-1], ye[0])
