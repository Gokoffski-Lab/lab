from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from axq.core.annotations import read_roiset, write_roiset
from axq.tools.axon_density import AxonDensity, Params
from tests.synth.nerve import make_axons, straight

GOLDEN = Path(__file__).parent / "golden"
P = Params(distances_um=(250, 500, 750, 1000), auc_max_um=1000)
P_V2 = Params(distances_um=(250, 500, 750, 1000), auc_max_um=1000, z="pre")  # same slice rule as the v2 macro


@pytest.fixture(scope="module")
def straight_run():
    axons = make_axons()
    img, shapes = straight(axons)
    return axons, AxonDensity().run(img, shapes, P)


def test_matches_v2_macro():
    img, shapes = straight(make_axons())
    r = AxonDensity().run(img, shapes, P_V2)
    gold = pd.read_csv(GOLDEN / "v2_straight_summary.csv").set_index("roi")
    ours = r.tables["lines"].set_index("roi")
    assert list(ours.index) == list(gold.index)
    assert (ours["percent_of_pre"] - gold["percent_of_pre"]).abs().max() < 0.5
    gm = pd.read_csv(GOLDEN / "v2_straight_curve_metrics.csv").set_index("metric")["value"]
    assert r.metrics["auc_250_1000_um"] == pytest.approx(float(gm.iloc[0]), rel=0.01)
    assert r.metrics["reach_um_at_0.25_of_pre"] == pytest.approx(float(gm.iloc[2]), abs=2)


def test_matches_ground_truth(straight_run):
    axons, r = straight_run
    for d in (250, 500, 750, 1000):
        assert r.metrics[f"pct_pre_Post_{d}um"] == pytest.approx(100 * axons.truth(d), abs=3)


def test_nerve_not_flat_in_z():
    """Distal half of the nerve sits 2 slices deeper; per-position slice choice must still find it."""
    axons = make_axons()
    img, shapes = straight(axons)
    tilted = img.data.copy()
    tilted[:, :, 1500:] = np.roll(tilted[:, :, 1500:], 2, axis=0)
    img = img.with_data(tilted)
    auto = AxonDensity().run(img, shapes, replace(P, z="auto"))
    pre_rule = AxonDensity().run(img, shapes, P_V2)
    for d in (500, 750, 1000):
        assert auto.metrics[f"pct_pre_Post_{d}um"] == pytest.approx(100 * axons.truth(d), abs=3)
    assert pre_rule.metrics["pct_pre_Post_1000um"] < 0.8 * auto.metrics["pct_pre_Post_1000um"]


def test_drops_slices_outside_nerve(straight_run):
    _, r = straight_run
    assert r.tables["per_slice"]["included"].tolist() == [0, 0] + [1] * 8 + [0, 0]


def test_roiset_round_trip(tmp_path):
    _, shapes = straight(make_axons())
    write_roiset(shapes, tmp_path / "r.zip")
    back = read_roiset(tmp_path / "r.zip")
    assert [s.name for s in back] == [s.name for s in shapes]
    for a, b in zip(shapes, back):
        assert a.kind == b.kind
        assert abs(a.xy - b.xy).max() < 1e-6
