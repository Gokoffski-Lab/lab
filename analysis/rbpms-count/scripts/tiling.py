"""Tile geometry and count ledgers for the RBPMS pipeline.

Standard library only, on purpose: this is the single source of truth for the tile geometry
that `count_rgc.groovy` reads out of `counts/plan.json`, and it has to be importable (and
testable) without pandas, numpy or tifffile.

Two jobs:

1. **Geometry.** A big flat-mount image is cut into *tiles*. Every tile has a **core** and a
   **padded window**. The cores partition the image exactly once, so every cell belongs to
   exactly one tile; the window is the core grown by `margin_px` on all sides so that the
   segmentation sees the same neighbourhood a cell would have had in the untiled image.
2. **Ledgers.** `tiles.csv` (one row per tile) folds up into `auto_counts.csv` (one row per
   image), and `tile_manual_counts.csv` folds up into `manual_counts.csv`.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

PLAN_VERSION = 1

IMAGES_COLUMNS = ["sample", "image", "file", "series", "format", "width_px", "height_px",
                  "z", "t", "channels", "channel_names", "rgb", "um_per_px", "bytes", "problem"]

TILES_COLUMNS = ["sample", "image", "tile", "col", "row", "x0", "y0", "w", "h",
                 "core_x0", "core_y0", "core_x1", "core_y1", "margin",
                 "auto_count", "objects_detected", "rejected_dim", "outside_core",
                 "core_px", "tissue_fraction", "skipped_empty",
                 "um_per_px", "source_format", "file", "counted_at", "problem"]

# the first six are the columns auto_counts.csv has always had; everything after is new
AUTO_COUNTS_COLUMNS = ["sample", "image", "auto_count", "objects_detected", "file", "counted_at",
                       "tiles", "tiles_counted", "core_px", "um_per_px", "area_mm2",
                       "cells_per_mm2", "source_format"]

# the first ten are the columns manual_counts.csv has always had
MANUAL_COUNTS_COLUMNS = ["sample", "image", "auto_count", "removed", "added", "final_count",
                         "reviewer", "reviewed_at", "seconds", "note", "tiles", "tiles_reviewed"]

ROIS_COLUMNS = ["cell", "x_px", "y_px", "parent_x_px", "parent_y_px", "area_px",
                "mean_intensity", "bg_mean", "contrast", "kept", "in_core"]

SUMMED_TILE_COLUMNS = ["auto_count", "objects_detected", "rejected_dim", "outside_core", "core_px"]


# ---------------------------------------------------------------- small helpers
def _as_int(v, default: int = 0) -> int:
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def _as_float(v, default=None):
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y", "t")


def _text(v) -> str:
    return "" if v is None else str(v).strip()


def read_csv_rows(path) -> list[dict]:
    """Rows of a .csv as dicts. Missing file -> no rows. Tolerates the utf-8 BOM Excel adds."""
    p = Path(path)
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8-sig") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def write_csv_rows(path, columns: Sequence[str], rows: Iterable[dict]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(columns), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
    return p


def last_by(rows: Iterable[dict], keys: Sequence[str]) -> list[dict]:
    """De-duplicate append-only ledger rows: last row for a key wins, first appearance orders."""
    order, latest = [], {}
    for r in rows:
        k = tuple(_text(r.get(c)) for c in keys)
        if k not in latest:
            order.append(k)
        latest[k] = r
    return [latest[k] for k in order]


# ---------------------------------------------------------------- records
@dataclass(frozen=True)
class SourceImage:
    """One series of one file on disk, as reported by Bio-Formats (`counts/images.csv`)."""
    sample: str
    image: str
    file: str = ""
    series: int = 0
    format: str = ""
    width_px: int = 0
    height_px: int = 0
    z: int = 1
    t: int = 1
    channels: int = 1
    channel_names: str = ""
    rgb: bool = False
    um_per_px: float | None = None
    bytes: int = 0
    problem: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.sample, self.image)


@dataclass(frozen=True)
class Tile:
    """A core that owns cells plus the padded window the segmentation actually runs on.

    Core is half-open, `[core_x0, core_x1) x [core_y0, core_y1)`, except on the right and
    bottom edge of the image: see `tile_owns`.
    """
    sample: str
    image: str
    tile: str
    col: int
    row: int
    x0: int
    y0: int
    w: int
    h: int
    core_x0: int
    core_y0: int
    core_x1: int
    core_y1: int
    margin: int
    is_right: bool
    is_bottom: bool
    todo: bool = True

    @property
    def core_w(self) -> int:
        return self.core_x1 - self.core_x0

    @property
    def core_h(self) -> int:
        return self.core_y1 - self.core_y0

    @property
    def core_px(self) -> int:
        return self.core_w * self.core_h

    @property
    def key(self) -> tuple[str, str]:
        return (self.sample, self.tile)


@dataclass(frozen=True)
class RunPlan:
    """What `count_rgc.groovy mode=run` has to do, written out as `counts/plan.json`."""
    tile_px: int
    margin_px: int
    images: tuple[SourceImage, ...] = ()
    tiles: tuple[Tile, ...] = ()
    settings: dict = field(default_factory=dict)
    count_tiles: bool = True
    materialize_tiles: bool = False
    skip_empty_tiles: bool = False
    tissue_fraction: float = 0.05
    overwrite: bool = False
    keep_normalized: bool = True
    created_at: str = ""
    version: int = PLAN_VERSION

    @property
    def todo_tiles(self) -> tuple[Tile, ...]:
        return tuple(t for t in self.tiles if t.todo)

    def tiles_of(self, sample: str, image: str) -> tuple[Tile, ...]:
        return tuple(t for t in self.tiles if t.sample == sample and t.image == image)


# ---------------------------------------------------------------- geometry
def derive_margin_px(max_diameter_px: float, local_threshold_radius: float,
                     gaussian_sigma: float, bg_radius_px: float) -> int:
    """How much context a tile needs so that a cell is segmented exactly as it would be untiled.

    The widest reach of any step in the pipeline wins: a whole cell body, the Niblack window,
    the Gaussian support (3 sigma) and the rolling-ball background radius.
    """
    return max(math.ceil(max_diameter_px) + 3,
               int(local_threshold_radius),
               math.ceil(3 * gaussian_sigma) + 1,
               int(bg_radius_px))


def validate_tiling(tile_px: int, margin_px: int, max_diameter_px: float,
                    width: int | None = None, height: int | None = None) -> None:
    """Raise ValueError if the tile size cannot hold cells of `max_diameter_px` sensibly."""
    if margin_px < 0:
        raise ValueError(f"margin_px must be >= 0, got {margin_px}")
    if tile_px <= 0:
        return                                             # tiling off
    if width is not None and height is not None and width <= tile_px and height <= tile_px:
        return                                             # one tile, no padding, nothing to check
    if tile_px < 4 * max_diameter_px:
        raise ValueError(
            f"tile_px={tile_px} is too small for max_diameter={max_diameter_px} px: a tile core "
            f"must be at least 4 cell diameters ({4 * max_diameter_px:.0f} px) wide, otherwise most "
            "of the work is spent on padding. Raise tile_px or lower max_diameter.")
    if 2 * margin_px >= tile_px:
        raise ValueError(
            f"margin_px={margin_px} is too large for tile_px={tile_px}: the padded windows would be "
            "more than twice the core. Raise tile_px.")


def _assert_partition(cells: Sequence[dict], width: int, height: int) -> None:
    """The cores must cover [0,width) x [0,height) with no overlap and no gap."""
    xs = sorted({(c["core_x0"], c["core_x1"]) for c in cells})
    ys = sorted({(c["core_y0"], c["core_y1"]) for c in cells})

    def contiguous(spans, n):
        at = 0
        for a, b in spans:
            if a != at or b <= a:
                return False
            at = b
        return at == n

    assert contiguous(xs, width), f"tile cores do not tile x exactly: {xs} for width {width}"
    assert contiguous(ys, height), f"tile cores do not tile y exactly: {ys} for height {height}"
    assert len(cells) == len(xs) * len(ys), "tile cores are not a full row x column product"
    area = sum((c["core_x1"] - c["core_x0"]) * (c["core_y1"] - c["core_y0"]) for c in cells)
    assert area == width * height, f"tile cores cover {area} px, image is {width * height} px"


def _spans(n: int, step: int) -> list[tuple[int, int]]:
    return [(a, min(a + step, n)) for a in range(0, n, step)]


def tile_grid(width: int, height: int, tile_px: int, margin_px: int = 0) -> list[dict]:
    """Cores and padded windows for a `width` x `height` image.

    Returns one dict per tile with the core bounds, the padded window `[x0, y0, w, h]` clamped
    to the image, and `is_right` / `is_bottom` edge flags. The padded windows do overlap; the
    cores never do (asserted before returning).

    `tile_px <= 0`, or an image that already fits in one tile, gives a single unpadded tile
    covering the whole image -- the pre-tiling behaviour.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"image must have a positive size, got {width} x {height}")
    if tile_px <= 0 or (width <= tile_px and height <= tile_px):
        cells = [dict(col=0, row=0, x0=0, y0=0, w=width, h=height,
                      core_x0=0, core_y0=0, core_x1=width, core_y1=height,
                      margin=0, is_right=True, is_bottom=True)]
        _assert_partition(cells, width, height)
        return cells

    margin_px = int(margin_px)
    cells = []
    for row, (cy0, cy1) in enumerate(_spans(height, tile_px)):
        for col, (cx0, cx1) in enumerate(_spans(width, tile_px)):
            x0, x1 = max(0, cx0 - margin_px), min(width, cx1 + margin_px)
            y0, y1 = max(0, cy0 - margin_px), min(height, cy1 + margin_px)
            cells.append(dict(col=col, row=row, x0=x0, y0=y0, w=x1 - x0, h=y1 - y0,
                              core_x0=cx0, core_y0=cy0, core_x1=cx1, core_y1=cy1,
                              margin=margin_px, is_right=cx1 == width, is_bottom=cy1 == height))
    _assert_partition(cells, width, height)
    return cells


