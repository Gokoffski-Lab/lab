"""The napari panel and the CLI give identical results on a real nerve (skipped when data/ is absent).

data/ is not tracked; this runs on the annotated nerve B from the validation set.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

napari = pytest.importorskip("napari")

from axq.cli import main  # noqa: E402
from axq.core.annotations import read_roiset  # noqa: E402
from axq.core.io import read_image  # noqa: E402
from axq.core.runs import find_runs  # noqa: E402
from axq.napari_plugin.widget import QuantifyWidget, shapes_to_layer_data  # noqa: E402

NERVE = Path(__file__).parents[1] / "data" / "annotations" / "nerve B"
pytestmark = pytest.mark.skipif(not (NERVE / "RoiSet.zip").exists(), reason="real validation data not present")


def test_panel_matches_cli_on_real_nerve(tmp_path, qtbot):
    img = read_image(NERVE / "straightened.tif")
    shapes = read_roiset(NERVE / "RoiSet.zip")
    um = img.um_per_px
    viewer = napari.Viewer(show=False)
    try:
        layer = viewer.add_image(img.data, name="nerve B", scale=(1, um[1], um[0]))
        data, kinds, names = shapes_to_layer_data(shapes)
        viewer.add_shapes(data, shape_type=kinds, name="annotations", features={"name": names},
                          scale=layer.scale[-2:])
        w = QuantifyWidget(viewer)
        w.image_box.value = layer
        w.shapes_box.value = viewer.layers["annotations"]
        w.out_dir.value = str(tmp_path / "panel")
        panel = w.run()
    finally:
        viewer.close()

    main(["run", "axon_density", str(NERVE / "straightened.tif"), "--roiset", str(NERVE / "RoiSet.zip"),
          "--out", str(tmp_path / "cli")])
    cli = find_runs(tmp_path / "cli")[0]

    pm, cm = (json.loads((d / "metrics.json").read_text()) for d in (panel, cli))
    assert pm.keys() == cm.keys()
    assert all(pm[k] == pytest.approx(cm[k], rel=1e-6, abs=1e-9) for k in pm)
    for t in ("lines", "counts", "per_slice", "curve"):
        pd.testing.assert_frame_equal(pd.read_csv(panel / "tables" / f"{t}.csv"),
                                      pd.read_csv(cli / "tables" / f"{t}.csv"), rtol=1e-6)
