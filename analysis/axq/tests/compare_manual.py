"""Compare automatic axon_density results against hand annotations.

    python tests/compare_manual.py data/annotations --raw data --out compare

Each subfolder of data/annotations is one nerve, named so it starts like its raw file (e.g. ON_000 -> data/ON_000_*.czi):
    straightened.tif   Fiji Straighten output (any name ending .tif)
    RoiSet.zip         straight lines Pre, Crush, Post_<d>um and a Background rectangle (as the v2 macro saves)
    counts.csv         optional: manual axon counts, columns distance_um,count
    um_per_px.txt      optional: pixel size, if the straightened TIFF lost its calibration

Writes compare/per_distance.csv and compare/summary.csv and prints the summary. What it measures:
    crush_error_um     auto crush suggestion on YOUR straightened image minus your Crush line (same coordinates)
    manual_pct         % of Pre with your ROIs on your straightened image (the v2 method's answer)
    manual_pct_zauto   same ROIs with per-position slice choice
    auto_pct           fully automatic: raw file -> straighten -> suggested lines -> measure
    manual_axons       axons crossing your lines (mean per included slice) on your straightened image
    auto_axons         axons crossing the suggested lines on the raw file (fully automatic)
"""

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from axq.core.annotations import find, read_roiset  # noqa: E402
from axq.core.io import read_image  # noqa: E402
from axq.tools.axon_density import AxonDensity, Params  # noqa: E402

TOOL = AxonDensity()


def post_pct(result) -> dict[float, float]:
    lines = result.tables["lines"]
    return {round(d): v for d, v in zip(lines.distance_um, lines.percent_of_pre) if d > 0}


def post_axons(result) -> dict[float, float]:
    c = result.tables.get("counts")
    if c is None:
        return {}
    return {round(d): v for d, v in zip(c.distance_um, c.axons_mean_per_slice) if d > 0}


def nearest(table: dict[float, float], d: float, tol: float = 30) -> float:
    if not table:
        return np.nan
    k = min(table, key=lambda x: abs(x - d))
    return table[k] if abs(k - d) <= tol else np.nan


def compare_nerve(folder: Path, raw_dir: Path | None, params: Params) -> tuple[list[dict], dict]:
    tif = next(p for p in sorted(folder.glob("*.tif*")))
    um = float((folder / "um_per_px.txt").read_text()) if (folder / "um_per_px.txt").exists() else None
    img = read_image(tif, um_per_px=um)
    shapes = read_roiset(folder / "RoiSet.zip")
    crush = find(shapes, "Crush")
    if crush is None or find(shapes, "Pre") is None:
        raise ValueError("RoiSet.zip needs straight lines named Pre and Crush")

    mres = TOOL.run(img, shapes, params)
    manual, manual_ax = post_pct(mres), post_axons(mres)
    manual_z = post_pct(TOOL.run(img, shapes, replace(params, z="auto")))

    _, sug = TOOL.suggest(img, replace(params, straighten=False))
    crush_err = (find(sug, "Crush").xy[0, 0] - crush.midpoint[0]) * img.um_per_px[0]
    # straighten=False keeps the user's frame unless it decided to flip; then compare from the other end
    if (find(sug, "Pre").xy[0, 0] < find(sug, "Crush").xy[0, 0]) != (find(shapes, "Pre").midpoint[0] < crush.midpoint[0]):
        crush_err = np.nan

    auto, auto_ax = {}, {}
    raw = next(iter(sorted(raw_dir.glob(f"{folder.name}*.czi")) + sorted(raw_dir.glob(f"{folder.name}*.tif")))) if raw_dir else None
    if raw is not None:
        rimg = read_image(raw)
        simg, sshapes = TOOL.suggest(rimg, params)
        ares = TOOL.run(simg, sshapes, params)
        auto, auto_ax = post_pct(ares), post_axons(ares)

    counts = {}
    if (folder / "counts.csv").exists():
        c = pd.read_csv(folder / "counts.csv")
        counts = dict(zip(c.distance_um.round(), c["count"]))

    rows = []
    for d in sorted(manual):
        rows.append({
            "nerve": folder.name, "distance_um": d,
            "manual_pct": manual[d], "manual_pct_zauto": manual_z.get(d, np.nan),
            "auto_pct": nearest(auto, d), "manual_axons": manual_ax.get(d, np.nan),
            "auto_axons": nearest(auto_ax, d), "manual_count": counts.get(d, np.nan),
        })
    summary = {"nerve": folder.name, "crush_error_um": crush_err, "raw_file": raw.name if raw else "",
               "auto_vs_manual_mean_abs_pct": float(np.nanmean([abs(r["auto_pct"] - r["manual_pct"]) for r in rows]))
               if auto else np.nan}
    return rows, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("annotations")
    ap.add_argument("--raw", help="folder with the raw .czi files")
    ap.add_argument("--out", default="compare")
    a = ap.parse_args()
    params = Params()
    rows, sums = [], []
    for folder in sorted(p for p in Path(a.annotations).iterdir() if p.is_dir()):
        try:
            r, s = compare_nerve(folder, Path(a.raw) if a.raw else None, params)
            rows += r
            sums.append(s)
        except Exception as e:  # report and continue with the other nerves
            print(f"{folder.name}: FAILED {type(e).__name__}: {e}")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    per = pd.DataFrame(rows)
    per.to_csv(out / "per_distance.csv", index=False)
    summ = pd.DataFrame(sums)
    if per["manual_count"].notna().sum() >= 3:
        ok = per.dropna(subset=["manual_count"])
        for col in ("manual_pct", "manual_pct_zauto", "auto_pct", "manual_axons", "auto_axons"):
            sub = ok.dropna(subset=[col])
            if len(sub) >= 3:
                summ.attrs[col] = sub[col].corr(sub["manual_count"])
    summ.to_csv(out / "summary.csv", index=False)
    pd.set_option("display.width", 160)
    print(per.round(1).to_string(index=False))
    print()
    print(summ.round(1).to_string(index=False))
    for col, r in summ.attrs.items():
        print(f"correlation of {col} with manual counts: r = {r:.2f}")


if __name__ == "__main__":
    main()