def tile_name(image: str, row: int, col: int) -> str:
    return f"{image}_r{row:02d}c{col:02d}"


def plan_tiles(img: SourceImage, tile_px: int, margin_px: int = 0) -> list[Tile]:
    """Tiles for one source image. A single-tile image keeps its own name, so `counted/<sample>/
    <image>.tif` and the review tool behave exactly as they did before tiling existed."""
    cells = tile_grid(img.width_px, img.height_px, tile_px, margin_px)
    single = len(cells) == 1
    return [Tile(sample=img.sample, image=img.image,
                 tile=img.image if single else tile_name(img.image, c["row"], c["col"]), **c)
            for c in cells]


def tile_owns(tile: Tile, x: float, y: float) -> bool:
    """Does this tile own the cell whose centroid is at (x, y) in the *parent* image?

    Cores are half-open so that a centroid on an inner boundary belongs to the tile on its
    right/below, and to that tile only. The outer bound of the last column/row is inclusive
    instead, because a centroid can land exactly on `width` or `height` (a cell touching the
    edge of the image) and would otherwise be dropped by every tile.
    """
    ok_x = x >= tile.core_x0 and (x <= tile.core_x1 if tile.is_right else x < tile.core_x1)
    ok_y = y >= tile.core_y0 and (y <= tile.core_y1 if tile.is_bottom else y < tile.core_y1)
    return ok_x and ok_y


