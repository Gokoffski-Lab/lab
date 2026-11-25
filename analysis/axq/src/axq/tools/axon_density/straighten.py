"""Find the nerve, straighten it along its centerline, and propose Crush / Pre / Background / Post lines.

Replaces the hand-drawn Segmented Line + Straighten step. Every output is a suggestion the user confirms.
"""

import numpy as np
from scipy import ndimage as ndi
from scipy.interpolate import splev, splprep
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from skimage import filters, morphology

from ...core.annotations import Shape
from ...core.image import Image


def nerve_mask(mean_proj: np.ndarray, blur_px: float) -> np.ndarray:
    """Whole nerve, including the dim distal part: Otsu on the log of the mean projection.

    Bright proximal CTB is orders of magnitude above the distal tissue signal, so a linear threshold keeps only
    the proximal nerve; on a log scale tissue autofluorescence separates cleanly from empty background.
    """
    smooth = filters.gaussian(np.log1p(np.clip(mean_proj - mean_proj.min(), 0, None)), blur_px)
    mask = smooth > filters.threshold_otsu(smooth)
    mask = ndi.binary_opening(mask, morphology.disk(max(1, int(4 * blur_px))))  # cut bridges to nearby tissue
    labels, n = ndi.label(mask)
    if n == 0:
        raise ValueError("no nerve found in the mean projection")
    mask = labels == (np.argmax(np.bincount(labels.ravel())[1:]) + 1)
    mask = ndi.binary_closing(mask, morphology.disk(max(1, int(blur_px))))
    return ndi.binary_fill_holes(mask)


def longest_path(skel: np.ndarray) -> np.ndarray:
    """Pixel path (row, col) between the two most distant ends of a skeleton."""
    rc = np.argwhere(skel)
    index = -np.ones(skel.shape, int)
    index[tuple(rc.T)] = np.arange(len(rc))
    rows, cols, wts = [], [], []
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        nb = rc + (dr, dc)
        ok = (nb[:, 0] < skel.shape[0]) & (nb[:, 1] >= 0) & (nb[:, 1] < skel.shape[1])
        j = np.full(len(rc), -1)
        j[ok] = index[nb[ok, 0], nb[ok, 1]]
        keep = j >= 0
        rows.append(np.flatnonzero(keep))
        cols.append(j[keep])
        wts.append(np.full(keep.sum(), np.hypot(dr, dc)))
    g = coo_matrix((np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))), shape=(len(rc),) * 2)
    d0 = dijkstra(g, directed=False, indices=0)
    a = int(np.argmax(np.where(np.isfinite(d0), d0, -1)))
    da, pred = dijkstra(g, directed=False, indices=a, return_predecessors=True)
    b = int(np.argmax(np.where(np.isfinite(da), da, -1)))
    path = [b]
    while path[-1] != a:
        path.append(pred[path[-1]])
    return rc[path[::-1]]


