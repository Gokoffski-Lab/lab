"""The contract every analysis tool implements. Interfaces (CLI, napari) only talk to this."""

from dataclasses import dataclass, field
from typing import Any, Protocol

import pandas as pd

from .annotations import Shape
from .image import Image


@dataclass
class Result:
    tables: dict[str, pd.DataFrame]
    metrics: dict[str, float]
    overlays: list[Shape] = field(default_factory=list)


class Tool(Protocol):
    name: str
    Params: type  # a dataclass; its fields drive params.json and UI forms

    def suggest(self, img: Image, params: Any, hints: list[Shape] | None = None) -> tuple[Image, list[Shape]]:
        """Propose annotations. May return a transformed image (e.g. straightened) that run() works on.

        hints are optional user shapes on the input image that steer the proposal (e.g. a rough centerline).
        """
        ...

    def run(self, img: Image, shapes: list[Shape], params: Any) -> Result:
        """Pure analysis: no UI, no file I/O."""
        ...
