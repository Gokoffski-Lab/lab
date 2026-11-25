"""Visual QC of automatic straightening on real nerves (not a pytest test).

    python tests/qc_real.py data/ON_000_YYMMDD.czi [more files...] --out qc

For each image writes <name>_qc.png: raw max projection with nerve outline, centerline and suggested
Crush/Pre positions; the straightened projection with every suggested line; the signal-vs-distance curve.
Prints the run metrics so files can be compared.
"""

import argparse
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from axq.core.annotations import Shape, find  # noqa: E402
from axq.core.io import read_image  # noqa: E402
from axq.tools.axon_density import AxonDensity, Params  # noqa: E402
from axq.tools.axon_density.straighten import nerve_mask  # noqa: E402


def stretch(a):
    lo, hi = np.percentile(a, (1, 99.7))
    return np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1)


def qc(path: Path, out: Path, params: Params, um_per_px: float | None = None, guide=None):
    t0 = time.time()
    img = read_image(path, um_per_px=um_per_px)
    t1 = time.time()
    tool = AxonDensity()
    simg, shapes = tool.suggest(img, params, guide)
    t2 = time.time()
    res = tool.run(simg, shapes, params)
    t3 = time.time()

    mip = img.data.max(0)
    pw = float(np.mean(img.um_per_px))
    mask = nerve_mask(img.data.mean(0), params.blur_um / pw) if params.straighten else None
    cl = find(shapes, "Centerline_source_px")
    smip = simg.data.max(0)
    curve = res.tables["curve"]

    fig, ax = plt.subplots(3, 1, figsize=(16, 11), gridspec_kw={"height_ratios": [2, 1.2, 1]})
    ax[0].imshow(stretch(np.log1p(img.data.mean(0))), cmap="gray", aspect="equal")
    if mask is not None:
        ax[0].contour(mask, levels=[0.5], colors="cyan", linewidths=0.6)
    if cl is not None:
        ax[0].plot(cl.xy[:, 0], cl.xy[:, 1], "y-", lw=1)
        step = max(1, simg.shape[2] // 500)
        for name, color in (("Crush", "r"), ("Pre", "lime")):
            i = int(find(shapes, name).xy[0, 0]) // step
            i = min(i, len(cl.xy) - 1)
            ax[0].plot(*cl.xy[i], "o", color=color, ms=8)
    ax[0].set_title(f"{path.name}: raw max projection, nerve outline (cyan), centerline (yellow), Crush (red), Pre (green)")
    ax[1].imshow(stretch(smip), cmap="gray", aspect="auto")
    for s in shapes:
        if s.kind == "line":
            c = "r" if s.name == "Crush" else "lime" if s.name == "Pre" else "orange"
            ax[1].plot(s.xy[:, 0], s.xy[:, 1], color=c, lw=1)
        elif s.name == "Background":
            xy = np.vstack([s.xy, s.xy[:1]])
            ax[1].plot(xy[:, 0], xy[:, 1], "c--", lw=1)
    ax[1].set_title("straightened max projection with suggested lines (Background dashed)")
    ax[2].plot(curve.distance_um, curve.fraction_of_pre_smoothed, "k-", lw=1)
    ax[2].axvline(0, color="r", lw=0.8)
    ax[2].set_xlabel("distance from suggested crush (um)")
    ax[2].set_ylabel("fraction of Pre")
    ax[2].set_ylim(-0.05, 1.5)
    fig.tight_layout()
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{path.stem}_qc.png", dpi=80)
    plt.close(fig)

    lines = res.tables["lines"]
    print(f"\n== {path.name}  raw {img.shape} um/px {img.um_per_px[0]:.3f}  straight {simg.shape}")
    print(f"   read {t1 - t0:.0f}s  suggest {t2 - t1:.0f}s  run {t3 - t2:.0f}s  slices {res.metrics['slices_included']}/{res.metrics['slices_total']}")
    print("   " + "  ".join(f"{r.roi}({r.distance_um:.0f})={r.percent_of_pre:.1f}%" for r in lines.itertuples()))
    print(f"   reach25={res.metrics['reach_um_at_0.25_of_pre']:.0f}um  reach10={res.metrics['reach_um_at_0.1_of_pre']:.0f}um")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", default="qc")
    ap.add_argument("--no-straighten", action="store_true")
    ap.add_argument("--um-per-px", type=float)
    ap.add_argument("--guide", help="rough centerline clicks in raw px: x,y;x,y;...")
    a = ap.parse_args()
    params = Params(straighten=not a.no_straighten)
    for p in a.images:
        try:
            guide = None
            if a.guide:
                xy = np.array([[float(v) for v in pt.split(",")] for pt in a.guide.split(";")])
                guide = [Shape("Centerline", "polyline", xy)]
            qc(Path(p), Path(a.out), params, a.um_per_px, guide)
        except Exception as e:  # keep going across files; report which failed
            print(f"\n== {Path(p).name}  FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
