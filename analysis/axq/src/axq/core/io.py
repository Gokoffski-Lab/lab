import warnings
from pathlib import Path

import numpy as np
import tifffile

from .image import Image


def read_image(path: str | Path, channel: int = 0, um_per_px: float | None = None) -> Image:
    """um_per_px overrides the file's calibration (needed for uncalibrated TIFFs, e.g. Fiji Straighten output)."""
    path = Path(path)
    if path.suffix.lower() == ".czi":
        data, um = _read_czi(path, channel)
    else:
        with tifffile.TiffFile(path) as tf:
            data = _to_zyx(tf.asarray(), tf.series[0].axes, channel)
            um = _tiff_um_per_px(tf)
    if um_per_px:
        um = (um_per_px, um_per_px)
    elif um is None:
        warnings.warn(f"{path.name} has no pixel calibration; treating 1 px as 1 um. Pass um_per_px.", stacklevel=2)
        um = (1.0, 1.0)
    return Image(data, um, path.stem, str(path))


def write_image(img: Image, path: str | Path) -> None:
    tifffile.imwrite(
        path,
        img.data,
        imagej=True,
        resolution=(1 / img.um_per_px[0], 1 / img.um_per_px[1]),
        metadata={"axes": "ZYX", "unit": "um"},
    )


def _to_zyx(data: np.ndarray, axes: str, channel: int) -> np.ndarray:
    axes = axes.upper()
    for ax in "TS":
        if ax in axes and data.shape[axes.index(ax)] > 1:
            raise ValueError(f"image has more than one {ax} position; expected a single z-stack")
    if "C" in axes:
        data = np.take(data, channel, axis=axes.index("C"))
        axes = axes.replace("C", "")
    for ax in reversed(axes):
        if ax not in "ZYX":
            data = data.squeeze(axis=axes.index(ax))
            axes = axes.replace(ax, "")
    if "Z" not in axes:
        data = data[None]
    return data


def _tiff_um_per_px(tf: tifffile.TiffFile) -> tuple[float, float] | None:
    """Micrometres per pixel, or None when the file carries no physical calibration."""
    page = tf.pages[0]
    if "XResolution" not in page.tags or "YResolution" not in page.tags:
        return None
    xr, yr = page.tags["XResolution"].value, page.tags["YResolution"].value
    x, y = xr[1] / xr[0], yr[1] / yr[0]
    if tf.is_imagej:
        unit = (tf.imagej_metadata or {}).get("unit", "")
        # ImageJ stores the micro sign as the character or as the escaped text \u00B5m
        scale = {"um": 1, "micron": 1, "microns": 1, "\u00B5m": 1, r"\u00B5m": 1, "nm": 1e-3, "mm": 1e3}
        if unit not in scale:
            return None
        return (x * scale[unit], y * scale[unit])
    unit_tag = page.tags.get("ResolutionUnit")
    if unit_tag is not None and unit_tag.value == 3:  # centimeter
        return (x * 1e4, y * 1e4)
    return None  # inch or no unit: a display resolution, not a physical one


def _read_czi(path: Path, channel: int) -> tuple[np.ndarray, tuple[float, float] | None]:
    try:
        from bioio import BioImage
    except ImportError as e:
        raise ImportError("reading .czi needs the czi extra: pip install axq[czi]") from e
    bi = BioImage(path)
    data = bi.get_image_data("ZYX", T=0, C=channel)
    ps = bi.physical_pixel_sizes
    return data, ((float(ps.X), float(ps.Y)) if ps.X and ps.Y else None)
