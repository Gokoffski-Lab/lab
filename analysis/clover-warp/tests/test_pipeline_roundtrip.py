"""End-to-end checks on synthetic data, where the answer is known.

These are the tests that matter. The unit tests above verify that the
algebra is right; these verify that the *pipeline* recovers positions it was
not told, which is the only claim anyone cares about.
"""

import numpy as np
import pandas as pd
import pytest

from cloverwarp.config import Config
from cloverwarp.frames import RetinalFrame
from cloverwarp.graph import bifurcation_descriptors, build_graph
from cloverwarp.landmarks import LandmarkSet, read_csv, write_native_csv
from cloverwarp.match import (
    MatchParams,
    match_petal,
    propose,
    ransac_similarity,
    sector_mask,
)
from cloverwarp.petals import disc_from_mask, split_petals, tissue_mask
from cloverwarp.pipeline import register_from_landmarks
from cloverwarp.points import ring_density, transfer
from cloverwarp.qc import leave_one_out_rmse, petal_report
from cloverwarp.synth import SynthConfig, make_clover, recovery_error
from cloverwarp.vessels import VesselParams, segment
from cloverwarp.warp import SimilarityTransform, fit

VP = VesselParams(scales_px=(2.0, 4.0, 8.0), min_object_px=16, closing_px=1)


# --- synthetic data sanity -------------------------------------------------

@pytest.fixture(scope="module")
def clover():
    return make_clover(SynthConfig(seed=3))


def test_synthetic_clover_has_matched_truth(clover):
    assert len(clover.fa_points) == len(clover.petal_points)
    assert len(clover.petal_id) == len(clover.fa_points)
    assert len(clover.fa_points) > 50
    # the distortion actually moved things
    d = np.linalg.norm(clover.petal_points - clover.fa_points, axis=1)
    assert d.mean() > 1.0


def test_vessel_segmentation_finds_the_tree(clover):
    mask, resp = segment(clover.fa_image, VP)
    assert mask.sum() > 0.005 * mask.size
    assert resp.max() == pytest.approx(1.0, rel=1e-6)


def test_graph_is_connected_and_rooted(clover):
    mask, _ = segment(clover.fa_image, VP)
    g = build_graph(mask, disc_xy=clover.disc_xy, prune_px=8.0)
    assert g.root is not None
    assert g.graph.number_of_nodes() > 10
    depths = [g.graph.nodes[n]["depth"] for n in g.graph.nodes]
    assert max(depths) >= 1
    assert all(d >= 0 for d in depths)


def test_descriptors_exclude_position(clover):
    mask, _ = segment(clover.fa_image, VP)
    g = build_graph(mask, disc_xy=clover.disc_xy, prune_px=8.0)
    xy, feats, ids = bifurcation_descriptors(g)
    assert len(xy) == len(feats) == len(ids)
    if len(feats):
        assert feats.shape[1] == 10
        # no feature should correlate ~perfectly with raw x or y
        for col in range(feats.shape[1]):
            if np.std(feats[:, col]) < 1e-9:
                continue
            for axis in range(2):
                r = abs(np.corrcoef(feats[:, col], xy[:, axis])[0, 1])
                assert r < 0.999


# --- matching --------------------------------------------------------------

def test_ransac_finds_inliers_among_decoys():
    rng = np.random.default_rng(1)
    good_src = rng.uniform(0, 400, size=(30, 2))
    T = SimilarityTransform(scale=1.1, rotation=0.2, translation=np.array([15.0, -8.0]))
    good_dst = T(good_src) + rng.normal(0, 2.0, size=good_src.shape)
    bad_src = rng.uniform(0, 400, size=(40, 2))
    bad_dst = rng.uniform(0, 400, size=(40, 2))
    src = np.vstack([good_src, bad_src])
    dst = np.vstack([good_dst, bad_dst])
    mask, est = ransac_similarity(src, dst, MatchParams(ransac_threshold_px=12.0, seed=2))
    assert est is not None
    # most of the true pairs recovered, few of the decoys accepted
    assert mask[:30].sum() >= 25
    assert mask[30:].sum() <= 8


def test_propose_is_symmetric_in_size():
    rng = np.random.default_rng(4)
    a = rng.normal(size=(10, 10))
    b = rng.normal(size=(20, 10))
    pairs = propose(a, b, MatchParams(k=3))
    assert pairs.shape == (30, 2)
    assert pairs[:, 0].max() < 10 and pairs[:, 1].max() < 20


def test_propose_handles_empty_input():
    assert propose(np.zeros((0, 10)), np.zeros((5, 10))).shape == (0, 2)


