"""Folding the ledgers: tiles.csv -> auto_counts.csv, tile_manual_counts.csv -> manual_counts.csv,
and what rbpms.counts / review_status / update_log make of them.

Everything is synthetic text in a temporary folder: no Fiji, no images.
"""
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import rbpms  # noqa: E402
import tiling  # noqa: E402

TILE_PX, MARGIN = 600, 133
UM = 0.227

IMAGES = [
    # a1 is tiled 2x2 and finished; a3 is the same shape but one tile short
    dict(sample="9000L", image="a1", file="D:/img/a1.czi", series=0, format="Zeiss CZI",
         width_px=1200, height_px=1000, z=2, t=1, channels=2, channel_names="RBPMS|DAPI", rgb=0,
         um_per_px=UM, bytes=1000, problem=""),
    dict(sample="9000L", image="a2", file="D:/img/a2.tif", series=0, format="Tagged Image File Format",
         width_px=500, height_px=500, z=1, t=1, channels=1, channel_names="", rgb=0,
         um_per_px="", bytes=900, problem=""),          # no pixel size: area must stay unknown
    dict(sample="9000L", image="a3", file="D:/img/a3.czi", series=0, format="Zeiss CZI",
         width_px=1200, height_px=1000, z=1, t=1, channels=1, channel_names="", rgb=0,
         um_per_px=UM, bytes=1000, problem=""),
    dict(sample="9000L", image="broken", file="D:/img/broken.tif", series=0, format="",
         width_px=0, height_px=0, z=0, t=0, channels=0, channel_names="", rgb=0,
         um_per_px="", bytes=12, problem="Unknown file format"),
    dict(sample="9000R", image="b1", file="D:/img/b1.czi", series=0, format="Zeiss CZI",
         width_px=500, height_px=500, z=1, t=1, channels=1, channel_names="", rgb=0,
         um_per_px=UM, bytes=800, problem=""),
]


def tile_row(sample, image, tile, *, auto, objects=0, dim=0, outside=0, core_px=300000,
             um=UM, skipped=0, at="2026-11-20 09:00"):
    """A tiles.csv row. Only the summed columns and skipped_empty matter to the folds, so the
    geometry here is a placeholder; test_tiling.py is where the geometry is checked."""
    return dict(sample=sample, image=image, tile=tile, col=0, row=0, x0=0, y0=0, w=733, h=633,
                core_x0=0, core_y0=0, core_x1=600, core_y1=500, margin=MARGIN, auto_count=auto,
                objects_detected=objects, rejected_dim=dim, outside_core=outside, core_px=core_px,
                tissue_fraction="", skipped_empty=skipped, um_per_px=um,
                source_format="Zeiss CZI", file=f"D:/img/{image}.czi", counted_at=at, problem="")


TILES = [
    tile_row("9000L", "a1", "a1_r00c00", auto=8, objects=10, dim=2, outside=1),
    tile_row("9000L", "a1", "a1_r00c01", auto=9, objects=11, dim=2, outside=0, at="2026-11-20 09:01"),
    tile_row("9000L", "a1", "a1_r01c00", auto=0, objects=0, dim=0, outside=0, skipped=1),
    tile_row("9000L", "a1", "a1_r01c01", auto=7, objects=9, dim=2, outside=1, at="2026-11-20 09:03"),
    tile_row("9000L", "a2", "a2", auto=12, objects=14, dim=2, core_px=500 * 500, um=""),
    tile_row("9000L", "a3", "a3_r00c00", auto=5, objects=5),
    tile_row("9000L", "a3", "a3_r00c01", auto=5, objects=5),
    tile_row("9000L", "a3", "a3_r01c00", auto=5, objects=5),               # a3_r01c01 is missing
    tile_row("9000R", "b1", "b1", auto=20, objects=22, dim=2, core_px=500 * 500),
]

