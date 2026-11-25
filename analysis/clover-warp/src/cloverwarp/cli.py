"""Command-line interface. Four verbs, no cleverness.

    cloverwarp init-config  out.yaml --species rat
    cloverwarp manual       config.yaml --landmarks L1=L1.csv --landmarks L2=L2.csv
    cloverwarp auto         config.yaml
    cloverwarp selftest     --out results/selftest

``selftest`` runs the synthetic clover round-trip and prints the recovery
error. Run it after every change to the matcher, and quote its numbers --
not the fit residual -- when anyone asks how accurate this is.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from . import __version__


def _cmd_init_config(args) -> int:
    from .config import Config, write_config

    cfg = Config(dataset=args.dataset, species=args.species)
    write_config(cfg, args.out)
    print(f"wrote {args.out}")
    print("Next: fill in fa_image, flatmount_image, centroid_table, and")
    print("measure fa_disc_xy / fa_rim_radius_px on the FA image.")
    return 0


def _parse_landmarks(values) -> dict[str, str] | str | None:
    if not values:
        return None
    if len(values) == 1 and "=" not in values[0]:
        return values[0]
    out = {}
    for v in values:
        if "=" not in v:
            raise SystemExit(f"--landmarks expects PETAL=path.csv, got {v!r}")
        petal, path = v.split("=", 1)
        out[petal] = path
    return out


def _report(result) -> None:
    if not result.qc.empty:
        cols = ["petal", "n_landmarks", "rmse_px", "loo_rmse_px", "coverage_frac", "passed"]
        print(result.qc[[c for c in cols if c in result.qc]].to_string(index=False))
    for note in result.notes:
        print(f"  note: {note}")
    if result.rings is not None:
        print("\nring densities (cells/mm^2):")
        print(result.rings[["ring", "ecc_mid_mm", "n_cells", "density_per_mm2"]].to_string(index=False))


def _cmd_manual(args) -> int:
    from .config import load_config
    from .pipeline import run

    cfg = load_config(args.config)
    if args.outdir:
        cfg.outdir = args.outdir
    paths = _parse_landmarks(args.landmarks)
    if not paths:
        raise SystemExit("manual needs --landmarks")
    result = run(cfg, landmark_paths=paths)
    _report(result)
    print(f"\nwrote outputs to {cfg.outdir}")
    return 0 if result.passed_petals else 1


def _cmd_auto(args) -> int:
    from .config import load_config
    from .pipeline import run

    cfg = load_config(args.config)
    if args.outdir:
        cfg.outdir = args.outdir
    result = run(cfg)
    _report(result)
    print(f"\nwrote outputs to {cfg.outdir}")
    return 0 if result.passed_petals else 1


def _cmd_selftest(args) -> int:
    from .graph import bifurcation_descriptors, build_graph
    from .match import MatchParams, match_petal, refine_nonrigid, sector_mask
    from .synth import SynthConfig, make_clover, recovery_error
    from .vessels import VesselParams, segment

    cfg = SynthConfig(seed=args.seed, stretch=args.stretch)
    clover = make_clover(cfg)
    disc = clover.disc_xy
    vparams = VesselParams(scales_px=(2.0, 4.0, 8.0), min_object_px=16, closing_px=1)

    fa_mask, _ = segment(clover.fa_image, vparams)
    fa_graph = build_graph(fa_mask, disc_xy=disc, prune_px=8.0)
    fa_xy, fa_feats, _ = bifurcation_descriptors(fa_graph, disc_xy=disc)
    print(f"FA reference: {len(fa_xy)} bifurcations, {fa_graph.meta}")

    pmask, _ = segment(clover.petal_image, vparams)
    ys, xs = np.nonzero(pmask)
    width = 2 * np.pi / cfg.n_petals
    ang = np.arctan2(ys - disc[1], xs - disc[0]) % (2 * np.pi)
    sect = (ang / width).astype(int) % cfg.n_petals

    transforms, rows = {}, []
    for p in range(cfg.n_petals):
        sub = np.zeros_like(pmask)
        sel = sect == p
        if sel.sum() < 50:
            continue
        sub[ys[sel], xs[sel]] = True
        try:
            pg = build_graph(sub, disc_xy=disc, prune_px=8.0)
            p_xy, p_feats, _ = bifurcation_descriptors(pg, disc_xy=disc)
        except ValueError:
            continue
        if len(p_xy) == 0:
            continue
        allowed = (
            None
            if args.no_sector_prior
            else sector_mask(fa_xy, disc, p * width, (p + 1) * width, pad_rad=0.35)
        )
        mr = match_petal(
            str(p), p_xy, p_feats, fa_xy, fa_feats,
            MatchParams(min_inliers=args.min_inliers, seed=args.seed),
            fa_allowed=allowed,
        )
        rows.append((p, len(p_xy), mr.n_inliers, mr.ok))
        if mr.ok:
            T, _ = refine_nonrigid(mr, smoothing=1e-3)
            transforms[str(p)] = T

    for p, n, n_in, ok in rows:
        print(f"  petal {p}: {n} bifurcations, {n_in} inliers, ok={ok}")
    err = recovery_error(clover, transforms)
    print(
        "\nrecovery error vs ground truth"
        + (" (sector prior OFF)" if args.no_sector_prior else "")
        + ":"
    )
    print(json.dumps(err, indent=2, default=float))
    if not args.no_sector_prior:
        print(
            "\nCompare with --no-sector-prior to see why the prior matters: "
            "without it the matcher finds a confident consensus in the wrong "
            "sector of a rotationally near-symmetric tree."
        )

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "selftest.json").write_text(json.dumps(err, indent=2, default=float))
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(1, 2, figsize=(10, 5))
            axes[0].imshow(clover.fa_image, cmap="gray")
            axes[0].set_title("synthetic FA (reference)")
            axes[1].imshow(clover.petal_image, cmap="gray")
            axes[1].set_title("synthetic clover (distorted)")
            for ax in axes:
                ax.set_axis_off()
            fig.tight_layout()
            fig.savefig(out / "selftest.png", dpi=130)
            plt.close(fig)
            print(f"wrote {out/'selftest.png'}")
        except ImportError:
            pass
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cloverwarp",
        description="Reconstruct retinal clover flatmounts by registering "
        "each petal's vasculature to the eye's in vivo angiogram.",
    )
    p.add_argument("--version", action="version", version=f"cloverwarp {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("init-config", help="write a starter config file")
    q.add_argument("out", type=Path)
    q.add_argument("--dataset", default="untitled")
    q.add_argument("--species", default="rat", choices=["rat", "mouse"])
    q.set_defaults(func=_cmd_init_config)

    q = sub.add_parser("manual", help="register from BigWarp landmark CSVs")
    q.add_argument("config", type=Path)
    q.add_argument(
        "--landmarks",
        action="append",
        metavar="PETAL=CSV",
        help="repeatable; or a single native multi-petal CSV path",
    )
    q.add_argument("--outdir")
    q.set_defaults(func=_cmd_manual)

    q = sub.add_parser("auto", help="register by automatic vessel-graph matching")
    q.add_argument("config", type=Path)
    q.add_argument("--outdir")
    q.set_defaults(func=_cmd_auto)

    q = sub.add_parser("selftest", help="synthetic clover round-trip")
    q.add_argument("--seed", type=int, default=0)
    q.add_argument("--stretch", type=float, default=0.12)
    q.add_argument("--min-inliers", type=int, default=6)
    q.add_argument(
        "--no-sector-prior",
        action="store_true",
        help="disable the angular sector prior, to see the failure it prevents",
    )
    q.add_argument("--out", type=Path)
    q.set_defaults(func=_cmd_selftest)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
