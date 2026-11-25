"""Landmark sets: the manual path, and the format the automated path emits.

The lightweight path through this repo is: open the FA image and one petal
side by side in Fiji's **BigWarp**, click matched vessel bifurcations, export
the landmark CSV, and run :func:`cloverwarp.pipeline.register_from_landmarks`.
That path needs none of the segmentation or graph-matching machinery and is
the only path that should be trusted until it has been shown to work on real
retinas. The automated path exists to reproduce it at scale, and is measured
against it.

Two CSV flavours are read:

BigWarp export
    ``name,active,movingX,movingY,fixedX,fixedY`` -- Fiji writes this with
    quoted fields and no header. "moving" is the petal, "fixed" is the FA.

cloverwarp native
    ``petal,label,petal_x,petal_y,fa_x,fa_y`` with a header. This is what
    the automated matcher writes and what QC reports read back, so a human
    can correct a bad automated match by editing one row.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

__all__ = ["LandmarkSet", "read_bigwarp_csv", "read_native_csv", "read_csv", "write_native_csv"]

NATIVE_HEADER = ["petal", "label", "petal_x", "petal_y", "fa_x", "fa_y"]


@dataclass
class LandmarkSet:
    """Matched points between one petal and the FA reference.

    ``petal`` is the petal identifier (free-form string; use the same ids
    everywhere -- the slide label, ``L6``, whatever the lab already writes on
    the tube). ``labels`` are per-correspondence names, carried through so a
    QC report can say *which* bifurcation is the outlier.
    """

    petal: str
    petal_xy: np.ndarray
    fa_xy: np.ndarray
    labels: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.petal_xy = np.asarray(self.petal_xy, dtype=float).reshape(-1, 2)
        self.fa_xy = np.asarray(self.fa_xy, dtype=float).reshape(-1, 2)
        if len(self.petal_xy) != len(self.fa_xy):
            raise ValueError(
                f"petal {self.petal!r}: {len(self.petal_xy)} petal points but "
                f"{len(self.fa_xy)} FA points"
            )
        if not self.labels:
            self.labels = [f"p{i:03d}" for i in range(len(self.petal_xy))]
        elif len(self.labels) != len(self.petal_xy):
            raise ValueError(f"petal {self.petal!r}: label count mismatch")

    def __len__(self) -> int:
        return len(self.petal_xy)

    def subset(self, mask) -> LandmarkSet:
        mask = np.asarray(mask)
        idx = np.flatnonzero(mask) if mask.dtype == bool else mask.astype(int)
        return LandmarkSet(
            petal=self.petal,
            petal_xy=self.petal_xy[idx],
            fa_xy=self.fa_xy[idx],
            labels=[self.labels[i] for i in idx],
        )


def _clean(value: str) -> str:
    return value.strip().strip('"').strip()


def read_bigwarp_csv(path, petal: str | None = None) -> LandmarkSet:
    """Read a Fiji BigWarp landmark export.

    Inactive rows (``active`` false) are dropped, which is how you disable a
    landmark in BigWarp without deleting it. Rows with a missing coordinate
    on either side are dropped too -- BigWarp writes those when a point has
    been placed in one viewer only.
    """
    path = Path(path)
    name = petal or path.stem
    labels, moving, fixed = [], [], []
    with path.open(newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 6:
                continue
            cells = [_clean(c) for c in row]
            if cells[0].lower() in {"name", "#name"}:
                continue  # header, if the user added one
            active = cells[1].lower()
            if active in {"false", "0", "f"}:
                continue
            try:
                mx, my, fx, fy = (float(c) for c in cells[2:6])
            except ValueError:
                continue
            if not all(np.isfinite([mx, my, fx, fy])):
                continue
            labels.append(cells[0] or f"p{len(labels):03d}")
            moving.append((mx, my))
            fixed.append((fx, fy))
    if not moving:
        raise ValueError(f"{path}: no usable landmark rows")
    return LandmarkSet(name, np.array(moving), np.array(fixed), labels)


def read_native_csv(path) -> dict[str, LandmarkSet]:
    """Read a cloverwarp landmark CSV, which may hold several petals."""
    path = Path(path)
    buckets: dict[str, list[tuple]] = {}
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        missing = set(NATIVE_HEADER) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        for row in reader:
            buckets.setdefault(row["petal"], []).append(
                (
                    row["label"],
                    float(row["petal_x"]),
                    float(row["petal_y"]),
                    float(row["fa_x"]),
                    float(row["fa_y"]),
                )
            )
    out = {}
    for name, rows in buckets.items():
        out[name] = LandmarkSet(
            petal=name,
            petal_xy=np.array([(r[1], r[2]) for r in rows]),
            fa_xy=np.array([(r[3], r[4]) for r in rows]),
            labels=[r[0] for r in rows],
        )
    return out


def read_csv(path, petal: str | None = None) -> dict[str, LandmarkSet]:
    """Read either flavour, sniffing by the header line."""
    path = Path(path)
    with path.open(newline="") as fh:
        first = fh.readline()
    if "petal_x" in first and "fa_x" in first:
        return read_native_csv(path)
    return {path.stem if petal is None else petal: read_bigwarp_csv(path, petal)}


def write_native_csv(path, sets) -> Path:
    """Write one or many :class:`LandmarkSet` to the native CSV format."""
    path = Path(path)
    if isinstance(sets, LandmarkSet):
        sets = [sets]
    elif isinstance(sets, dict):
        sets = list(sets.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(NATIVE_HEADER)
        for ls in sets:
            for label, (px, py), (fx, fy) in zip(ls.labels, ls.petal_xy, ls.fa_xy, strict=True):
                writer.writerow([ls.petal, label, px, py, fx, fy])
    return path