# the review tool writes one row per .tif in counted/<sample>/, so `image` holds the tile name
TILE_MANUAL = [
    dict(sample="9000L", image="a1_r00c00", auto_count=8, removed=1, added=2, final_count=9,
         reviewer="WL", reviewed_at="2026-11-21 10:00", seconds=40, note=""),
    dict(sample="9000L", image="a1_r00c01", auto_count=9, removed=0, added=1, final_count=10,
         reviewer="WL", reviewed_at="2026-11-21 10:02", seconds=35, note="edge cell"),
    dict(sample="9000L", image="a1_r01c01", auto_count=7, removed=2, added=0, final_count=5,
         reviewer="KG", reviewed_at="2026-11-21 10:05", seconds=25, note=""),
    dict(sample="9000R", image="b1", auto_count=20, removed=3, added=1, final_count=18,
         reviewer="WL", reviewed_at="2026-11-21 11:00", seconds=60, note=""),
    dict(sample="9000L", image="a3_r00c00", auto_count=5, removed=1, added=0, final_count=4,
         reviewer="WL", reviewed_at="2026-11-21 12:00", seconds=20, note=""),
]

# written straight into manual_counts.csv by the review tool as it was before tiling
LEGACY_MANUAL = [
    dict(sample="9000X", image="old1", auto_count=10, removed=1, added=1, final_count=10,
         reviewer="AB", reviewed_at="2024-01-01 10:00", seconds=30, note="before tiling"),
]


class LedgerCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="rbpms-ledger-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.data, self.out, self.tracking = self.tmp / "data", self.tmp / "out", self.tmp / "tracking"
        self.data.mkdir()
        self.counts = self.out / "counts"
        tiling.write_csv_rows(self.counts / "images.csv", tiling.IMAGES_COLUMNS, IMAGES)
        tiling.write_csv_rows(self.counts / "tiles.csv", tiling.TILES_COLUMNS, TILES)
        tiling.write_csv_rows(self.counts / "tile_manual_counts.csv",
                              tiling.MANUAL_COUNTS_COLUMNS[:10], TILE_MANUAL)
        tiling.write_csv_rows(self.counts / "manual_counts.csv",
                              tiling.MANUAL_COUNTS_COLUMNS[:10], LEGACY_MANUAL)

    @property
    def images(self):
        return tiling.read_images_csv(self.counts / "images.csv")

    @property
    def tiles(self):
        return tiling.read_tiles_csv(self.counts / "tiles.csv")

    def write_auto_counts(self):
        rows = tiling.fold_auto(self.tiles, self.images, TILE_PX, MARGIN)
        tiling.write_auto_counts_csv(self.counts / "auto_counts.csv", rows)
        return rows


