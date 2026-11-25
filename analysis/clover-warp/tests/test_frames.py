import numpy as np
import pytest

from cloverwarp.frames import (
    PROJECTION_MAX_DEG,
    PROJECTIONS,
    RAT_EYE,
    EyeGeometry,
    RetinalFrame,
)


@pytest.fixture
def frame():
    return RetinalFrame.from_rim(disc_xy=(500.0, 400.0), rim_radius_px=440.0)


@pytest.mark.parametrize("projection", sorted(PROJECTIONS))
def test_roundtrip_fa_to_retinal(projection):
    """Every projection must round-trip within its own declared domain."""
    rim_deg = min(80.0, PROJECTION_MAX_DEG[projection] - 5.0)
    eye = EyeGeometry("test", retinal_radius_mm=3.0, rim_eccentricity_deg=rim_deg)
    f = RetinalFrame.from_rim((300.0, 300.0), 250.0, projection=projection, eye=eye)
    pts = np.array([[300.0, 300.0], [380.0, 340.0], [190.0, 420.0], [420.0, 220.0]])
    back = f.to_fa(f.to_retinal(pts))
    assert np.allclose(back, pts, atol=1e-6)


def test_narrow_field_projection_refused_for_whole_retina():
    """A rat clover reaches past 100 deg; gnomonic cannot describe that."""
    with pytest.raises(ValueError, match="cannot represent eccentricities"):
        RetinalFrame.from_rim((0.0, 0.0), 400.0, projection="gnomonic", eye=RAT_EYE)


def test_disc_is_zero_eccentricity(frame):
    ret = frame.to_retinal(frame.disc_xy[None, :])
    assert ret[0, 0] == pytest.approx(0.0, abs=1e-9)


def test_rim_radius_maps_to_rim_eccentricity(frame):
    rim_pt = frame.disc_xy + np.array([440.0, 0.0])
    ret = frame.to_retinal(rim_pt[None, :])
    assert ret[0, 0] == pytest.approx(RAT_EYE.rim_eccentricity, rel=1e-6)
    assert frame.in_bounds(ret)[0]


def test_beyond_rim_is_out_of_bounds(frame):
    pt = frame.disc_xy + np.array([600.0, 0.0])
    assert not frame.in_bounds(frame.to_retinal(pt[None, :]))[0]


def test_meridian_angles(frame):
    offsets = np.array([[100.0, 0.0], [0.0, 100.0], [-100.0, 0.0]])
    ret = frame.to_retinal(frame.disc_xy + offsets)
    assert ret[0, 1] == pytest.approx(0.0, abs=1e-9)
    assert ret[1, 1] == pytest.approx(np.pi / 2, abs=1e-9)
    assert abs(ret[2, 1]) == pytest.approx(np.pi, abs=1e-9)


def test_cartesian3d_lies_on_sphere(frame):
    ret = frame.to_retinal(
        frame.disc_xy + np.array([[0.0, 0.0], [200.0, 100.0], [-300.0, 50.0]])
    )
    xyz = frame.to_cartesian3d(ret)
    r = np.linalg.norm(xyz, axis=1)
    assert np.allclose(r, RAT_EYE.retinal_radius_mm, rtol=1e-9)


def test_area_element_is_finite_at_disc_and_periphery(frame):
    ret = np.array([[0.0, 0.0], [0.5, 0.0], [1.5, 1.0]])
    a = frame.area_element_mm2(ret)
    assert np.all(np.isfinite(a))
    assert np.all(a > 0)


def test_area_element_grows_with_eccentricity_for_equidistant(frame):
    """For azimuthal equidistant, mm^2 per pixel falls off toward the rim."""
    ret = np.column_stack([np.linspace(0.05, 1.5, 12), np.zeros(12)])
    a = frame.area_element_mm2(ret)
    assert np.all(np.diff(a) < 0)


def test_quadrant_labels_cover_all_four(frame):
    ang = np.linspace(0, 2 * np.pi, 40, endpoint=False)
    ret = np.column_stack([np.full_like(ang, 0.5), ang])
    q = frame.quadrant(ret)
    assert set(np.unique(q)) == {0, 1, 2, 3}


def test_arclength_scales_with_radius():
    eye = EyeGeometry("test", retinal_radius_mm=2.0, rim_eccentricity_deg=90.0)
    assert eye.arclength_mm(np.pi / 2) == pytest.approx(np.pi)


def test_bad_projection_rejected():
    with pytest.raises(ValueError, match="unknown projection"):
        RetinalFrame((0, 0), 100.0, projection="mercator")


def test_bad_scale_rejected():
    with pytest.raises(ValueError, match="positive"):
        RetinalFrame((0, 0), 0.0)