# ---------------------------------------------------------------- the plan
def plan_run(images: Iterable[SourceImage], tile_px: int, margin_px: int, *,
             done: Iterable = (), overwrite: bool = False, settings: dict | None = None,
             count_tiles: bool = True, materialize_tiles: bool = False,
             skip_empty_tiles: bool = False, tissue_fraction: float = 0.05,
             keep_normalized: bool = True, max_diameter_px: float | None = None) -> RunPlan:
    """Work out which tiles still need counting.

    `done` is whatever is already in `tiles.csv`: `(sample, tile)` pairs or `"sample/tile"`
    strings. Tiles already done keep `todo=False` instead of being dropped, because the
    counting script needs the full tile list of an image to crop and to draw the overview.
    """
    settings = dict(settings or {})
    max_d = float(settings.get("max_diameter", 0) if max_diameter_px is None else max_diameter_px)
    done_keys = {k if isinstance(k, tuple) else tuple(str(k).split("/", 1)) for k in done}

    usable = [i for i in images if not i.problem and i.width_px > 0 and i.height_px > 0]
    tiles: list[Tile] = []
    kept: list[SourceImage] = []
    for img in usable:
        validate_tiling(tile_px, margin_px, max_d, img.width_px, img.height_px)
        planned = plan_tiles(img, tile_px, margin_px)
        todo = [overwrite or t.key not in done_keys for t in planned]
        if not any(todo):
            continue
        kept.append(img)
        tiles += [Tile(**{**asdict(t), "todo": flag}) for t, flag in zip(planned, todo)]
    return RunPlan(tile_px=int(tile_px), margin_px=int(margin_px), images=tuple(kept),
                   tiles=tuple(tiles), settings=settings, count_tiles=count_tiles,
                   materialize_tiles=materialize_tiles, skip_empty_tiles=skip_empty_tiles,
                   tissue_fraction=float(tissue_fraction), overwrite=bool(overwrite),
                   keep_normalized=bool(keep_normalized),
                   created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def _tile_json(t: Tile) -> dict:
    d = {k: v for k, v in asdict(t).items() if k not in ("sample", "image")}
    d["core_px"] = t.core_px
    return d


def plan_to_obj(plan: RunPlan) -> dict:
    by_image: dict[tuple[str, str], list[Tile]] = {}
    for t in plan.tiles:
        by_image.setdefault((t.sample, t.image), []).append(t)
    return dict(version=plan.version, created_at=plan.created_at, tile_px=plan.tile_px,
                margin_px=plan.margin_px, count_tiles=plan.count_tiles,
                materialize_tiles=plan.materialize_tiles, skip_empty_tiles=plan.skip_empty_tiles,
                tissue_fraction=plan.tissue_fraction, overwrite=plan.overwrite,
                keep_normalized=plan.keep_normalized, settings=plan.settings,
                images=[{**asdict(img), "tiles": [_tile_json(t) for t in by_image.get(img.key, [])]}
                        for img in plan.images])


def write_plan(path, plan: RunPlan) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plan_to_obj(plan), indent=1), encoding="utf-8")
    return p