def centerline(
    mask: np.ndarray, guide: np.ndarray | None = None, guide_smooth_px: float = 100.0, step_px: float = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    """Smooth centerline points (x, y) at unit arc-length spacing, and unit normals.

    Without a guide, the path is the mask's skeleton, extended to both ends of the mask. With a guide (a rough
    polyline the user clicked along the nerve, (n, 2) as x, y), the path follows the guide end to end.
    """
    if guide is None:
        path = longest_path(morphology.skeletonize(mask))
        # a blunt nerve end skeletonizes into spurs toward its corners; drop one half-width at each end,
        # then _extend_to_mask_edge continues straight along the nerve axis instead
        trim = int(ndi.distance_transform_edt(mask)[tuple(path.T)].max())
        if len(path) > 4 * trim:
            path = path[trim:-trim]
        path = path[:, ::-1].astype(float)  # -> (x, y)
        sigma = max(trim, 1)
    else:
        path = _densify(np.asarray(guide, float))
        sigma = guide_smooth_px
    # bends tighter than the nerve half-width make neighbouring normals cross and fold the straightened image
    path = ndi.gaussian_filter1d(path, sigma=sigma, axis=0, mode="nearest")
    sub = path[:: max(1, len(path) // 200)]
    if not np.allclose(sub[-1], path[-1]):
        sub = np.vstack([sub, path[-1]])
    tck, _ = splprep(sub.T, s=len(sub) * 4.0)
    fine = np.array(splev(np.linspace(0, 1, len(path) * 4), tck)).T
    if guide is None:
        fine = _extend_to_mask_edge(fine, mask)
    seg = np.hypot(*np.diff(fine, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.arange(0, s[-1], step_px)
    pts = np.stack([np.interp(t, s, fine[:, 0]), np.interp(t, s, fine[:, 1])], -1)
    tan = np.gradient(pts, axis=0)
    tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    return pts, np.stack([-tan[:, 1], tan[:, 0]], -1)


def _densify(xy: np.ndarray) -> np.ndarray:
    seg = np.hypot(*np.diff(xy, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.arange(0, s[-1], 1.0)
    return np.stack([np.interp(t, s, xy[:, 0]), np.interp(t, s, xy[:, 1])], -1)


def _extend_to_mask_edge(pts: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Skeletons stop about one half-width short of each end; continue along the end tangent to the mask edge."""
    h, w = mask.shape

    def inside(p):
        x, y = int(round(p[0])), int(round(p[1]))
        return 0 <= x < w and 0 <= y < h and mask[y, x]

    def grow(end, prev):
        d = (end - prev) / max(np.linalg.norm(end - prev), 1e-9)
        out, p = [], end + d
        while inside(p) and len(out) < max(h, w):
            out.append(p.copy())
            p = p + d
        return out

    k = min(20, len(pts) - 1)
    head = grow(pts[0], pts[k])[::-1]
    tail = grow(pts[-1], pts[-1 - k])
    return np.vstack([np.array(head).reshape(-1, 2), pts, np.array(tail).reshape(-1, 2)])


def resample(stack: np.ndarray, pts: np.ndarray, normals: np.ndarray, half: int, order: int = 1) -> np.ndarray:
    """Sample perpendicular to the centerline: output [z, 2*half+1, len(pts)]."""
    t = np.arange(-half, half + 1, dtype=float)
    xs = pts[None, :, 0] + t[:, None] * normals[None, :, 0]
    ys = pts[None, :, 1] + t[:, None] * normals[None, :, 1]
    return np.stack(
        [ndi.map_coordinates(pl, [ys, xs], order=order, mode="constant", cval=np.nan) for pl in stack]
    )


def suggest(img: Image, p, hints: list[Shape] | None = None) -> tuple[Image, list[Shape]]:
    """hints: an optional polyline (any name; "Centerline" preferred) drawn roughly along the nerve on the raw
    image. Use it when the automatic outline merges the nerve with neighbouring tissue or a second nerve."""
    pw = float(np.mean(img.um_per_px))
    um = lambda v: v / pw  # noqa: E731  um -> px
    proj = img.data.mean(axis=0)
    guides = [s for s in hints or [] if s.kind == "polyline"]
    guide = next((s for s in guides if s.name == "Centerline"), guides[0] if guides else None)

    if p.straighten:
        mask = nerve_mask(proj, um(p.blur_um))
        pts, normals = centerline(mask, None if guide is None else guide.xy, guide_smooth_px=um(60))
        along = ndi.distance_transform_edt(mask)[
            np.clip(np.round(pts[:, 1]).astype(int), 0, mask.shape[0] - 1),
            np.clip(np.round(pts[:, 0]).astype(int), 0, mask.shape[1] - 1),
        ]
        # a guided path may cross tissue merged into the mask; ignore the widest 10% of positions
        half_nerve = along.max() if guide is None else np.percentile(along, 90)
        half = int(np.ceil(half_nerve + um(p.margin_um)))
        data = resample(img.data, pts, normals, half)
        smask = resample(mask[None].astype(np.float32), pts, normals, half, order=0)[0] > 0.5
        valid = ~np.isnan(data).any(axis=0)  # samples that fell outside the raw image
        data = np.where(np.isnan(data), np.nanmedian(data), data)
    else:
        pts = None
        data = img.data
        smask = nerve_mask(proj, um(p.blur_um))
        valid = np.ones(smask.shape, bool)

    # proximal (eye) end carries the most CTB; put it on the left
    signal = _column_signal(data.max(axis=0), um(25))
    third = len(signal) // 3
    if (signal[-third:].mean() > signal[:third].mean()) != p.flip_direction:
        data, smask, valid, signal = data[..., ::-1], smask[:, ::-1], valid[:, ::-1], signal[::-1]
        if pts is not None:
            pts = pts[::-1]

    # the nerve's own tip is a steeper drop than any crush; search away from both ends
    cols = np.flatnonzero(smask.any(axis=0))
    end = int(um(200))
    lo, hi = cols[0] + end, cols[-1] - end
    crush_x = _crush_edge(signal, lo, hi) if hi > lo else _crush_edge(signal, 0, len(signal))

    pre_x = max(int(um(p.band_um)), int(round(crush_x - um(p.pre_offset_um))))

    def across(x):
        rows = np.flatnonzero(smask[:, min(max(int(x), 0), smask.shape[1] - 1)])
        if rows.size == 0:
            rows = np.flatnonzero(smask.any(axis=1))
        return rows.min() - 2, rows.max() + 2

    def vline(name, x):
        y0, y1 = across(x)
        return Shape.line(name, float(x), float(y0), float(x), float(y1))

    shapes = [vline("Pre", pre_x), vline("Crush", crush_x)]
    for d in p.distances_um:
        x = crush_x + um(d)
        if x < data.shape[2]:
            shapes.append(vline(f"Post_{d:g}um", x))
    bg = _background_strip(smask, valid, max(3, int(um(5))))
    if bg is not None:
        shapes.append(bg)
    if pts is not None:
        shapes.append(Shape("Centerline_source_px", "polyline", pts[:: max(1, len(pts) // 500)]))

    out = Image(data.astype(np.float32), (pw, pw), f"{img.name}_straight", img.source)
    return out, shapes


def _crush_edge(signal: np.ndarray, lo: int, hi: int) -> int:
    """Steepest drop distal to the signal peak.

    Searching the whole nerve can land inside the bright end-bulb band proximal to the crush (its rising edge
    sits next to dips in it); searching past the peak finds where that band ends. A fixed fraction of the
    peak would not work, because how far the signal falls at the crush depends on how much regrows.
    """
    grad = np.gradient(signal)
    peak = lo + int(np.argmax(signal[lo:hi]))
    return peak + int(np.argmin(grad[peak:hi]))


def _column_signal(mip: np.ndarray, sigma_px: float) -> np.ndarray:
    col = np.clip(mip - np.median(mip), 0, None).sum(axis=0)
    return ndi.gaussian_filter1d(col, sigma_px)


def _background_strip(smask: np.ndarray, valid: np.ndarray, gap: int) -> Shape | None:
    """Largest rectangle touching the top or bottom edge that avoids the nerve (plus a gap) and padded pixels."""
    h = smask.shape[0]
    blocked = ndi.binary_dilation(smask, iterations=gap) | ~valid
    any_blocked = blocked.any(axis=0)
    free_top = np.where(any_blocked, blocked.argmax(axis=0), h)
    free_bottom = np.where(any_blocked, blocked[::-1].argmax(axis=0), h)
    best, best_area = None, 0
    for free, at_top in ((free_top, True), (free_bottom, False)):
        for height in np.unique(free[free >= 5]):
            ok = free >= height
            edges = np.flatnonzero(np.diff(np.concatenate([[0], ok.astype(int), [0]])))
            starts, ends = edges[::2], edges[1::2]
            i = int(np.argmax(ends - starts))
            area = int(height) * int(ends[i] - starts[i])
            if area > best_area:
                y0 = 0 if at_top else h - int(height)
                best, best_area = (int(starts[i]), y0, int(ends[i] - starts[i]), int(height)), area
    return Shape.rect("Background", *best) if best else None