def _auto_match(clover, use_sector_prior: bool):
    """Shared body: run the automatic matcher over a synthetic clover."""
    fa_mask, _ = segment(clover.fa_image, VP)
    fg = build_graph(fa_mask, disc_xy=clover.disc_xy, prune_px=8.0)
    fa_xy, fa_feats, _ = bifurcation_descriptors(fg)

    p_mask, _ = segment(clover.petal_image, VP)
    n = clover.config.n_petals
    ys, xs = np.nonzero(p_mask)
    ang = np.arctan2(ys - clover.disc_xy[1], xs - clover.disc_xy[0]) % (2 * np.pi)
    sect = (ang / (2 * np.pi / n)).astype(int) % n
    width = 2 * np.pi / n

    transforms = {}
    for p in range(n):
        sub = np.zeros_like(p_mask)
        sel = sect == p
        if sel.sum() < 50:
            continue
        sub[ys[sel], xs[sel]] = True
        pg = build_graph(sub, disc_xy=clover.disc_xy, prune_px=8.0)
        p_xy, p_feats, _ = bifurcation_descriptors(pg)
        if len(p_xy) < 3:
            continue
        allowed = (
            sector_mask(fa_xy, clover.disc_xy, p * width, (p + 1) * width, pad_rad=0.35)
            if use_sector_prior
            else None
        )
        mr = match_petal(
            str(p), p_xy, p_feats, fa_xy, fa_feats,
            MatchParams(min_inliers=4, ransac_threshold_px=45.0, seed=0),
            fa_allowed=allowed,
        )
        if mr.ok and len(mr.landmarks) >= 3:
            transforms[str(p)] = fit(
                mr.landmarks.petal_xy, mr.landmarks.fa_xy, "tps", smoothing=1e-2
            )
    return transforms


def test_automatic_matching_recovers_synthetic_positions(clover):
    """The headline test: match without ground truth, then score against it."""
    transforms = _auto_match(clover, use_sector_prior=True)
    assert transforms, "matcher produced no usable transform on synthetic data"
    err = recovery_error(clover, transforms)
    # Loose bound on purpose: this guards against regression to nonsense, not
    # against a specific accuracy. Tighten it once measured on real data.
    assert err["median_px"] < 40.0, err


def test_sector_prior_is_what_makes_matching_work(clover):
    """Documents the dominant failure mode rather than hiding it.

    Without the sector prior the matcher finds a self-consistent consensus in
    the wrong sector of a rotationally near-symmetric tree: the fit looks
    fine and the positions are badly wrong. If this test ever starts failing
    because the unconstrained matcher got good, that is excellent news -- but
    check it deliberately rather than loosening the prior by accident.
    """
    with_prior = recovery_error(clover, _auto_match(clover, True))
    without = recovery_error(clover, _auto_match(clover, False))
    assert with_prior["median_px"] < without["median_px"]


def test_sector_mask_wraps_through_zero():
    disc = np.array([0.0, 0.0])
    pts = np.array([[1.0, 0.1], [1.0, -0.1], [-1.0, 0.0], [0.0, 1.0]])
    m = sector_mask(pts, disc, -0.2, 0.2, pad_rad=0.05)
    assert m[0] and m[1]
    assert not m[2] and not m[3]


# --- petal splitting -------------------------------------------------------

def _disc_blob(size=400, n_petals=4, radius=150):
    """A clover-shaped tissue mask: petals joined at the centre."""
    yy, xx = np.mgrid[0:size, 0:size]
    c = size / 2
    r = np.hypot(xx - c, yy - c)
    a = np.arctan2(yy - c, xx - c)
    lobe = radius * (0.72 + 0.28 * np.abs(np.cos(n_petals * a / 2)))
    return r < lobe


def test_tissue_mask_and_disc():
    mask = _disc_blob()
    tm = tissue_mask(mask.astype(float), smooth_px=2.0, close_px=3)
    assert tm.mask.sum() > 0
    disc = disc_from_mask(tm.mask)
    assert np.allclose(disc, [200, 200], atol=25)


def test_split_petals_gives_requested_count():
    mask = _disc_blob(n_petals=4)
    split = split_petals(mask, n_petals=4)
    assert split.n_petals == 4
    sizes = [int((split.labels == i).sum()) for i in range(1, 5)]
    assert min(sizes) > 0.1 * mask.sum()


def test_split_petals_eight():
    mask = _disc_blob(n_petals=8, radius=170)
    split = split_petals(mask, n_petals=8)
    assert split.n_petals == 8


# --- landmarks, QC, and the manual path -----------------------------------

def test_bigwarp_csv_roundtrip(tmp_path):
    p = tmp_path / "L1.csv"
    p.write_text(
        '"Pt-0","true",10.0,20.0,12.0,23.0\n'
        '"Pt-1","true",30.0,40.0,33.0,44.0\n'
        '"Pt-2","false",50.0,60.0,55.0,66.0\n'   # inactive, dropped
        '"Pt-3","true",70.0,80.0,,\n'            # incomplete, dropped
    )
    sets = read_csv(p)
    ls = sets["L1"]
    assert len(ls) == 2
    assert ls.labels == ["Pt-0", "Pt-1"]
    out = write_native_csv(tmp_path / "all.csv", ls)
    again = read_csv(out)
    assert len(again["L1"]) == 2


