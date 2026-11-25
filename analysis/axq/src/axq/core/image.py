from dataclasses import dataclass, replace

import numpy as np


@dataclass(frozen=True)
class Image:
    """A single-channel z-stack. Pixel (i, j) of slice z is data[z, i, j]; x is the column."""

    data: np.ndarray  # float32 [z, y, x]
    um_per_px: tuple[float, float]  # (x, y)
    name: str
    source: str = ""

    def __post_init__(self):
        if self.data.ndim == 2:
            object.__setattr__(self, "data", self.data[None])
        if self.data.ndim != 3:
            raise ValueError(f"expected a [z, y, x] stack, got shape {self.data.shape}")
        if self.data.dtype != np.float32:
            object.__setattr__(self, "data", self.data.astype(np.float32))

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.data.shape

    def with_data(self, data: np.ndarray, **changes) -> "Image":
        return replace(self, data=data, **changes)
