from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import roifile
from roifile import ROI_TYPE, ImagejRoi

Kind = Literal["line", "polygon", "polyline", "points"]


@dataclass(frozen=True)
class Shape:
    """A named annotation in pixel coordinates; xy is (n, 2) as (x, y)."""

    name: str
    kind: Kind
    xy: np.ndarray

    @staticmethod
    def line(name: str, x1: float, y1: float, x2: float, y2: float) -> "Shape":
        return Shape(name, "line", np.array([[x1, y1], [x2, y2]], dtype=float))

    @staticmethod
    def rect(name: str, x: float, y: float, w: float, h: float) -> "Shape":
        return Shape(name, "polygon", np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=float))

    @property
    def midpoint(self) -> np.ndarray:
        return self.xy.mean(axis=0)


def find(shapes: list[Shape], name: str) -> Shape | None:
    return next((s for s in shapes if s.name == name), None)


_KIND = {
    ROI_TYPE.LINE: "line",
    ROI_TYPE.POLYLINE: "polyline",
    ROI_TYPE.FREELINE: "polyline",
    ROI_TYPE.POINT: "points",
}


def read_roiset(path: str | Path) -> list[Shape]:
    rois = roifile.roiread(path)
    if isinstance(rois, ImagejRoi):
        rois = [rois]
    shapes = []
    for r in rois:
        kind = _KIND.get(r.roitype, "polygon")
        if r.roitype == ROI_TYPE.LINE:
            xy = np.array([[r.x1, r.y1], [r.x2, r.y2]], dtype=float)
        else:
            xy = np.asarray(r.coordinates(), dtype=float)
            if kind == "polygon" and len(xy) > 1 and np.allclose(xy[0], xy[-1]):
                xy = xy[:-1]
        shapes.append(Shape(r.name or f"roi{len(shapes)}", kind, xy))
    return shapes


def write_roiset(shapes: list[Shape], path: str | Path) -> None:
    rois = []
    for s in shapes:
        if s.kind == "line":
            (x1, y1), (x2, y2) = s.xy
            r = ImagejRoi.frompoints(s.xy, name=s.name)
            r.roitype = ROI_TYPE.LINE
            r.x1, r.y1, r.x2, r.y2 = float(x1), float(y1), float(x2), float(y2)
        else:
            r = ImagejRoi.frompoints(s.xy, name=s.name)
            r.roitype = {"polygon": ROI_TYPE.POLYGON, "polyline": ROI_TYPE.POLYLINE, "points": ROI_TYPE.POINT}[s.kind]
        rois.append(r)
    path = Path(path)
    path.unlink(missing_ok=True)
    roifile.roiwrite(path, rois)
