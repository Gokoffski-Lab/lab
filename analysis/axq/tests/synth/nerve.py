"""Synthetic CTB-labelled optic nerves with known regeneration, straight or curved.

Axons run proximal (left / curve start) to the crush; a fraction regrow past it with
exponentially distributed lengths. truth(d) is the exact fraction of Pre axons reaching d um.
"""

from dataclasses import dataclass

import numpy as np

from axq.core.annotations import Shape
from axq.core.image import Image

NZ = 12
NERVE_SLICES = range(2, 10)  # slices 0,1,10,11 lie outside the nerve
HALF_WIDTH = 100  # nerve half-width in px (1 um/px)
CRUSH_S = 1000  # crush position along the nerve, um from proximal end
LENGTH = 2400  # nerve length, um
AXON = 1000.0


@dataclass(frozen=True)
class Axons:
    t: np.ndarray  # offset across the nerve, px
    z: np.ndarray
    length: np.ndarray  # regrowth past the crush, um (0 = no regrowth)

    def truth(self, d: float) -> float:
        return float((self.length >= d).mean())


def make_axons(seed: int = 42, n: int = 200, regen: float = 0.6, mean_len: float = 500, spacing_px: int = 0) -> Axons:
    """spacing_px > 0 keeps axons in the same slice at least that far apart, so each is countable."""
    rng = np.random.default_rng(seed)
    t = rng.integers(-HALF_WIDTH + 5, HALF_WIDTH - 5, n).astype(float)
    z = rng.integers(NERVE_SLICES.start, NERVE_SLICES.stop, n)
    if spacing_px:
        grid = np.arange(-HALF_WIDTH + 5, HALF_WIDTH - 5, spacing_px, dtype=float)
        for zz in NERVE_SLICES:
            idx = np.flatnonzero(z == zz)
            if len(idx) > len(grid):
                raise ValueError("too many axons per slice for this spacing")
            t[idx] = rng.choice(grid, len(idx), replace=False)
    length = np.where(rng.random(n) < regen, rng.exponential(mean_len, n), 0.0)
    return Axons(t, z, length)


def _noise(shape, seed):
    rng = np.random.default_rng(seed + 1)
    return np.clip(rng.normal(0, 20, shape), 0, None) + 100  # like ImageJ "Add Specified Noise" on 16-bit, +100


def straight(axons: Axons, autofluor: float = 0.0, seed: int = 42) -> tuple[Image, list[Shape]]:
    h, w, cy = 300, LENGTH, 150
    data = np.zeros((NZ, h, w), np.float32)
    for t, z, ln in zip(axons.t, axons.z, axons.length):
        y = int(cy + t)
        data[z, y, : CRUSH_S + 1] = AXON
        if ln > 0:
            data[z, y, CRUSH_S : int(min(w - 1, CRUSH_S + ln)) + 1] = AXON
    if autofluor:
        for z in NERVE_SLICES:
            data[z, cy - HALF_WIDTH : cy + HALF_WIDTH] += autofluor
    data = np.round(data + _noise(data.shape, seed)).astype(np.float32)
    shapes = [
        Shape.line("Pre", 600, 40, 600, 260),
        Shape.line("Crush", CRUSH_S, 40, CRUSH_S, 260),
        Shape.rect("Background", 0, 0, w, 35),
    ] + [Shape.line(f"Post_{d}um", CRUSH_S + d, 40, CRUSH_S + d, 260) for d in (250, 500, 750, 1000)]
    return Image(data, (1.0, 1.0), "synth_straight"), shapes


def centerline(s: np.ndarray, bend: float = 0.6) -> tuple[np.ndarray, np.ndarray]:
    """Position and unit normal along a gently S-curved nerve, parameterized by arc length s (um)."""
    ds = 0.25
    grid = np.arange(0, LENGTH + ds, ds)
    heading = bend * np.sin(2 * np.pi * grid / LENGTH)
    xs = np.concatenate([[0], np.cumsum(np.cos(heading[:-1]) * ds)])
    ys = np.concatenate([[0], np.cumsum(np.sin(heading[:-1]) * ds)])
    x = np.interp(s, grid, xs)
    y = np.interp(s, grid, ys)
    th = np.interp(s, grid, heading)
    return np.stack([x, y], -1), np.stack([-np.sin(th), np.cos(th)], -1)


def curved(axons: Axons, autofluor: float = 20.0, seed: int = 42, bend: float = 0.6) -> Image:
    margin = 150
    s_all = np.arange(0, LENGTH, 0.5)
    pos, _ = centerline(s_all, bend)
    off = pos.min(0) - margin
    h = int(np.ceil(pos[:, 1].max() - off[1] + margin))
    w = int(np.ceil(pos[:, 0].max() - off[0] + margin))
    data = np.zeros((NZ, h, w), np.float32)

    def stamp(z, s, t, value, accumulate=False):
        p, nrm = centerline(s, bend)
        q = p + t[..., None] * nrm - off if np.ndim(t) else p + t * nrm - off
        q = np.round(q.reshape(-1, 2)).astype(int)
        q = q[(q[:, 0] >= 0) & (q[:, 0] < w) & (q[:, 1] >= 0) & (q[:, 1] < h)]
        q = np.unique(q, axis=0)
        if accumulate:
            data[z, q[:, 1], q[:, 0]] += value
        else:
            data[z, q[:, 1], q[:, 0]] = value

    for t, z, ln in zip(axons.t, axons.z, axons.length):
        end = CRUSH_S + min(ln, LENGTH - CRUSH_S - 1) if ln > 0 else CRUSH_S
        stamp(z, np.arange(0, end, 0.5), t, AXON)
    if autofluor:
        ss, tt = np.meshgrid(np.arange(0, LENGTH, 0.5), np.arange(-HALF_WIDTH, HALF_WIDTH, 0.5))
        p, nrm = centerline(ss.ravel(), bend)
        q = np.unique(np.round(p + tt.ravel()[:, None] * nrm - off).astype(int), axis=0)
        mask = np.zeros((h, w), bool)
        mask[q[:, 1], q[:, 0]] = True
        for z in NERVE_SLICES:
            data[z][mask] += autofluor
    data = np.round(data + _noise(data.shape, seed)).astype(np.float32)
    return Image(data, (1.0, 1.0), "synth_curved")