class TestFoldAuto(LedgerCase):
    def test_one_row_per_image_with_the_old_columns_first(self):
        rows = tiling.fold_auto(self.tiles, self.images, TILE_PX, MARGIN)
        self.assertEqual([(r["sample"], r["image"]) for r in rows],
                         [("9000L", "a1"), ("9000L", "a2"), ("9000R", "b1")])
        self.assertEqual(tiling.AUTO_COUNTS_COLUMNS[:6],
                         ["sample", "image", "auto_count", "objects_detected", "file", "counted_at"])
        a1 = rows[0]
        self.assertEqual(a1["auto_count"], 8 + 9 + 0 + 7)
        self.assertEqual(a1["objects_detected"], 10 + 11 + 0 + 9)
        self.assertEqual(a1["rejected_dim"], 6)
        self.assertEqual(a1["outside_core"], 2)
        self.assertEqual(a1["core_px"], 1200 * 1000)
        self.assertEqual((a1["tiles"], a1["tiles_counted"]), (4, 4))
        self.assertEqual(a1["counted_at"], "2026-11-20 09:03")        # the latest of its tiles
        self.assertEqual(a1["source_format"], "Zeiss CZI")

    def test_an_image_with_a_missing_tile_is_not_finished(self):
        rows = tiling.fold_auto(self.tiles, self.images, TILE_PX, MARGIN)
        self.assertNotIn("a3", [r["image"] for r in rows])
        partial = tiling.fold_auto(self.tiles, self.images, TILE_PX, MARGIN, include_incomplete=True)
        a3 = next(r for r in partial if r["image"] == "a3")
        self.assertEqual((a3["tiles"], a3["tiles_counted"]), (4, 3))
        self.assertEqual(a3["auto_count"], 15)

    def test_area_is_blank_when_the_pixel_size_is_unknown(self):
        rows = {r["image"]: r for r in tiling.fold_auto(self.tiles, self.images, TILE_PX, MARGIN)}
        want = 1200 * 1000 * UM * UM / 1e6
        self.assertAlmostEqual(rows["a1"]["area_mm2"], want, places=6)
        self.assertAlmostEqual(rows["a1"]["cells_per_mm2"], 24 / want, places=1)
        # never a guessed 0.146 mm^2 and never 0: unknown stays unknown
        self.assertIsNone(rows["a2"]["um_per_px"])
        self.assertIsNone(rows["a2"]["area_mm2"])
        self.assertIsNone(rows["a2"]["cells_per_mm2"])

    def test_area_reads_back_as_nan(self):
        import pandas as pd
        self.write_auto_counts()
        df = pd.read_csv(self.counts / "auto_counts.csv").set_index("image")
        self.assertTrue(pd.isna(df.loc["a2", "area_mm2"]))
        self.assertTrue(pd.isna(df.loc["a2", "cells_per_mm2"]))
        self.assertFalse(pd.isna(df.loc["a1", "area_mm2"]))

    def test_a_corrected_tile_row_replaces_the_earlier_one(self):
        with open(self.counts / "tiles.csv", "a", encoding="utf-8", newline="") as fh:
            fh.write(",".join(str(tile_row("9000L", "a1", "a1_r00c00", auto=99)[c])
                              for c in tiling.TILES_COLUMNS) + "\n")
        rows = {r["image"]: r for r in tiling.fold_auto(self.tiles, self.images, TILE_PX, MARGIN)}
        self.assertEqual(rows["a1"]["auto_count"], 99 + 9 + 0 + 7)

    def test_an_image_no_longer_in_the_survey_still_folds(self):
        rows = {r["image"]: r for r in tiling.fold_auto(self.tiles, [], TILE_PX, MARGIN)}
        self.assertEqual(rows["a1"]["auto_count"], 24)
        self.assertEqual((rows["a1"]["tiles"], rows["a1"]["tiles_counted"]), (4, 4))
        self.assertEqual(rows["a3"]["tiles"], 3)       # the rows present are all we know about
        self.assertAlmostEqual(rows["a1"]["um_per_px"], UM)


class TestFoldManual(LedgerCase):
    def fold(self):
        return tiling.fold_manual(tiling.read_manual_csv(self.counts / "tile_manual_counts.csv"),
                                  self.tiles,
                                  tiling.read_manual_csv(self.counts / "manual_counts.csv"))

    def test_tiles_fold_into_one_row_per_image(self):
        rows = {(r["sample"], r["image"]): r for r in self.fold()}
        a1 = rows[("9000L", "a1")]
        self.assertEqual(a1["auto_count"], 8 + 9 + 7)
        self.assertEqual((a1["removed"], a1["added"], a1["final_count"]), (3, 3, 24))
        self.assertEqual(a1["reviewer"], "KG;WL")
        self.assertEqual(a1["reviewed_at"], "2026-11-21 10:05")
        self.assertEqual(a1["seconds"], 100)
        self.assertEqual(a1["note"], "edge cell")
        # the tile that was skipped as empty has no counted .tif, so it is not waiting for review
        self.assertEqual((a1["tiles"], a1["tiles_reviewed"]), (3, 3))

    def test_a_half_reviewed_image_is_not_reviewed(self):
        rows = {(r["sample"], r["image"]) for r in self.fold()}
        self.assertNotIn(("9000L", "a3"), rows)          # 1 of its 3 counted tiles reviewed
        self.assertIn(("9000R", "b1"), rows)             # a single-tile image needs one review

    def test_legacy_rows_are_kept(self):
        rows = {(r["sample"], r["image"]): r for r in self.fold()}
        old = rows[("9000X", "old1")]
        self.assertEqual((old["final_count"], old["reviewer"]), (10, "AB"))
        self.assertEqual((old["tiles"], old["tiles_reviewed"]), ("", ""))

    def test_sync_is_idempotent(self):
        first = rbpms.sync_manual_counts(self.out).read_text(encoding="utf-8")
        self.assertEqual(rbpms.sync_manual_counts(self.out).read_text(encoding="utf-8"), first)
        self.assertIn("9000X,old1", first)
        self.assertIn("9000L,a1", first)


