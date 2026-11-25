"""Vessel segmentation, for both modalities.

Two very different images have to yield comparable vessel masks:

* the **FA / fundus** image -- single channel, low contrast, vignetted,
  often with a bright disc and choroidal background;
* the **confocal flatmount** vessel channel -- high SNR, but the vessel
  stain depends entirely on what was used (isolectin GS-IB4, collagen IV,
  CD31, or in the cheapest case the autofluorescence that already rides
  along in the RBPMS or CTB channel).

The classical route (Frangi vesselness on a contrast-normalised image) is
implemented and is the default, because it needs no training data and its
failure modes are legible. A learned route is left as a hook: fundus-trained
vessel networks (DRIVE/AutoMorph lineage) transfer poorly to rodent FA and
not at all to confocal flatmounts, so fine-tuning on your own images is the
only honest option, and that is a second project. Do not reach for it until
Frangi has been shown to be the limiting factor.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from skimage import exposure, filters, morphology
from skimage.util import img_as_float

from ._compat import binary_closing, remove_small_objects

__all__ = ["VesselParams", "segment", "segment_frangi", "segment_learned"]


@dataclass
class VesselParams:
    """Knobs for :func:`segment_frangi`.

    ``scales_px``
        Expected vessel half-widths in pixels, smallest first. Set these
        from your actual pixel size: at 0.5 um/px a 6 um capillary is ~6 px
        across, a 40 um arteriole ~80 px. Getting this wrong is the single
        most common reason the mask looks like noise.
    ``clip_limit``
        CLAHE strength for contrast normalisation; 0 disables it.
    ``threshold``
        ``"otsu"``, ``"li"``, or a float in [0, 1] applied to the
        vesselness response.
    ``min_object_px`` / ``closing_px``
        Cleanup. Keep these small: aggressive cleanup removes exactly the
        thin terminal branches that make a bifurcation graph distinctive.
    ``invert``
        Set True when vessels are *dark* on a light background, which is the
        usual case for red-free fundus photographs but not for FA.
    """

    scales_px: tuple[float, ...] = (2.0, 4.0, 8.0, 16.0)
    clip_limit: float = 0.02
    threshold: str | float = "otsu"
    min_object_px: int = 64
    closing_px: int = 2
    invert: bool = False


def _prepare(image: np.ndarray, params: VesselParams) -> np.ndarray:
    img = img_as_float(np.asarray(image))
    if img.ndim == 3:
        img = img.mean(axis=-1)
    if img.ndim != 2:
        raise ValueError(f"expected a 2-D image, got shape {img.shape}")
    finite = np.isfinite(img)
    if not finite.all():
        img = np.nan_to_num(img, nan=float(np.nanmedian(img)))
    lo, hi = np.percentile(img, (0.5, 99.5))
    if hi > lo:
        img = np.clip((img - lo) / (hi - lo), 0, 1)
    if params.invert:
        img = 1.0 - img
    if params.clip_limit > 0:
        img = exposure.equalize_adapthist(img, clip_limit=params.clip_limit)
    return img


def vesselness(image: np.ndarray, params: VesselParams | None = None) -> np.ndarray:
    """Multiscale Frangi vesselness response, normalised to [0, 1]."""
    params = params or VesselParams()
    img = _prepare(image, params)
    sigmas = [s / 2.0 for s in params.scales_px]
    resp = filters.frangi(img, sigmas=sigmas, black_ridges=False)
    m = resp.max()
    return resp / m if m > 0 else resp


def segment_frangi(
    image: np.ndarray, params: VesselParams | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(mask, vesselness)``.

    The vesselness map is returned alongside the mask on purpose: the graph
    builder uses it to weight branch confidence, and a QC overlay of the
    continuous response tells you far more about a bad segmentation than the
    binarised mask does.
    """
    params = params or VesselParams()
    resp = vesselness(image, params)
    if isinstance(params.threshold, (int, float)):
        thr = float(params.threshold)
    elif params.threshold == "otsu":
        thr = filters.threshold_otsu(resp)
    elif params.threshold == "li":
        thr = filters.threshold_li(resp)
    else:
        raise ValueError(f"unknown threshold {params.threshold!r}")
    mask = resp > thr
    if params.closing_px > 0:
        mask = binary_closing(mask, morphology.disk(params.closing_px))
    if params.min_object_px > 0:
        mask = remove_small_objects(mask, params.min_object_px)
    return mask, resp


def segment_learned(image: np.ndarray, model_path) -> tuple[np.ndarray, np.ndarray]:
    """Hook for a fine-tuned segmentation network.

    Deliberately unimplemented. When it is time for this, the sequence is:
    label ~20 FA images and ~20 flatmount vessel-channel crops using the
    Frangi mask as a starting point, fine-tune a small U-Net or a Cellpose
    model per modality, and keep the Frangi path as the fallback and as the
    comparator in :mod:`cloverwarp.qc`. Train on HPC3, not the analysis PC.
    """
    raise NotImplementedError(
        "learned vessel segmentation is not implemented; "
        "use segment_frangi until it is the measured bottleneck"
    )


def segment(
    image: np.ndarray,
    params: VesselParams | None = None,
    model_path=None,
) -> tuple[np.ndarray, np.ndarray]:
    """Dispatch to the learned path if a model is given, else Frangi."""
    if model_path is not None:
        return segment_learned(image, model_path)
    return segment_frangi(image, params)