# ---------------------------------------------------------------- reading the ledgers
def read_images_csv(path) -> list[SourceImage]:
    out = []
    for r in last_by(read_csv_rows(path), ("sample", "image")):
        um = _as_float(r.get("um_per_px"))
        out.append(SourceImage(
            sample=_text(r.get("sample")), image=_text(r.get("image")), file=_text(r.get("file")),
            series=_as_int(r.get("series")), format=_text(r.get("format")),
            width_px=_as_int(r.get("width_px")), height_px=_as_int(r.get("height_px")),
            z=_as_int(r.get("z"), 1), t=_as_int(r.get("t"), 1),
            channels=_as_int(r.get("channels"), 1), channel_names=_text(r.get("channel_names")),
            rgb=_truthy(r.get("rgb")), um_per_px=um if (um or 0) > 0 else None,
            bytes=_as_int(r.get("bytes")), problem=_text(r.get("problem"))))
    return out


def read_tiles_csv(path) -> list[dict]:
    """`tiles.csv` rows with the numbers parsed. Append-only, so the last row for a tile wins."""
    rows = []
    for r in last_by(read_csv_rows(path), ("sample", "tile")):
        d = {c: _text(r.get(c)) for c in TILES_COLUMNS}
        for c in ("col", "row", "x0", "y0", "w", "h", "core_x0", "core_y0", "core_x1", "core_y1",
                  "margin", *SUMMED_TILE_COLUMNS):
            d[c] = _as_int(r.get(c))
        d["tissue_fraction"] = _as_float(r.get("tissue_fraction"))
        d["um_per_px"] = _as_float(r.get("um_per_px"))
        d["skipped_empty"] = _truthy(r.get("skipped_empty"))
        rows.append(d)
    return rows


