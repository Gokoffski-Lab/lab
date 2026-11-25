"""Image loading, kept deliberately thin.

Confocal flatmount mosaics arrive as ``.lif`` (Leica) or ``.czi`` (Zeiss),
which need ``bioio`` / ``bioformats`` and are large enough that reading one
is a job in itself. Rather than hide that, this module reads OME-TIFF and
ordinary image formats natively and asks you to convert vendor files first
-- which you want anyway, because the stitched OME-TIFF is what the rest of
the lab's tools (ASHLAR, QuPath, ``rbpms-count``) already consume.

Convert once, up front::

    bfconvert -series 0 flatmount.lif flatmount.ome.tiff

and keep the OME-TIFF as the analysis input of record.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

__all__ = ["read_image", "read_channel", "available_backends"]


def available_backends() -> dict[str, bool]:
    """Report which optional readers are installed, for a startup banner."""
    out = {}
    for mod in ("tifffile", "imageio", "bioio", "aicsimageio"):
        try:
            __import__(mod)
            out[mod] = True
        except ImportError:
            out[mod] = False
    return out


def read_image(path, series: int = 0) -> np.ndarray:
    """Read an image, returning an array with channels last if present.

    Handles ``.tif/.tiff/.ome.tiff`` via tifffile and common 8-bit formats
    via imageio. Vendor formats are attempted through ``bioio`` if it happens
    to be installed, and otherwise raise with the conversion command above.
    """
    path = Path(path)
    suf = "".join(path.suffixes).lower()
    if not path.exists():
        raise FileNotFoundError(path)

    if suf.endswith((".tif", ".tiff")):
        import tifffile

        with tifffile.TiffFile(path) as tf:
            arr = tf.series[series].asarray() if tf.series else tf.asarray()
        return np.asarray(arr)

    if suf.endswith((".png", ".jpg", ".jpeg", ".bmp")):
        import imageio.v3 as iio

        return np.asarray(iio.imread(path))

    if suf.endswith((".lif", ".czi", ".nd2", ".oib", ".oif")):
        try:
            from bioio import BioImage
        except ImportError as exc:
            raise ImportError(
                f"{path.name} is a vendor format. Either install bioio "
                f"(pip install 'cloverwarp[vendor]') or convert it first:\n"
                f"  bfconvert -series {series} {path.name} "
                f"{path.with_suffix('').name}.ome.tiff"
            ) from exc
        img = BioImage(path)
        return np.asarray(img.get_image_data("CYX" if img.dims.C > 1 else "YX"))

    raise ValueError(f"unsupported image format: {path.name}")


def read_channel(path, channel: int, series: int = 0) -> np.ndarray:
    """Read one channel as a 2-D float array.

    Channel axis detection: an array with a dimension of size <= 8 that is
    not the last two is taken to be channels. Z stacks are max-projected,
    because for vessel topology and for RGC somata in a thin flatmount a
    maximum projection is what you want and a mean projection throws away
    thin vessels.
    """
    arr = np.asarray(read_image(path, series=series))
    if arr.ndim == 2:
        if channel not in (0, -1):
            raise ValueError(f"{path} is single-channel; asked for channel {channel}")
        return arr.astype(float)

    if arr.ndim == 3:
        if arr.shape[-1] <= 8 and arr.shape[0] > 8:  # YXC
            return arr[..., channel].astype(float)
        if arr.shape[0] <= 8:  # CYX
            return arr[channel].astype(float)
        return arr.max(axis=0).astype(float)  # ZYX, project

    if arr.ndim == 4:  # CZYX or ZCYX
        if arr.shape[0] <= 8:
            return arr[channel].max(axis=0).astype(float)
        if arr.shape[1] <= 8:
            return arr[:, channel].max(axis=0).astype(float)

    raise ValueError(f"cannot find a channel axis in array of shape {arr.shape}")
