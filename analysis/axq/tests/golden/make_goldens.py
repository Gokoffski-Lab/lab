"""Regenerate the v2-macro golden outputs that test_parity.py compares the Python port against.

    python tests/golden/make_goldens.py --java <java.exe> --ij <ij-1.54x.jar>

Uses plain ImageJ in -batch mode (needs a display; no Fiji plugins required).
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from axq.core.annotations import write_roiset  # noqa: E402
from axq.core.io import write_image  # noqa: E402
from tests.synth.nerve import make_axons, straight  # noqa: E402

MACRO = ROOT / "fiji" / "AxonQuantifier_v2.ijm"
MACRO_ARGS = "distances=[250,500,750,1000] aucmax=1000"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--java", required=True)
    ap.add_argument("--ij", required=True)
    a = ap.parse_args()
    img, shapes = straight(make_axons())
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        write_image(img.with_data(img.data.astype("uint16")), tmp / "synth.tif")
        write_roiset(shapes, tmp / "RoiSet.zip")
        (tmp / "out").mkdir()
        arg = f"image=[{tmp / 'synth.tif'}] out=[{tmp / 'out'}] roiset=[{tmp / 'RoiSet.zip'}] {MACRO_ARGS}"
        r = subprocess.run([a.java, "-jar", a.ij, "-batch", str(MACRO), arg], capture_output=True, text=True)
        print(r.stdout[-2000:])
        run = next((tmp / "out").iterdir())
        for name in ("summary.csv", "curve_metrics.csv"):
            shutil.copy(run / name, HERE / f"v2_straight_{name}")
    print("wrote goldens to", HERE)


if __name__ == "__main__":
    main()