def read_manual_csv(path) -> list[dict]:
    """`tile_manual_counts.csv` or `manual_counts.csv` rows with the numbers parsed.

    In `tile_manual_counts.csv` the `image` column holds the *tile* name (the review tool walks
    `counted/<sample>/*.tif` and does not know about tiles); `fold_manual` maps it back.
    """
    rows = []
    for r in last_by(read_csv_rows(path), ("sample", "image")):
        d = {k: _text(v) for k, v in r.items()}
        for c in ("auto_count", "removed", "added", "final_count"):
            d[c] = _as_int(r.get(c))
        d["seconds"] = _as_float(r.get("seconds"), 0.0) or 0.0
        rows.append(d)
    return rows


def done_tile_keys(path) -> set[tuple[str, str]]:
    """`(sample, tile)` of every tile already in `tiles.csv`, counted or deliberately skipped."""
    return {(r["sample"], r["tile"]) for r in read_tiles_csv(path) if r.get("tile")}


# ---------------------------------------------------------------- folding
def area_mm2(core_px: int, um_per_px: float | None) -> float | None:
    """Imaged area of the cores. None when the pixel size is unknown -- never a guessed 0.146."""
    if not um_per_px or um_per_px <= 0 or core_px <= 0:
        return None
    return core_px * um_per_px * um_per_px / 1e6        # um^2 -> mm^2


def fold_auto(tile_rows: Iterable[dict], images: Iterable[SourceImage] | None = None,
              tile_px: int = 0, margin_px: int = 0,
              include_incomplete: bool = False) -> list[dict]:
    """Fold `tiles.csv` into one `auto_counts.csv` row per original `(sample, image)`.

    An image is complete when every planned tile has a row -- a tile that was skipped as empty
    counts as done, it just contributes nothing. Incomplete images are left out so that the next
    `count()` picks their missing tiles up again.

    `images` (from `counts/images.csv`) supplies the planned tile list. Without it, or for an
    image that is no longer in the survey, the rows present are taken to be the whole image.
    """
    rows = last_by(tile_rows, ("sample", "tile"))
    planned: dict[tuple[str, str], list[Tile]] = {}
    by_key: dict[tuple[str, str], SourceImage] = {}
    for img in (images or ()):
        if img.problem or img.width_px <= 0 or img.height_px <= 0:
            continue
        by_key[img.key] = img
        planned[img.key] = plan_tiles(img, tile_px, margin_px)

    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        groups.setdefault((_text(r.get("sample")), _text(r.get("image"))), []).append(r)

    out = []
    for key in list(by_key) + [k for k in groups if k not in by_key]:
        got = groups.get(key, [])
        if not got:
            continue
        want = planned.get(key)
        n_tiles = len(want) if want is not None else len(got)
        have = {r["tile"] for r in got}
        complete = (set(t.tile for t in want) <= have) if want is not None else True
        if not complete and not include_incomplete:
            continue
        img = by_key.get(key)
        um = img.um_per_px if img is not None else next(
            (r["um_per_px"] for r in got if (r.get("um_per_px") or 0) > 0), None)
        core_px = sum(r["core_px"] for r in got)
        area = area_mm2(core_px, um)
        total = sum(r["auto_count"] for r in got)
        row = dict(sample=key[0], image=key[1], auto_count=total,
                   file=(img.file if img is not None else next((r["file"] for r in got if r.get("file")), "")),
                   counted_at=max((r.get("counted_at") or "") for r in got),
                   tiles=n_tiles, tiles_counted=len(have), core_px=core_px,
                   um_per_px=um, area_mm2=None if area is None else round(area, 6),
                   cells_per_mm2=None if not area else round(total / area, 1),
                   source_format=(img.format if img is not None
                                  else next((r["source_format"] for r in got if r.get("source_format")), "")))
        for c in SUMMED_TILE_COLUMNS:
            row.setdefault(c, sum(r[c] for r in got))
        out.append(row)
    return out


