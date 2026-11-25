from dataclasses import dataclass
from typing import Literal

from ...core.annotations import Shape
from ...core.image import Image
from ...core.tool import Result
from .measure import measure


@dataclass(frozen=True)
class Params:
    band_um: float = 25.0
    threshold: Literal["background", "auto", "manual"] = "background"
    k: float = 2.0
    auto_method: str = "triangle"
    manual_threshold: float = 0.0
    below: Literal["subtract", "hard"] = "subtract"
    # pre: v2 macro rule (validated method). auto: per position, for nerves not flat in z; adds a distal floor
    # of 2-10% on real nerves whose source (faint axons or tissue) is not yet known
    z: Literal["pre", "auto", "all", "manual"] = "pre"
    z_frac: float = 0.10
    z_first: int = 1
    z_last: int = 0
    distances_um: tuple[float, ...] = (250, 500, 750, 1000, 1250, 1500, 1750, 2000)
    auc_min_um: float = 250.0
    auc_max_um: float = 2000.0
    reach: tuple[float, ...] = (0.5, 0.25, 0.1, 0.05)
    # axons crossing each line (count.py); a peak counts when it rises peak_k x the line profile's noise SD
    count: bool = True
    count_band_um: float = 10.0
    peak_k: float = 8.0  # exact on synthetic nerves; leaves 1-4 false peaks per line on empty real nerve
    min_sep_um: float = 3.0
    section_thickness_um: float = 0.0  # > 0 adds sigma_ad (axons per nerve, Leon et al. 2000); sections only
    # suggest(): automatic straightening and line placement
    straighten: bool = True
    flip_direction: bool = False  # set when Suggest put the eye (proximal) end on the wrong side
    blur_um: float = 5.0
    pre_offset_um: float = 300.0
    margin_um: float = 40.0


class AxonDensity:
    name = "axon_density"
    Params = Params

    def suggest(self, img: Image, params: Params, hints: list[Shape] | None = None) -> tuple[Image, list[Shape]]:
        from .straighten import suggest

        return suggest(img, params, hints)

    def run(self, img: Image, shapes: list[Shape], params: Params) -> Result:
        return measure(img, shapes, params)
