import numpy as np
import pytest

from axq.core.annotations import Shape, find
from axq.tools.axon_density import AxonDensity, Params
from tests.synth import nerve

P = Params(distances_um=(250, 500, 750, 1000), auc_max_um=1000)


@pytest.fixture(scope="module")
def runs():
    axons = nerve.make_axons()
    tool = AxonDensity()
    simg, shapes = tool.suggest(nerve.curved(axons), P)
    ref_img, ref_shapes = nerve.straight(axons, autofluor=20)
    return simg, shapes, tool.run(simg, shapes, P), tool.run(ref_img, ref_shapes, P)


def test_crush_found_where_it_is(runs):
    simg, shapes, _, _ = runs
    pos, _ = nerve.centerline(np.arange(0, nerve.LENGTH, 0.5))
    off = pos.min(0) - 150
    true_crush = nerve.centerline(np.array([nerve.CRUSH_S]))[0][0] - off
    cl = find(shapes, "Centerline_source_px").xy
    step = max(1, simg.shape[2] // 500)
    true_col = np.argmin(np.linalg.norm(cl - true_crush, axis=1)) * step
    assert abs(find(shapes, "Crush").xy[0, 0] - true_col) <= 25


def test_curved_matches_straight(runs):
    _, _, curved, straight = runs
    for d in (250, 500, 750, 1000):
        key = f"pct_pre_Post_{d}um"
        assert curved.metrics[key] == pytest.approx(straight.metrics[key], abs=3)


def test_rough_guide_gives_same_result(runs):
    _, _, auto, _ = runs
    axons = nerve.make_axons()
    raw = nerve.curved(axons)
    pos, _ = nerve.centerline(np.arange(0, nerve.LENGTH, 300.0))
    off = nerve.centerline(np.arange(0, nerve.LENGTH, 0.5))[0].min(0) - 150
    clicks = pos - off + np.random.default_rng(0).normal(0, 15, pos.shape)  # one click every 300 um, +-15 px
    tool = AxonDensity()
    simg, shapes = tool.suggest(raw, P, hints=[Shape("Centerline", "polyline", clicks)])
    guided = tool.run(simg, shapes, P)
    for d in (250, 500, 750, 1000):
        key = f"pct_pre_Post_{d}um"
        assert guided.metrics[key] == pytest.approx(auto.metrics[key], abs=3)


def test_suggests_background_outside_nerve(runs):
    simg, shapes, _, _ = runs
    bg = find(shapes, "Background")
    assert bg is not None
    rows = slice(int(bg.xy[:, 1].min()), int(bg.xy[:, 1].max()))
    assert simg.data[:, rows].mean() < 130  # noise floor ~108; nerve tissue >= 128