def fold_manual(manual_tile_rows: Iterable[dict], tile_rows: Iterable[dict],
                legacy_rows: Iterable[dict] = ()) -> list[dict]:
    """Fold `tile_manual_counts.csv` into one `manual_counts.csv` row per `(sample, image)`.

    An image counts as reviewed only once every one of its counted tiles has been reviewed, so a
    half-reviewed image is not silently treated as finished.

    `legacy_rows` are the per-image rows the pre-tiling review tool wrote straight into
    `manual_counts.csv`. They are passed through unchanged for any image that has no tile-level
    review, which keeps old output folders readable.
    """
    tiles = last_by(tile_rows, ("sample", "tile"))
    tile_to_image = {(r["sample"], r["tile"]): r["image"] for r in tiles}
    counted: dict[tuple[str, str], set[str]] = {}
    for r in tiles:
        if not r.get("skipped_empty"):
            counted.setdefault((r["sample"], r["image"]), set()).add(r["tile"])

    reviewed: dict[tuple[str, str], dict[str, dict]] = {}
    for r in last_by(manual_tile_rows, ("sample", "image")):
        sample, name = _text(r.get("sample")), _text(r.get("image"))
        if not sample or not name:
            continue
        image = tile_to_image.get((sample, name), name)
        reviewed.setdefault((sample, image), {})[name] = r

    out = []
    for key in sorted(reviewed):
        got = reviewed[key]
        want = counted.get(key) or set(got)
        if not want <= set(got):
            continue                                    # still tiles of this image to review
        rs = [got[t] for t in sorted(got)]
        notes = [r["note"] for r in rs if r.get("note")]
        people = sorted({r["reviewer"] for r in rs if r.get("reviewer")})
        out.append(dict(sample=key[0], image=key[1],
                        auto_count=sum(r["auto_count"] for r in rs),
                        removed=sum(r["removed"] for r in rs),
                        added=sum(r["added"] for r in rs),
                        final_count=sum(r["final_count"] for r in rs),
                        reviewer=";".join(people),
                        reviewed_at=max((r.get("reviewed_at") or "") for r in rs),
                        seconds=round(sum(r["seconds"] for r in rs)),
                        note="; ".join(notes), tiles=len(want),
                        tiles_reviewed=len(want & set(got))))
    for r in legacy_rows:
        key = (_text(r.get("sample")), _text(r.get("image")))
        if key in reviewed or not key[0]:
            continue
        out.append({**{c: r.get(c, "") for c in MANUAL_COUNTS_COLUMNS}, "sample": key[0],
                    "image": key[1], "tiles": "", "tiles_reviewed": ""})
    return out


def write_auto_counts_csv(path, rows: Iterable[dict]) -> Path:
    return write_csv_rows(path, AUTO_COUNTS_COLUMNS, rows)


def write_manual_counts_csv(path, rows: Iterable[dict]) -> Path:
    return write_csv_rows(path, MANUAL_COUNTS_COLUMNS, rows)
