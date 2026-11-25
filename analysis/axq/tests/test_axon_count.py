from dataclasses import replace

import numpy as np
import pytest

from axq.core.annotations import Shape, find, read_roiset, write_roiset
from axq.tools.axon_density import AxonDensity, Params
from tests.synth import nerve
from tests.synth.nerve import CRUSH_S, curved, make_axons, straight

P = Params(distances_um=(250, 500, 750, 1000), auc_max_um=1000)
DIST = (250, 500, 750, 1000)


@pytest.fixture(scope="module")
def spaced():
    axons = make_axons(n=120, spacing_px=6)
    img, shapes = straight(axons)
    return axons, img, shapes, AxonDensity().run(img, shapes, P)


def reaching(axons, d):
    return int((axons.length >= d).sum())


def test_counts_match_truth(spaced):
    axons, _, _, r = spaced
    c = r.tables["counts"].set_index("roi")
    assert c.loc["Pre", "axons_total"] == len(axons.length)
    for d in DIST:
        truth = reaching(axons, d)
        assert c.loc[f"Post_{d}um", "axons_total"] == pytest.approx(truth, abs=max(2, 0.05 * truth))
        assert r.metrics[f"axons_Post_{d}um"] == pytest.approx(c.loc[f"Post_{d}um", "axons_total"] / 8)


def test_counts_do_not_depend_on_pre(spaced):
    _, img, shapes, r = spaced
    moved = [Shape.line("Pre", 300, 40, 300, 260) if s.name == "Pre" else s for s in shapes]
    r2 = AxonDensity().run(img, moved, P)
    for d in DIST:
        assert r2.metrics[f"axons_Post_{d}um"] == r.metrics[f"axons_Post_{d}um"]


def test_counts_survive_straightening():
    """Counts on the auto-straightened curved nerve, at lines placed from the TRUE crush.

    Crush detection is tested separately (test_straighten); on evenly spaced axons it is not reliable yet,
    so this test keeps the two apart.
    """
    axons = make_axons(n=120, spacing_px=6)
    simg, sug = AxonDensity().suggest(curved(axons), P)
    pos, _ = nerve.centerline(np.arange(0, nerve.LENGTH, 0.5))
    true_crush = nerve.centerline(np.array([CRUSH_S]))[0][0] - (pos.min(0) - 150)
    cl = find(sug, "Centerline_source_px").xy
    crush_x = float(np.argmin(np.linalg.norm(cl - true_crush, axis=1)) * max(1, simg.shape[2] // 500))
    (_, y0), (_, y1) = find(sug, "Crush").xy
    shapes = [Shape.line("Pre", crush_x - 300, y0, crush_x - 300, y1), Shape.line("Crush", crush_x, y0, crush_x, y1),
              find(sug, "Background")]
    shapes += [Shape.line(f"Post_{d}um", crush_x + d, y0, crush_x + d, y1) for d in DIST]
    c = AxonDensity().run(simg, shapes, P).tables["counts"].set_index("roi")
    tol = 25  # the true-crush column is only known to within the centerline sampling step
    for d in DIST:
        n = c.loc[f"Post_{d}um", "axons_total"]
        assert reaching(axons, d + tol) - 3 <= n <= reaching(axons, d - tol) + 3


def test_overlays_mark_counted_axons(spaced, tmp_path):
    axons, _, shapes, r = spaced
    pts = [s for s in r.overlays if s.name.startswith("Axons_Post_250um_")]
    assert sum(len(s.xy) for s in pts) == r.tables["counts"].set_index("roi").loc["Post_250um", "axons_total"]
    x = find(shapes, "Post_250um").xy[0, 0]
    assert all(np.allclose(s.xy[:, 0], x, atol=1) for s in pts)
    write_roiset(r.overlays, tmp_path / "o.zip")
    back = read_roiset(tmp_path / "o.zip")
    assert [s.name for s in back] == [s.name for s in r.overlays]
    assert all(b.kind == "points" and len(b.xy) == len(a.xy) for a, b in zip(r.overlays, back))


def test_sigma_ad_only_when_thickness_given(spaced):
    _, img, shapes, r = spaced
    assert "sigma_ad" not in r.tables["counts"]
    r2 = AxonDensity().run(img, shapes, replace(P, section_thickness_um=14))
    row = r2.tables["counts"].set_index("roi").loc["Post_250um"]
    r_mm = row.line_length_um / 2000
    assert row.sigma_ad == pytest.approx(np.pi * r_mm**2 * row.axons_per_mm_width / 0.014)


def test_count_off(spaced):
    _, img, shapes, _ = spaced
    r = AxonDensity().run(img, shapes, replace(P, count=False))
    assert "counts" not in r.tables and not r.overlays


