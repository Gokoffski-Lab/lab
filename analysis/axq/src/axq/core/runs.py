"""One folder per (tool, image) run. Every tool writes the same layout, so aggregation works across tools."""

import dataclasses
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd

from .. import __version__
from .annotations import Shape, write_roiset
from .image import Image
from .tool import Result


def params_to_dict(params) -> dict:
    return {k: list(v) if isinstance(v, tuple) else v for k, v in dataclasses.asdict(params).items()}


def params_from_dict(cls, d: dict):
    fields = {f.name: f for f in dataclasses.fields(cls)}
    kw = {}
    for k, v in d.items():
        if k in fields:
            kw[k] = tuple(v) if isinstance(v, list) else v
    return cls(**kw)


def write_run(out_root: str | Path, tool: str, img: Image, params, shapes: list[Shape], result: Result) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(out_root) / tool / f"{img.name}_{stamp}"
    n = 1
    while out.exists():
        out = Path(out_root) / tool / f"{img.name}_{stamp}_{n}"
        n += 1
    (out / "tables").mkdir(parents=True)
    for name, df in result.tables.items():
        df.to_csv(out / "tables" / f"{name}.csv", index=False)
    write_roiset(shapes, out / "RoiSet.zip")
    if result.overlays:
        write_roiset(result.overlays, out / "overlays.zip")
    (out / "metrics.json").write_text(json.dumps(result.metrics, indent=2))
    (out / "params.json").write_text(json.dumps(params_to_dict(params), indent=2))
    (out / "provenance.json").write_text(json.dumps(_provenance(tool, img), indent=2))
    return out


def read_run(path: str | Path) -> dict:
    path = Path(path)
    return {
        "path": path,
        "provenance": json.loads((path / "provenance.json").read_text()),
        "params": json.loads((path / "params.json").read_text()),
        "metrics": json.loads((path / "metrics.json").read_text()),
        "tables": {p.stem: pd.read_csv(p) for p in (path / "tables").glob("*.csv")},
    }


def find_runs(root: str | Path) -> list[Path]:
    return sorted(p.parent for p in Path(root).rglob("provenance.json"))


def _provenance(tool: str, img: Image) -> dict:
    return {
        "tool": tool,
        "axq_version": __version__,
        "git_sha": _git_sha(),
        "image": img.name,
        "source": img.source,
        "source_sha256": _sha256(img.source),
        "shape_zyx": list(img.shape),
        "um_per_px": list(img.um_per_px),
        "created": datetime.now().isoformat(timespec="seconds"),
    }


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _sha256(path: str) -> str:
    if not path or not Path(path).is_file():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
