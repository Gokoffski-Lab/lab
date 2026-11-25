import sys
import textwrap

import pandas as pd

from axq.cli import aggregate, main
from axq.core.annotations import write_roiset
from axq.core.io import write_image
from axq.core.registry import load_tools
from tests.synth.nerve import curved, make_axons, straight


def test_outside_tool_plugs_in_without_core_changes(tmp_path, monkeypatch, capsys):
    (tmp_path / "dummy_tool.py").write_text(
        textwrap.dedent(
            """
            from dataclasses import dataclass
            from axq.core.tool import Result

            @dataclass(frozen=True)
            class Params:
                scale: float = 1.0

            class Dummy:
                name = "dummy"
                Params = Params
                def suggest(self, img, p, hints=None):
                    return img, []
                def run(self, img, shapes, p):
                    return Result({}, {"mean": float(img.data.mean() * p.scale)})
            """
        )
    )
    dist = tmp_path / "dummy_tool-0.1.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text("Metadata-Version: 2.1\nName: dummy-tool\nVersion: 0.1\n")
    (dist / "entry_points.txt").write_text("[axq.tools]\ndummy = dummy_tool:Dummy\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    assert {"axon_density", "dummy"} <= set(load_tools())
    main(["list"])
    assert "dummy" in capsys.readouterr().out


def test_run_with_roiset_then_aggregate(tmp_path):
    img, shapes = straight(make_axons())
    write_image(img, tmp_path / "n1.tif")
    write_roiset(shapes, tmp_path / "n1.zip")
    out = tmp_path / "runs"
    main(["run", "axon_density", str(tmp_path / "n1.tif"), "--roiset", str(tmp_path / "n1.zip"),
          "--out", str(out), "--set", "distances_um=250,500", "auc_max_um=1000"])
    (tmp_path / "groups.csv").write_text("image,group\nn1,control\n")
    df = aggregate(str(out), str(tmp_path / "groups.csv"))
    row = df[df.metric == "pct_pre_Post_250um"].iloc[0]
    assert row.group == "control" and 30 < row.value < 45


def test_fully_automatic_run_on_curved_nerve(tmp_path):
    write_image(curved(make_axons()), tmp_path / "c.tif")
    main(["run", "axon_density", str(tmp_path / "c.tif"), "--out", str(tmp_path / "runs"),
          "--set", "distances_um=250,500,750,1000", "auc_max_um=1000"])
    run = next((tmp_path / "runs" / "axon_density").iterdir())
    lines = pd.read_csv(run / "tables" / "lines.csv").set_index("roi")
    assert 30 < lines.loc["Post_250um", "percent_of_pre"] < 45
    assert (run / "RoiSet.zip").exists() and (run / "provenance.json").exists()