class TestReports(LedgerCase):
    def test_counts_per_image(self):
        self.write_auto_counts()
        df = rbpms.counts(self.out, level="image").set_index("image")
        self.assertEqual(sorted(df.index), ["a1", "a2", "b1"])
        self.assertEqual(int(df.loc["a1", "auto_count"]), 24)
        self.assertEqual(int(df.loc["a1", "final_count"]), 24)
        self.assertEqual(int(df.loc["a1", "tiles_reviewed"]), 3)
        self.assertTrue(bool(df.loc["a1", "reviewed"]))
        self.assertFalse(bool(df.loc["a2", "reviewed"]))
        self.assertEqual(int(df.loc["a2", "count"]), 12)      # falls back to the automated count
        self.assertEqual(int(df.loc["b1", "count"]), 18)

    def test_counts_per_tile(self):
        self.write_auto_counts()
        df = rbpms.counts(self.out, level="tile").set_index("tile")
        self.assertEqual(len(df), len(TILES))
        self.assertEqual(int(df.loc["a1_r00c00", "final_count"]), 9)
        self.assertEqual(df.loc["a1_r00c00", "reviewer"], "WL")
        import pandas as pd
        self.assertTrue(pd.isna(df.loc["a1_r01c00", "final_count"]))   # skipped, never reviewed

    def test_counts_rejects_an_unknown_level(self):
        self.write_auto_counts()
        with self.assertRaises(ValueError):
            rbpms.counts(self.out, level="animal")

    def test_review_status(self):
        self.write_auto_counts()
        st = rbpms.review_status(self.out).set_index("retina")
        self.assertEqual(int(st.loc["9000L", "images"]), 2)        # a1 and a2; a3 is unfinished
        self.assertEqual(int(st.loc["9000L", "reviewed"]), 1)
        self.assertEqual(int(st.loc["9000L", "still_to_review"]), 1)
        self.assertEqual(int(st.loc["9000L", "fields"]), 5)        # 4 tiles of a1 plus a2
        self.assertEqual(int(st.loc["9000R", "reviewed"]), 1)

    def test_update_log_compares_images_not_tiles(self):
        self.write_auto_counts()
        self.tracking.mkdir()
        (self.tracking / "animals.csv").write_text(
            "animal,eyes,priority,requested,notes\n9000,L R,today,2026-11-01,\n", encoding="utf-8")
        st = rbpms.update_log(self.data, self.out, tracking=self.tracking).set_index("eye")
        left, right = st.loc["L"], st.loc["R"]
        # three readable source images in 9000L (a1, a2, a3), two of them finished
        self.assertEqual((int(left["images"]), int(left["counted"]), int(left["reviewed"])), (3, 2, 1))
        self.assertTrue(str(left["stage"]).startswith("3 counting (2 of 3)"))
        self.assertEqual((int(right["images"]), int(right["counted"]), int(right["reviewed"])), (1, 1, 1))
        self.assertTrue(str(right["stage"]).startswith("6 reviewed"))
        self.assertTrue((self.tracking / "STATUS.md").exists())
        self.assertTrue((self.tracking / "status.csv").exists())

    def test_images_in_counts_series_and_skips_unreadable(self):
        found = rbpms.images_in(self.data, self.out)
        self.assertEqual(found, {"9000L": 3, "9000R": 1})      # "broken" is left out
        # with no survey it falls back to counting files
        (self.data / "9000L").mkdir()
        (self.data / "9000L" / "x.czi").write_bytes(b"0")
        (self.data / "9000L" / "._x.czi").write_bytes(b"0")
        (self.data / "9000L" / "notes.txt").write_bytes(b"0")
        self.assertEqual(rbpms.images_in(self.data), {"9000L": 1})


if __name__ == "__main__":
    unittest.main()
