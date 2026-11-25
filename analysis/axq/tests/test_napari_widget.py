import json

import numpy as np
import pytest

napari = pytest.importorskip("napari")

from axq.napari_plugin.widget import QuantifyWidget  # noqa: E402
from tests.synth.nerve import curved, make_axons  # noqa: E402


def test_suggest_edit_run_matches_cli(tmp_path, qtbot):
    viewer = napari.Viewer(show=False)
    try:
        img = curved(make_axons())
        viewer.add_image(img.data, name="nerve", scale=(1, 1, 1))
        w = QuantifyWidget(viewer)
        w.params_box["distances_um"].value = "250, 500"
        w.out_dir.value = str(tmp_path)

        w.suggest()
        sl = w.shapes_box.value
        names = list(sl.features["name"])
        assert {"Pre", "Crush", "Post_250um", "Post_500um", "Background"} <= set(names)

        # user deletes the 500 um line and draws their own at 750 um
        crush = sl.data[names.index("Crush")]
        sl.selected_data = {names.index("Post_500um")}
        sl.remove_selected()
        sl.add_lines(crush + np.array([0, 750]))

        run_dir = w.run()
        metrics = json.loads((run_dir / "metrics.json").read_text())
        assert "pct_pre_Post_500um" not in metrics
        assert 8 < metrics["pct_pre_Line_1"] < 20  # unnamed user line, 750 um past the crush
        assert 30 < metrics["pct_pre_Post_250um"] < 45

        # counted axons shown on the straightened image, at their slice; curve and counts plotted
        pts = viewer.layers[f"{w.image_box.value.name} counted axons"]
        assert len(pts.data) > 0 and pts.data.shape[1] == 3
        assert set(np.unique(pts.data[:, 0])) <= set(range(img.data.shape[0]))
        assert len(w.figure.axes) == 2 and len(w.figure.axes[1].lines[0].get_xdata()) == 2
    finally:
        viewer.close()
