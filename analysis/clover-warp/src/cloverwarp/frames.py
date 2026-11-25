"""Coordinate frames and the sphere <-> plane projections between them.

Three frames matter in this pipeline:

``petal``
    Pixel coordinates of one petal, in the confocal flatmount image (or a
    crop of the stitched mosaic). Each petal has its own frame because each
    petal was flattened independently.

``fa``
    Pixel coordinates of the in vivo fundus / fluorescein angiography image
    of the same eye. This is the **common 2-D frame**: the FA shows the
    vascular tree *uncut and unstretched*, so it is the reference every
    petal is registered into. Reassembly of the clover is a by-product of
    each petal landing correctly in this frame.

``retinal``
    Angular position on the retinal sphere: ``eccentricity`` (great-circle
    angle from the optic disc, radians) and ``meridian`` (angle around the
    disc, radians, measured from the image +x axis of the FA). Converting to
    this frame is what makes counts comparable across animals and across
    eyes of different size, and it is the frame Retistruct-style outputs and
    isodensity maps live in.

The FA image is treated as a projection of the retinal sphere centred on
the optic disc. Which projection is correct depends on the camera; the model
is therefore pluggable and the choice is a config field, not a hard-coded
assumption. For small fields all four agree to within a few percent, so this
only starts to matter in the far periphery -- which, for a clover flatmount,
is exactly where the petal tips are.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "PROJECTIONS",
    "EyeGeometry",
    "RetinalFrame",
    "RAT_EYE",
    "MOUSE_EYE",
]


# --- projection pairs: angular eccentricity (rad) <-> normalised radius ----
#
# Each pair maps a great-circle angle from the projection centre to a radius
# in units of the sphere radius. ``forward`` is sphere -> plane.

def _azimuthal_equidistant_fwd(a):
    return a


def _azimuthal_equidistant_inv(r):
    return r


def _gnomonic_fwd(a):
    return np.tan(np.clip(a, 0, np.pi / 2 - 1e-6))


def _gnomonic_inv(r):
    return np.arctan(r)


def _orthographic_fwd(a):
    return np.sin(np.clip(a, 0, np.pi / 2))


def _orthographic_inv(r):
    return np.arcsin(np.clip(r, -1.0, 1.0))


def _stereographic_fwd(a):
    return 2.0 * np.tan(np.clip(a, 0, np.pi - 1e-6) / 2.0)


def _stereographic_inv(r):
    return 2.0 * np.arctan(r / 2.0)


PROJECTIONS = {
    "azimuthal_equidistant": (_azimuthal_equidistant_fwd, _azimuthal_equidistant_inv),
    "gnomonic": (_gnomonic_fwd, _gnomonic_inv),
    "orthographic": (_orthographic_fwd, _orthographic_inv),
    "stereographic": (_stereographic_fwd, _stereographic_inv),
}

#: Largest eccentricity each projection can represent, in degrees. This is not
#: a detail: a rat retina extends past 100 deg from the disc, so gnomonic and
#: orthographic -- which both blow up or fold at 90 deg -- simply cannot
#: describe a whole clover. They are offered for narrow-field fundus cameras
#: and for comparison, and the frame refuses to be built if the eye's rim lies
#: outside the projection's domain rather than silently clipping the periphery.
PROJECTION_MAX_DEG = {
    "azimuthal_equidistant": 180.0,
    "gnomonic": 85.0,
    "orthographic": 89.0,
    "stereographic": 175.0,
}


@dataclass(frozen=True)
class EyeGeometry:
    """Species-level eye parameters.

    ``retinal_radius_mm``
        Radius of the sphere the retina lies on. Not the axial length: for a
        rat eye of ~6.3 mm axial length the retinal radius is ~3.0 mm.
    ``rim_eccentricity_deg``
        Great-circle angle from the optic disc to the retinal rim (the far
        edge of the petal tips). Sets the outer bound of valid eccentricity
        and is what a petal tip should map to. Measure this on your own
        flatmounts rather than trusting the default.
    """

    name: str
    retinal_radius_mm: float
    rim_eccentricity_deg: float

    @property
    def rim_eccentricity(self) -> float:
        return float(np.deg2rad(self.rim_eccentricity_deg))

    def arclength_mm(self, eccentricity_rad) -> np.ndarray:
        """Great-circle distance from the disc, in mm along the retina."""
        return self.retinal_radius_mm * np.asarray(eccentricity_rad, dtype=float)


# Defaults are literature order-of-magnitude starting points, NOT measured
# values for your colony. Override them in config and record what you used.
RAT_EYE = EyeGeometry("rat", retinal_radius_mm=3.0, rim_eccentricity_deg=105.0)
MOUSE_EYE = EyeGeometry("mouse", retinal_radius_mm=1.7, rim_eccentricity_deg=110.0)


@dataclass
class RetinalFrame:
    """Maps FA pixel coordinates to retinal spherical coordinates.

    Parameters
    ----------
    disc_xy
        Optic disc centre in FA pixel coordinates.
    px_per_unit_radius
        FA pixels corresponding to one unit of projected radius (i.e. one
        sphere radius). Calibrate this from a feature at known eccentricity:
        in practice, the retinal rim. If the rim sits ``r_rim`` pixels from
        the disc, then ``px_per_unit_radius = r_rim / forward(rim_ecc)``.
        :meth:`from_rim` does that for you.
    projection
        Key into :data:`PROJECTIONS`.
    eye
        :class:`EyeGeometry` for the species.
    """

    disc_xy: np.ndarray
    px_per_unit_radius: float
    projection: str = "azimuthal_equidistant"
    eye: EyeGeometry = RAT_EYE

    def __post_init__(self):
        self.disc_xy = np.asarray(self.disc_xy, dtype=float).reshape(2)
        if self.projection not in PROJECTIONS:
            raise ValueError(
                f"unknown projection {self.projection!r}; "
                f"choose from {sorted(PROJECTIONS)}"
            )
        if not np.isfinite(self.px_per_unit_radius) or self.px_per_unit_radius <= 0:
            raise ValueError("px_per_unit_radius must be positive and finite")
        limit = PROJECTION_MAX_DEG[self.projection]
        if self.eye.rim_eccentricity_deg > limit:
            raise ValueError(
                f"projection {self.projection!r} cannot represent eccentricities "
                f"beyond {limit:g} deg, but {self.eye.name} rim is at "
                f"{self.eye.rim_eccentricity_deg:g} deg. Use "
                f"'azimuthal_equidistant' or 'stereographic' for a whole-retina "
                f"flatmount, or reduce rim_eccentricity_deg if you are only "
                f"registering a central field."
            )

    @classmethod
    def from_rim(
        cls,
        disc_xy,
        rim_radius_px: float,
        projection: str = "azimuthal_equidistant",
        eye: EyeGeometry = RAT_EYE,
    ) -> RetinalFrame:
        """Calibrate from the disc position and the rim radius in FA pixels."""
        fwd, _ = PROJECTIONS[projection]
        scale = float(rim_radius_px) / float(fwd(eye.rim_eccentricity))
        return cls(disc_xy, scale, projection=projection, eye=eye)

    # --- conversions -------------------------------------------------------

    def to_retinal(self, fa_xy: np.ndarray) -> np.ndarray:
        """FA pixels -> ``(eccentricity, meridian)`` in radians, shape (N, 2)."""
        p = np.asarray(fa_xy, dtype=float).reshape(-1, 2) - self.disc_xy
        r_px = np.hypot(p[:, 0], p[:, 1])
        meridian = np.arctan2(p[:, 1], p[:, 0])
        _, inv = PROJECTIONS[self.projection]
        ecc = inv(r_px / self.px_per_unit_radius)
        return np.column_stack([ecc, meridian])

    def to_fa(self, retinal: np.ndarray) -> np.ndarray:
        """``(eccentricity, meridian)`` in radians -> FA pixels, shape (N, 2)."""
        a = np.asarray(retinal, dtype=float).reshape(-1, 2)
        fwd, _ = PROJECTIONS[self.projection]
        r_px = fwd(a[:, 0]) * self.px_per_unit_radius
        return np.column_stack(
            [
                self.disc_xy[0] + r_px * np.cos(a[:, 1]),
                self.disc_xy[1] + r_px * np.sin(a[:, 1]),
            ]
        )

    def to_cartesian3d(self, retinal: np.ndarray) -> np.ndarray:
        """``(eccentricity, meridian)`` -> 3-D points on the sphere, in mm.

        The disc sits at the +z pole. Useful for writing a surface mesh or
        for handing coordinates to Retistruct-style downstream code.
        """
        a = np.asarray(retinal, dtype=float).reshape(-1, 2)
        R = self.eye.retinal_radius_mm
        ecc, mer = a[:, 0], a[:, 1]
        return np.column_stack(
            [
                R * np.sin(ecc) * np.cos(mer),
                R * np.sin(ecc) * np.sin(mer),
                R * np.cos(ecc),
            ]
        )

    def area_element_mm2(self, retinal: np.ndarray) -> np.ndarray:
        """mm^2 on the retinal sphere per FA pixel, at each point.

        Multiply a count-per-pixel density by this to get a true retinal
        density in cells/mm^2. This is the correction that stops peripheral
        RGC densities from being systematically wrong, and it is the main
        reason to carry an explicit projection model instead of counting in
        flat pixels.

        Derivation: on the sphere ``dA = R^2 sin(e) de dm``; in the projected
        plane ``dA = s^2 f(e) f'(e) de dm`` with ``s`` pixels per unit
        radius. The ratio is ``R^2 sin(e) / (s^2 f(e) f'(e))``, which tends
        to ``R^2 / s^2`` at the disc.
        """
        a = np.asarray(retinal, dtype=float).reshape(-1, 2)
        ecc = np.clip(a[:, 0], 0.0, None)
        fwd, _ = PROJECTIONS[self.projection]
        h = 1e-5
        f = fwd(ecc)
        df = (fwd(ecc + h) - fwd(np.maximum(ecc - h, 0.0))) / (
            (ecc + h) - np.maximum(ecc - h, 0.0)
        )
        base = self.eye.retinal_radius_mm**2 / self.px_per_unit_radius**2
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.sin(ecc) / (f * df)
        # limit at the disc, and guard the degenerate f == 0 row
        ratio = np.where(ecc > 10 * h, ratio, 1.0)
        return base * np.nan_to_num(ratio, nan=1.0, posinf=1.0)

    def in_bounds(self, retinal: np.ndarray) -> np.ndarray:
        """Boolean mask: is this point inside the retinal rim?"""
        a = np.asarray(retinal, dtype=float).reshape(-1, 2)
        return a[:, 0] <= self.eye.rim_eccentricity

    def quadrant(self, retinal: np.ndarray, offset_deg: float = 45.0) -> np.ndarray:
        """Label points by quadrant from the meridian angle.

        Returns an integer array 0..3. ``offset_deg`` rotates the quadrant
        boundaries so they can be aligned to your dissection cuts (the cuts
        normally fall on the boundaries, not the centres). You are
        responsible for mapping 0..3 onto dorsal/ventral/nasal/temporal using
        the eye's orientation marks -- the code cannot know which way up the
        retina was mounted.
        """
        a = np.asarray(retinal, dtype=float).reshape(-1, 2)
        shifted = (a[:, 1] + np.deg2rad(offset_deg)) % (2 * np.pi)
        return (shifted / (np.pi / 2)).astype(int) % 4
