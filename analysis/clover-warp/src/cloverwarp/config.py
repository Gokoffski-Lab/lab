"""Configuration: one YAML file per project, loaded into typed dataclasses.

Every number that affects a result lives here and is copied verbatim into
the output directory next to the results. A result whose config is not
alongside it is not reproducible and should be deleted rather than
interpreted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

from .frames import MOUSE_EYE, RAT_EYE, EyeGeometry
from .match import MatchParams
from .vessels import VesselParams

__all__ = ["Config", "load_config", "write_config"]

_EYES = {"rat": RAT_EYE, "mouse": MOUSE_EYE}


@dataclass
class GateConfig:
    min_landmarks: int = 8
    max_loo_px: float = 25.0
    max_stretch: float = 3.0
    min_coverage: float = 0.75


@dataclass
class Config:
    #: free-form dataset name, used in output file names
    dataset: str = "untitled"

    # --- species / geometry -----------------------------------------------
    species: str = "rat"
    retinal_radius_mm: float | None = None
    rim_eccentricity_deg: float | None = None
    projection: str = "azimuthal_equidistant"

    # --- inputs -----------------------------------------------------------
    fa_image: str | None = None
    flatmount_image: str | None = None
    #: 0-based channel indices in the flatmount image
    vessel_channel: int = 0
    tissue_channel: int = 0
    centroid_table: str | None = None
    #: multiply centroid coordinates by this to get flatmount pixels
    centroid_scale_to_px: float = 1.0

    # --- geometry calibration --------------------------------------------
    #: optic disc in FA pixels; auto-detected from the tissue mask if null
    fa_disc_xy: list[float] | None = None
    #: radius in FA pixels of the retinal rim, for scale calibration
    fa_rim_radius_px: float | None = None

    # --- stages -----------------------------------------------------------
    n_petals: int | None = 4
    #: how far outside its own sector a petal may match in the FA, radians.
    #: Covers rotation introduced by mounting. Too large reintroduces the
    #: rotational ambiguity the prior exists to remove; too small rejects
    #: correct matches on a petal that was mounted crooked.
    sector_pad_rad: float = 0.35
    warp_model: str = "tps"
    warp_smoothing: float = 1e-3
    vessels: VesselParams = field(default_factory=VesselParams)
    matching: MatchParams = field(default_factory=MatchParams)
    gates: GateConfig = field(default_factory=GateConfig)

    # --- outputs ----------------------------------------------------------
    outdir: str = "results"
    n_rings: int = 8
    density_bin_px: float = 100.0

    @property
    def eye(self) -> EyeGeometry:
        base = _EYES.get(self.species.lower())
        if base is None:
            raise ValueError(
                f"unknown species {self.species!r}; known: {sorted(_EYES)}. "
                "Add an EyeGeometry for it in frames.py."
            )
        return EyeGeometry(
            name=base.name,
            retinal_radius_mm=self.retinal_radius_mm or base.retinal_radius_mm,
            rim_eccentricity_deg=(
                self.rim_eccentricity_deg
                if self.rim_eccentricity_deg is not None
                else base.rim_eccentricity_deg
            ),
        )

    def to_dict(self) -> dict:
        return asdict(self)


def _build(cls, data):
    if data is None:
        return cls()
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"{cls.__name__}: unknown keys {sorted(unknown)}")
    kwargs = dict(data)
    for f in fields(cls):
        if f.name in kwargs and isinstance(kwargs[f.name], list):
            # dataclass tuple fields come back from YAML as lists
            if f.type and "tuple" in str(f.type):
                kwargs[f.name] = tuple(kwargs[f.name])
    return cls(**kwargs)


def load_config(path) -> Config:
    """Load a YAML config, failing loudly on unknown keys.

    Unknown keys are an error on purpose: a typo in a threshold name would
    otherwise silently leave the default in place, and you would never know
    the setting you thought you changed was ignored.
    """
    data = yaml.safe_load(Path(path).read_text()) or {}
    nested = {
        "vessels": VesselParams,
        "matching": MatchParams,
        "gates": GateConfig,
    }
    kwargs = {k: v for k, v in data.items() if k not in nested}
    known = {f.name for f in fields(Config)}
    unknown = set(kwargs) - known
    if unknown:
        raise ValueError(
            f"{path}: unknown config keys {sorted(unknown)}; known keys are "
            f"{sorted(known)}"
        )
    for key, cls in nested.items():
        kwargs[key] = _build(cls, data.get(key))
    return Config(**kwargs)


def write_config(cfg: Config, path) -> Path:
    """Write the fully-resolved config beside the results."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg.to_dict(), sort_keys=False))
    return path
