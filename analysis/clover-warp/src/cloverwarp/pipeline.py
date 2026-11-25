"""The two entry points: manual landmarks, and automatic vessel matching.

:func:`register_from_landmarks` is the path to use first and the path that
defines correctness. It needs no segmentation, no graph, no matcher -- just a
BigWarp CSV per petal -- and it will give usable retinal coordinates on the
Weston clovers this afternoon.

:func:`register_automatic` is the same pipeline with the landmark-clicking
replaced by vessel-graph matching. It exists to scale, and its output is
only believable to the extent it reproduces the manual result on the same
retinas. Build the manual path's results first; they are the training and
test set for the automatic one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import graph as graphmod
from . import io as iomod
from . import landmarks as lm
from . import match as matchmod
from . import petals as petalmod
from . import points as pointsmod
from . import qc as qcmod
from . import vessels as vesselmod
from .config import Config, write_config
from .frames import RetinalFrame
from .warp import Transform, fit

__all__ = ["Result", "register_from_landmarks", "register_automatic", "build_frame"]


@dataclass
class Result:
    """Everything one retina produces."""

    dataset: str
    transforms: dict[str, Transform] = field(default_factory=dict)
    landmarks: dict[str, lm.LandmarkSet] = field(default_factory=dict)
    qc: pd.DataFrame = field(default_factory=pd.DataFrame)
    centroids: pd.DataFrame | None = None
    rings: pd.DataFrame | None = None
    quadrants: pd.DataFrame | None = None
    frame: RetinalFrame | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def passed_petals(self) -> list[str]:
        if self.qc.empty:
            return []
        return list(self.qc.loc[self.qc["passed"], "petal"].astype(str))

    def write(self, outdir) -> Path:
        """Write every table to ``outdir``. Returns the directory."""
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        if not self.qc.empty:
            self.qc.to_csv(outdir / f"{self.dataset}_qc.csv", index=False)
        if self.landmarks:
            lm.write_native_csv(
                outdir / f"{self.dataset}_landmarks.csv", self.landmarks
            )
        if self.centroids is not None:
            self.centroids.to_csv(
                outdir / f"{self.dataset}_cells_retinal.csv", index=False
            )
        if self.rings is not None:
            self.rings.to_csv(outdir / f"{self.dataset}_ring_density.csv", index=False)
        if self.quadrants is not None:
            self.quadrants.to_csv(
                outdir / f"{self.dataset}_quadrants.csv", index=False
            )
        if self.notes:
            (outdir / f"{self.dataset}_notes.txt").write_text(
                "\n".join(self.notes) + "\n"
            )
        return outdir


def build_frame(cfg: Config, fa_image: np.ndarray | None = None) -> RetinalFrame:
    """Construct the retinal coordinate frame from config, inferring what it can.

    The two calibration numbers -- disc position and rim radius in FA pixels
    -- should be measured once per eye and written into config. They are
    inferred from the FA image only as a convenience for a first look; an
    inferred disc is routinely off by enough to matter.
    """
    disc = cfg.fa_disc_xy
    rim = cfg.fa_rim_radius_px
    if (disc is None or rim is None) and fa_image is not None:
        tm = petalmod.tissue_mask(fa_image)
        if disc is None:
            disc = petalmod.disc_from_mask(tm.mask).tolist()
        if rim is None:
            ys, xs = np.nonzero(tm.mask)
            rim = float(
                np.percentile(np.hypot(xs - disc[0], ys - disc[1]), 99)
            )
    if disc is None or rim is None:
        raise ValueError(
            "need fa_disc_xy and fa_rim_radius_px in config, or an FA image "
            "to infer them from"
        )
    return RetinalFrame.from_rim(
        disc_xy=disc,
        rim_radius_px=rim,
        projection=cfg.projection,
        eye=cfg.eye,
    )


def _finish(
    cfg: Config,
    result: Result,
    petal_masks: dict[str, np.ndarray] | None = None,
) -> Result:
    """Shared tail: QC every petal, then transfer and summarise centroids."""
    rows = []
    for petal, ls in result.landmarks.items():
        T = result.transforms.get(petal)
        if T is None:
            continue
        mask = (petal_masks or {}).get(petal)
        rows.append(
            qcmod.petal_report(
                ls,
                T,
                petal_mask=mask,
                model=cfg.warp_model,
                smoothing=cfg.warp_smoothing,
                min_landmarks=cfg.gates.min_landmarks,
                max_loo_px=cfg.gates.max_loo_px,
                max_stretch=cfg.gates.max_stretch,
                min_coverage=cfg.gates.min_coverage,
            ).as_dict()
        )
    result.qc = pd.DataFrame(rows)

    if cfg.centroid_table:
        cells = pointsmod.read_centroids(
            cfg.centroid_table, scale_to_px=cfg.centroid_scale_to_px
        )
        # only petals that passed QC contribute coordinates
        usable = {
            k: v for k, v in result.transforms.items() if k in set(result.passed_petals)
        }
        dropped = sorted(set(result.transforms) - set(usable))
        if dropped:
            result.notes.append(
                f"petals excluded by QC, cells left unmapped: {', '.join(dropped)}"
            )
        mapped = pointsmod.transfer(cells, usable, result.frame)
        result.centroids = mapped
        n_unmapped = int(mapped["fa_x"].isna().sum())
        if n_unmapped:
            result.notes.append(f"{n_unmapped} cells unmapped of {len(mapped)}")
        if mapped["fa_x"].notna().any():
            result.rings = pointsmod.ring_density(
                mapped, result.frame, n_rings=cfg.n_rings
            )
            result.quadrants = pointsmod.quadrant_summary(mapped, result.frame)
    return result


def register_from_landmarks(cfg: Config, landmark_paths: dict[str, str] | str) -> Result:
    """Register petals using hand-placed correspondences.

    ``landmark_paths`` is either a mapping ``{petal_id: csv_path}`` of
    BigWarp exports, or a single path to a native multi-petal CSV.
    """
    result = Result(dataset=cfg.dataset)
    fa = iomod.read_image(cfg.fa_image) if cfg.fa_image else None
    result.frame = build_frame(cfg, fa)

    if isinstance(landmark_paths, (str, Path)):
        sets = lm.read_csv(landmark_paths)
    else:
        sets = {}
        for petal, path in landmark_paths.items():
            sets[str(petal)] = lm.read_bigwarp_csv(path, petal=str(petal))
    result.landmarks = sets

    for petal, ls in sets.items():
        try:
            result.transforms[petal] = fit(
                ls.petal_xy,
                ls.fa_xy,
                model=cfg.warp_model,
                smoothing=cfg.warp_smoothing,
            )
        except ValueError as exc:
            result.notes.append(f"petal {petal}: {exc}")

    return _finish(cfg, result)


def register_automatic(cfg: Config) -> Result:
    """Register petals by matching vessel-bifurcation graphs to the FA.

    Stages, each of which writes something a human can check:
    segment tissue -> split petals -> segment vessels in both modalities ->
    build rooted graphs -> descriptors -> propose + RANSAC -> TPS on the
    verified inliers -> QC.

    Petals that fail the gates are reported with their inlier counts so they
    can be sent to :func:`register_from_landmarks` individually; the usual
    mixed workflow is "automatic for the clean petals, hand-clicked for the
    two that tore".
    """
    if not cfg.fa_image or not cfg.flatmount_image:
        raise ValueError("register_automatic needs both fa_image and flatmount_image")

    result = Result(dataset=cfg.dataset)
    fa = iomod.read_image(cfg.fa_image)
    if fa.ndim == 3:
        fa = fa.mean(axis=-1)
    result.frame = build_frame(cfg, fa)

    # --- FA reference graph ------------------------------------------------
    fa_mask, _ = vesselmod.segment(fa, cfg.vessels)
    fa_graph = graphmod.build_graph(fa_mask, disc_xy=result.frame.disc_xy)
    fa_xy, fa_feats, _ = graphmod.bifurcation_descriptors(fa_graph)
    result.notes.append(f"FA reference: {len(fa_xy)} bifurcations")
    if len(fa_xy) < cfg.matching.min_inliers:
        result.notes.append(
            "FA has too few bifurcations to match against; check "
            "vessels.scales_px against the FA pixel size"
        )
        return _finish(cfg, result)

    # --- petals ------------------------------------------------------------
    tissue_img = iomod.read_channel(cfg.flatmount_image, cfg.tissue_channel)
    vessel_img = iomod.read_channel(cfg.flatmount_image, cfg.vessel_channel)
    tm = petalmod.tissue_mask(tissue_img)
    split = petalmod.split_petals(tm.mask, n_petals=cfg.n_petals)
    result.notes.append(
        f"split into {split.n_petals} petals; disc at "
        f"({split.disc_xy[0]:.0f}, {split.disc_xy[1]:.0f})"
    )

    # Each petal's angular sector, from the relief cuts. This is the prior
    # that stops a petal being matched into a structurally similar but wrong
    # sector of the FA; see match.sector_mask for why it matters so much.
    cuts = np.asarray(split.cut_angles, dtype=float)
    sectors: dict[str, tuple[float, float]] = {}
    if len(cuts) >= 2:
        for i, label in enumerate(range(1, split.n_petals + 1)):
            lo = cuts[i % len(cuts)]
            hi = cuts[(i + 1) % len(cuts)]
            if hi <= lo:
                hi += 2 * np.pi
            sectors[str(label)] = (float(lo), float(hi))

    petal_masks: dict[str, np.ndarray] = {}
    for label in range(1, split.n_petals + 1):
        petal = str(label)
        pmask = split.labels == label
        if not pmask.any():
            continue
        petal_masks[petal] = pmask
        vmask, _ = vesselmod.segment(np.where(pmask, vessel_img, 0), cfg.vessels)
        if not vmask.any():
            result.notes.append(f"petal {petal}: empty vessel mask, skipped")
            continue
        try:
            pg = graphmod.build_graph(vmask, disc_xy=split.disc_xy)
        except ValueError as exc:
            result.notes.append(f"petal {petal}: {exc}")
            continue
        p_xy, p_feats, _ = graphmod.bifurcation_descriptors(pg)
        if len(p_xy) == 0:
            result.notes.append(f"petal {petal}: no bifurcations found")
            continue

        allowed = None
        if petal in sectors:
            lo, hi = sectors[petal]
            allowed = matchmod.sector_mask(
                fa_xy, result.frame.disc_xy, lo, hi, pad_rad=cfg.sector_pad_rad
            )
            if allowed.sum() < cfg.matching.min_inliers:
                result.notes.append(
                    f"petal {petal}: sector prior left only {int(allowed.sum())} "
                    f"FA candidates; widening to the whole FA"
                )
                allowed = None

        mr = matchmod.match_petal(
            petal, p_xy, p_feats, fa_xy, fa_feats, cfg.matching, fa_allowed=allowed
        )
        result.notes.append(
            f"petal {petal}: {len(p_xy)} bifurcations, "
            f"{mr.n_proposed} proposals, {mr.n_inliers} inliers"
            + (f" -- {mr.reason}" if mr.reason else "")
        )
        if not mr.ok:
            continue
        result.landmarks[petal] = mr.landmarks
        T, err = matchmod.refine_nonrigid(
            mr, model=cfg.warp_model, smoothing=cfg.warp_smoothing
        )
        result.transforms[petal] = T

    return _finish(cfg, result, petal_masks)


def run(cfg: Config, landmark_paths=None) -> Result:
    """Dispatch, write outputs, and copy the resolved config beside them."""
    result = (
        register_from_landmarks(cfg, landmark_paths)
        if landmark_paths
        else register_automatic(cfg)
    )
    outdir = Path(cfg.outdir)
    result.write(outdir)
    write_config(cfg, outdir / f"{cfg.dataset}_config_used.yaml")
    return result
