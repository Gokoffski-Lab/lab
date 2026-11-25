"""One napari panel for every registered tool: pick tool, set params, Suggest, adjust shapes, Run.

The panel holds no analysis. It converts napari layers to axq Image/Shape and calls the tool.
"""

import dataclasses
import re
import typing
from typing import Optional
from pathlib import Path

import numpy as np
from magicgui.widgets import ComboBox, Container, FileEdit, Label, LineEdit, PushButton, Table, create_widget

from ..cli import coerce
from ..core.annotations import Shape
from ..core.image import Image
from ..core.registry import load_tools
from ..core.runs import write_run

_TO_NAPARI = {"line": "line", "polygon": "polygon", "polyline": "path"}
_FROM_NAPARI = {"line": "line", "polygon": "polygon", "rectangle": "polygon", "ellipse": "polygon", "path": "polyline"}


def shapes_to_layer_data(shapes: list[Shape]) -> tuple[list[np.ndarray], list[str], list[str]]:
    keep = [s for s in shapes if s.kind in _TO_NAPARI]
    return [s.xy[:, ::-1].copy() for s in keep], [_TO_NAPARI[s.kind] for s in keep], [s.name for s in keep]


def layer_to_shapes(layer, image_layer=None) -> list[Shape]:
    """Shapes in pixel coordinates; pass image_layer when the shapes were drawn over it at a different scale."""
    names = list(layer.features["name"]) if "name" in layer.features else [""] * len(layer.data)
    out, n_new = [], 0
    for data, kind, name in zip(layer.data, layer.shape_type, names):
        rc = np.asarray(data)[:, -2:]
        if image_layer is not None:
            world = rc * layer.scale[-2:] + layer.translate[-2:]
            rc = (world - image_layer.translate[-2:]) / image_layer.scale[-2:]
        xy = rc[:, ::-1]  # napari (row, col) -> (x, y)
        if not name:
            n_new += 1
            name = f"Line_{n_new}" if kind == "line" else f"Shape_{n_new}"
        out.append(Shape(str(name), _FROM_NAPARI.get(kind, "polygon"), xy))
    return out


def overlay_points(overlays: list[Shape], ndim: int) -> np.ndarray:
    """All Points overlays as napari (z, row, col) or (row, col) coordinates; z comes from a _z<k> name suffix."""
    rows = []
    for s in overlays:
        if s.kind != "points":
            continue
        m = re.search(r"_z(\d+)$", s.name)
        z = int(m.group(1)) - 1 if m else 0
        rc = s.xy[:, ::-1]
        rows.append(np.column_stack([np.full(len(rc), z), rc]) if ndim == 3 else rc)
    return np.vstack(rows) if rows else np.zeros((0, ndim))


def layer_to_image(layer) -> Image:
    data = np.asarray(layer.data)
    sy, sx = layer.scale[-2:]
    return Image(data, (float(sx), float(sy)), layer.name, str(layer.source.path or ""))