def test_landmark_length_mismatch_rejected():
    with pytest.raises(ValueError, match="petal points"):
        LandmarkSet("x", np.zeros((3, 2)), np.zeros((2, 2)))


def test_loo_rmse_exceeds_in_sample_for_noisy_landmarks():
    rng = np.random.default_rng(7)
    src = rng.uniform(0, 300, size=(14, 2))
    dst = src * 1.05 + rng.normal(0, 6, size=src.shape)
    ls = LandmarkSet("p", src, dst)
    assert leave_one_out_rmse(ls) > 1e-3


def test_qc_flags_a_folded_warp():
    """A deliberately inconsistent landmark set should fail the gates."""
    rng = np.random.default_rng(11)
    src = rng.uniform(0, 200, size=(10, 2))
    dst = src.copy()
    dst[0] += 500.0  # one wildly wrong correspondence
    ls = LandmarkSet("bad", src, dst)
    T = fit(src, dst, "tps", smoothing=0.0)
    mask = np.ones((220, 220), dtype=bool)
    qc = petal_report(ls, T, petal_mask=mask)
    assert not qc.passed
    assert qc.notes


def test_manual_pipeline_end_to_end(tmp_path):
    """Config -> landmark CSVs -> transforms -> retinal coords -> ring table."""
    rng = np.random.default_rng(13)
    disc = np.array([400.0, 400.0])

    # two petals, each a known similarity away from the FA frame
    truths = {
        "L1": SimilarityTransform(1.08, 0.05, np.array([6.0, -4.0])),
        "L2": SimilarityTransform(0.95, -0.08, np.array([-5.0, 7.0])),
    }
    paths = {}
    for petal, T in truths.items():
        fa_pts = disc + rng.uniform(-250, 250, size=(14, 2))
        # invert: petal coords are what map forward onto the FA points
        petal_pts = np.linalg.solve(
            np.array([[T.scale * np.cos(T.rotation), -T.scale * np.sin(T.rotation)],
                      [T.scale * np.sin(T.rotation), T.scale * np.cos(T.rotation)]]),
            (fa_pts - T.translation).T,
        ).T
        lines = [
            f'"{i}","true",{px},{py},{fx},{fy}'
            for i, ((px, py), (fx, fy)) in enumerate(zip(petal_pts, fa_pts, strict=True))
        ]
        p = tmp_path / f"{petal}.csv"
        p.write_text("\n".join(lines) + "\n")
        paths[petal] = str(p)

    # centroids in petal coordinates
    cells = []
    for petal in truths:
        pts = disc + rng.uniform(-200, 200, size=(60, 2))
        cells.append(pd.DataFrame({"petal": petal, "x": pts[:, 0], "y": pts[:, 1]}))
    cell_csv = tmp_path / "cells.csv"
    pd.concat(cells).to_csv(cell_csv, index=False)

    cfg = Config(
        dataset="synthtest",
        species="rat",
        fa_disc_xy=[400.0, 400.0],
        fa_rim_radius_px=380.0,
        centroid_table=str(cell_csv),
        warp_model="tps",
        warp_smoothing=0.0,
        outdir=str(tmp_path / "out"),
    )
    result = register_from_landmarks(cfg, paths)

    assert set(result.transforms) == {"L1", "L2"}
    assert not result.qc.empty
    assert result.qc["rmse_px"].max() < 1e-3        # exact landmarks, exact fit
    assert set(result.passed_petals) == {"L1", "L2"}
    assert result.centroids is not None
    assert result.centroids["fa_x"].notna().all()
    assert result.rings is not None
    assert result.rings["n_cells"].sum() > 0
    assert (result.rings["density_per_mm2"].dropna() >= 0).all()

    outdir = result.write(tmp_path / "out")
    assert (outdir / "synthtest_qc.csv").exists()
    assert (outdir / "synthtest_cells_retinal.csv").exists()


def test_transfer_keeps_unmapped_cells_visible():
    frame = RetinalFrame.from_rim((100.0, 100.0), 90.0)
    cells = pd.DataFrame({"petal": ["A", "A", "B"], "x": [10.0, 20.0, 30.0], "y": [10.0, 20.0, 30.0]})
    out = transfer(cells, {"A": SimilarityTransform()}, frame)
    assert len(out) == 3
    assert out["fa_x"].isna().sum() == 1  # petal B had no transform


def test_ring_density_areas_sum_to_spherical_cap():
    frame = RetinalFrame.from_rim((0.0, 0.0), 100.0)
    df = pd.DataFrame(
        {"eccentricity_rad": np.linspace(0.0, frame.eye.rim_eccentricity * 0.99, 100)}
    )
    rings = ring_density(df, frame, n_rings=6)
    R = frame.eye.retinal_radius_mm
    expected = 2 * np.pi * R**2 * (1 - np.cos(frame.eye.rim_eccentricity))
    assert rings["area_mm2"].sum() == pytest.approx(expected, rel=1e-9)
    assert rings["n_cells"].sum() == 100
