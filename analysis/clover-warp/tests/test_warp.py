import numpy as np
import pytest

from cloverwarp.warp import (
    AffineTransform,
    SimilarityTransform,
    ThinPlateSpline,
    fit,
    rmse,
)

RNG = np.random.default_rng(0)


def _points(n=25, scale=500.0):
    return RNG.uniform(0, scale, size=(n, 2))


def test_similarity_recovers_known_transform():
    src = _points()
    truth = SimilarityTransform(scale=1.3, rotation=0.4, translation=np.array([30.0, -12.0]))
    dst = truth(src)
    est = SimilarityTransform.estimate(src, dst)
    assert est.scale == pytest.approx(1.3, rel=1e-6)
    assert est.rotation == pytest.approx(0.4, abs=1e-6)
    assert rmse(est, src, dst) < 1e-8


def test_affine_recovers_shear():
    src = _points()
    M = np.array([[1.1, 0.25, 10.0], [-0.1, 0.9, -5.0], [0.0, 0.0, 1.0]])
    truth = AffineTransform(matrix=M)
    dst = truth(src)
    est = AffineTransform.estimate(src, dst)
    assert rmse(est, src, dst) < 1e-8


def test_tps_interpolates_control_points_exactly():
    src = _points(12)
    dst = src + RNG.normal(0, 20, size=src.shape)
    T = ThinPlateSpline.estimate(src, dst, smoothing=0.0)
    assert rmse(T, src, dst) < 1e-6


def test_tps_smoothing_trades_fit_for_bending():
    src = _points(20)
    dst = src + RNG.normal(0, 15, size=src.shape)
    exact = rmse(ThinPlateSpline.estimate(src, dst, 0.0), src, dst)
    smooth = rmse(ThinPlateSpline.estimate(src, dst, 1.0), src, dst)
    assert smooth > exact


def test_tps_reduces_to_affine_for_affine_data():
    """A TPS fitted to affine data should have ~zero non-affine weights."""
    src = _points(30)
    M = np.array([[1.05, 0.1, 3.0], [0.02, 0.98, -7.0], [0.0, 0.0, 1.0]])
    dst = AffineTransform(matrix=M)(src)
    T = ThinPlateSpline.estimate(src, dst, smoothing=0.0)
    assert np.abs(T.weights).max() < 1e-6


def test_jacobian_of_similarity_is_scale_squared():
    T = SimilarityTransform(scale=2.0, rotation=0.9)
    j = T.jacobian_determinant(_points(10))
    assert np.allclose(j, 4.0, rtol=1e-6)


def test_fit_falls_back_when_too_few_points():
    src = _points(2)
    dst = src * 1.5 + 3.0
    with pytest.warns(UserWarning, match="falling back"):
        T = fit(src, dst, model="tps")
    assert isinstance(T, SimilarityTransform)


def test_fit_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="same number"):
        fit(_points(5), _points(4))


def test_fit_rejects_unknown_model():
    with pytest.raises(ValueError, match="unknown model"):
        fit(_points(5), _points(5), model="elastic")
