"""axq list | suggest | run | aggregate"""

import argparse
import dataclasses
import json
import sys
import typing
from pathlib import Path

import pandas as pd

from .core.annotations import read_roiset, write_roiset
from .core.io import read_image, write_image
from .core.registry import load_tools
from .core.runs import find_runs, read_run, write_run


def parse_params(cls, pairs: list[str], json_path: str | None = None):
    """Build a Params dataclass from defaults, an optional params.json, then key=value overrides."""
    values = json.loads(Path(json_path).read_text()) if json_path else {}
    for pair in pairs:
        k, _, v = pair.partition("=")
        values[k.strip()] = v.strip()
    hints = typing.get_type_hints(cls)
    known = {f.name for f in dataclasses.fields(cls)}
    unknown = set(values) - known
    if unknown:
        raise SystemExit(f"unknown parameter(s): {', '.join(sorted(unknown))}. Known: {', '.join(sorted(known))}")
    return cls(**{k: coerce(hints[k], v) for k, v in values.items()})


def coerce(hint, v):
    if not isinstance(v, str):
        return tuple(v) if isinstance(v, list) else v
    origin = typing.get_origin(hint)
    if origin is tuple:
        inner = typing.get_args(hint)[0]
        return tuple(inner(x) for x in v.replace(";", ",").split(",") if x.strip())
    if hint is bool:
        return v.lower() in ("1", "true", "yes", "y")
    if hint in (int, float):
        return hint(v)
    return v


def main(argv=None):
    ap = argparse.ArgumentParser(prog="axq")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list installed tools and their parameters")

    def tool_args(p):
        p.add_argument("tool")
        p.add_argument("image")
        p.add_argument("--out", required=True)
        p.add_argument("--params", help="params.json from an earlier run")
        p.add_argument("--set", nargs="*", default=[], metavar="KEY=VALUE")
        p.add_argument("--channel", type=int, default=0)
        p.add_argument("--um-per-px", type=float, help="override pixel size (uncalibrated TIFFs)")
        p.add_argument("--hints", help="RoiSet.zip of hint shapes on the input image, e.g. a rough Centerline polyline")

    sp = sub.add_parser("suggest", help="propose annotations (and a straightened image) for review")
    tool_args(sp)
    rp = sub.add_parser("run", help="measure an image")
    tool_args(rp)
    rp.add_argument("--roiset", help="RoiSet.zip; omit to use suggest() automatically")
    ag = sub.add_parser("aggregate", help="collect metrics from many run folders into one long table")
    ag.add_argument("runs")
    ag.add_argument("--groups", help="CSV with columns image,group")
    ag.add_argument("-o", "--output", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "aggregate":
        df = aggregate(a.runs, a.groups)
        df.to_csv(a.output, index=False)
        print(f"{len(df)} rows from {df['run'].nunique() if len(df) else 0} runs -> {a.output}")
        return

    tools = load_tools()
    if a.cmd == "list":
        for name, t in tools.items():
            fields = ", ".join(f"{f.name}={f.default!r}" for f in dataclasses.fields(t.Params))
            print(f"{name}\n  {fields}")
        return

    tool = tools.get(a.tool) or sys.exit(f"unknown tool {a.tool!r}; installed: {', '.join(tools)}")
    params = parse_params(tool.Params, a.set, a.params)
    img = read_image(a.image, a.channel, a.um_per_px)
    out = Path(a.out)
    hints = read_roiset(a.hints) if a.hints else None

    if a.cmd == "suggest":
        simg, shapes = tool.suggest(img, params, hints)
        out.mkdir(parents=True, exist_ok=True)
        write_image(simg, out / f"{simg.name}.tif")
        write_roiset(shapes, out / f"{simg.name}_RoiSet.zip")
        print(f"review {out / (simg.name + '.tif')} with {out / (simg.name + '_RoiSet.zip')}, then run --roiset")
        return

    if a.roiset:
        shapes = read_roiset(a.roiset)
    else:
        img, shapes = tool.suggest(img, params, hints)
    result = tool.run(img, shapes, params)
    run_dir = write_run(out, tool.name, img, params, shapes, result)
    for k, v in result.metrics.items():
        print(f"{k}: {v:.4g}" if isinstance(v, float) else f"{k}: {v}")
    print(f"results: {run_dir}")


def aggregate(root: str, groups_csv: str | None = None) -> pd.DataFrame:
    rows = []
    for path in find_runs(root):
        r = read_run(path)
        prov = r["provenance"]
        for metric, value in r["metrics"].items():
            rows.append({"run": path.name, "image": prov["image"], "tool": prov["tool"], "metric": metric, "value": value})
    df = pd.DataFrame(rows, columns=["run", "image", "tool", "metric", "value"])
    if groups_csv:
        df = df.merge(pd.read_csv(groups_csv)[["image", "group"]], on="image", how="left")
    return df


if __name__ == "__main__":
    main()