class QuantifyWidget(Container):
    def __init__(self, napari_viewer):
        super().__init__()
        import napari.layers

        self.viewer = napari_viewer
        self.tools = load_tools()
        self.tool_box = ComboBox(label="tool", choices=list(self.tools))
        self.image_box = create_widget(annotation=napari.layers.Image, label="image")
        self.guide_box = create_widget(annotation=Optional[napari.layers.Shapes], label="centerline guide")
        self.guide_box.tooltip = "Optional: a path drawn roughly along the nerve on the raw image"
        self.shapes_box = create_widget(annotation=napari.layers.Shapes, label="annotations")
        self.params_box = Container(label="parameters")
        self.out_dir = FileEdit(label="results folder", mode="d", value=str(Path.home() / "axq_runs"))
        self.suggest_btn = PushButton(text="Suggest")
        self.run_btn = PushButton(text="Run")
        self.status = Label(value="")
        self.table = Table(value={"metric": [], "value": []})
        self.extend([self.tool_box, self.image_box, self.guide_box, self.params_box, self.suggest_btn, self.shapes_box,
                     self.out_dir, self.run_btn, self.status, self.table])
        self._build_plot()
        self.tool_box.changed.connect(self._build_params)
        self.suggest_btn.changed.connect(self.suggest)
        self.run_btn.changed.connect(self.run)
        self.viewer.layers.events.inserted.connect(self.reset_choices)
        self.viewer.layers.events.removed.connect(self.reset_choices)
        self._build_params()

    def _build_plot(self):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        self.figure = Figure(figsize=(4, 2.6), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(220)
        self.native.layout().addWidget(self.canvas)

    def _plot(self, result):
        """Signal curve plus axon counts, when the tool returns them (axon_density does)."""
        self.figure.clear()
        curve = result.tables.get("curve")
        if curve is None:
            self.canvas.draw_idle()
            return
        ax = self.figure.add_subplot()
        post = curve[curve.distance_um >= 0]
        ax.plot(post.distance_um, 100 * post.fraction_of_pre_smoothed, lw=1, color="0.2")
        ax.set_xlabel("distance from crush (um)")
        ax.set_ylabel("signal, % of Pre")
        counts = result.tables.get("counts")
        if counts is not None:
            c = counts[counts.distance_um > 0]
            ax2 = ax.twinx()
            ax2.plot(c.distance_um, c.axons_mean_per_slice, "o", color="tab:cyan", ms=4)
            ax2.set_ylabel("axons crossing line", color="tab:cyan")
        self.canvas.draw_idle()

    def _show_overlays(self, layer, result):
        name = f"{layer.name} counted axons"
        if name in self.viewer.layers:
            self.viewer.layers.remove(name)
        pts = overlay_points(result.overlays, layer.data.ndim)
        if len(pts):
            self.viewer.add_points(pts, name=name, size=6, face_color="cyan", border_width=0,
                                   scale=layer.scale, translate=layer.translate)

    @property
    def tool(self):
        return self.tools[self.tool_box.value]

    def _build_params(self, *_):
        self.params_box.clear()
        hints = typing.get_type_hints(self.tool.Params)
        for f in dataclasses.fields(self.tool.Params):
            hint = hints[f.name]
            if typing.get_origin(hint) is typing.Literal:
                w = ComboBox(name=f.name, choices=typing.get_args(hint), value=f.default)
            elif typing.get_origin(hint) is tuple:
                w = LineEdit(name=f.name, value=", ".join(f"{v:g}" for v in f.default))
            else:
                w = create_widget(name=f.name, value=f.default, annotation=hint)
            self.params_box.append(w)

    def params(self):
        hints = typing.get_type_hints(self.tool.Params)
        return self.tool.Params(**{w.name: coerce(hints[w.name], w.value) for w in self.params_box})

    def suggest(self, *_):
        layer = self.image_box.value
        if layer is None:
            self.status.value = "Open an image first."
            return
        guide = self.guide_box.value
        hints = layer_to_shapes(guide, layer) if guide is not None else None
        img, shapes = self.tool.suggest(layer_to_image(layer), self.params(), hints)
        new_img = self.viewer.add_image(img.data, name=img.name, scale=(1, img.um_per_px[1], img.um_per_px[0]))
        data, kinds, names = shapes_to_layer_data(shapes)
        sl = self.viewer.add_shapes(
            data, shape_type=kinds, name=f"{img.name} annotations", edge_color="yellow", edge_width=2,
            face_color="transparent", features={"name": names}, text={"string": "{name}", "size": 10},
            scale=new_img.scale[-2:],
        )
        sl.feature_defaults["name"] = ""
        self.reset_choices()
        self.image_box.value = new_img
        self.shapes_box.value = sl
        self.status.value = "Check the lines; move, delete or add straight lines, then Run."

    def run(self, *_):
        layer, sl = self.image_box.value, self.shapes_box.value
        if layer is None or sl is None:
            self.status.value = "Pick an image and an annotations layer (or click Suggest)."
            return
        img, shapes, params = layer_to_image(layer), layer_to_shapes(sl), self.params()
        result = self.tool.run(img, shapes, params)
        run_dir = write_run(self.out_dir.value, self.tool.name, img, params, shapes, result)
        self.table.value = {"metric": list(result.metrics), "value": [f"{v:.4g}" for v in result.metrics.values()]}
        self._show_overlays(layer, result)
        self._plot(result)
        self.status.value = f"Saved {run_dir}"
        return run_dir
