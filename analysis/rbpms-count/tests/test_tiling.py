"""Tile geometry and the run plan. Standard library only: no Fiji, no pandas, no image files."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import tiling  # noqa: E402

SETTINGS = dict(max_diameter=130.0, min_diameter=35.0, radius=60, sigma=8.0, min_contrast=1.15,
                channel=1)
# primes, powers of two and both sides of a tile boundary
AWKWARD_SIZES = [(1, 1), (600, 500), (599, 501), (601, 499), (1200, 1000), (1201, 1009),
                 (2048, 2048), (2049, 2047), (997, 1009), (4099, 7), (2047, 2053)]


def img(w, h, sample="9000L", image="a1", **kw):
    return tiling.SourceImage(sample=sample, image=image, width_px=w, height_px=h, **kw)


class TestGeometry(unittest.TestCase):
    def test_cores_partition_awkward_image_sizes(self):
        for w, h in AWKWARD_SIZES:
            for tile_px in (0, 256, 600, 1024, 2048):
                for margin in (0, 37, 133):
                    with self.subTest(size=(w, h), tile_px=tile_px, margin=margin):
                        cells = tiling.tile_grid(w, h, tile_px, margin)
                        self.assertEqual(
                            sum((c["core_x1"] - c["core_x0"]) * (c["core_y1"] - c["core_y0"])
                                for c in cells), w * h)
                        for c in cells:
                            # the padded window stays inside the image and holds the whole core
                            self.assertGreaterEqual(c["x0"], 0)
                            self.assertGreaterEqual(c["y0"], 0)
                            self.assertLessEqual(c["x0"] + c["w"], w)
                            self.assertLessEqual(c["y0"] + c["h"], h)
                            self.assertLessEqual(c["x0"], c["core_x0"])
                            self.assertLessEqual(c["y0"], c["core_y0"])
                            self.assertGreaterEqual(c["x0"] + c["w"], c["core_x1"])
                            self.assertGreaterEqual(c["y0"] + c["h"], c["core_y1"])

    def test_every_point_has_exactly_one_owner(self):
        """Exhaustive on small images, edges included: no cell is counted twice or dropped."""
        for w, h in [(7, 5), (8, 8), (9, 4), (13, 11), (16, 9)]:
            for tile_px in (0, 3, 4, 5, 8, 16):
                tiles = tiling.plan_tiles(img(w, h), tile_px, 1)
                for x in range(w + 1):
                    for y in range(h + 1):
                        owners = [t.tile for t in tiles if tiling.tile_owns(t, x, y)]
                        self.assertEqual(len(owners), 1,
                                         f"{w}x{h} tile_px={tile_px} at ({x}, {y}): {owners}")

    def test_a_centroid_on_a_tile_boundary_is_counted_once(self):
        tiles = tiling.plan_tiles(img(1200, 1000), 600, 133)
        for x, y in [(600.0, 600.0), (599.5, 599.5), (600.5, 600.5), (0.0, 0.0),
                     (1200.0, 1000.0), (1199.9, 999.9), (600.0, 0.0), (0.0, 600.0)]:
            owners = [t.tile for t in tiles if tiling.tile_owns(t, x, y)]
            self.assertEqual(len(owners), 1, f"({x}, {y}) -> {owners}")
        # an inner boundary belongs to the tile to the right of and below it
        self.assertEqual([t.tile for t in tiles if tiling.tile_owns(t, 600.0, 600.0)],
                         ["a1_r01c01"])
        # the outer edge belongs to the last tile, which is why it is inclusive there
        self.assertEqual([t.tile for t in tiles if tiling.tile_owns(t, 1200.0, 1000.0)],
                         ["a1_r01c01"])

    def test_single_tile_keeps_the_image_name_and_no_padding(self):
        i = img(800, 600, image="9000L_20x_a1")
        for tile_px in (0, -1, 800, 2048):
            with self.subTest(tile_px=tile_px):
                tiles = tiling.plan_tiles(i, tile_px, 133)
                self.assertEqual(len(tiles), 1)
                t = tiles[0]
                self.assertEqual(t.tile, i.image)
                self.assertEqual((t.margin, t.x0, t.y0, t.w, t.h), (0, 0, 0, 800, 600))
                self.assertEqual((t.core_x0, t.core_y0, t.core_x1, t.core_y1), (0, 0, 800, 600))
                self.assertTrue(t.is_right and t.is_bottom)
                self.assertEqual(t.core_px, 800 * 600)

    def test_tile_names_and_geometry_of_a_four_tile_image(self):
        tiles = tiling.plan_tiles(img(1200, 1000), 600, 133)
        self.assertEqual([t.tile for t in tiles],
                         ["a1_r00c00", "a1_r00c01", "a1_r01c00", "a1_r01c01"])
        first, last = tiles[0], tiles[-1]
        self.assertEqual((first.x0, first.y0, first.w, first.h), (0, 0, 733, 733))
        self.assertEqual((first.core_x0, first.core_y0, first.core_x1, first.core_y1),
                         (0, 0, 600, 600))
        self.assertFalse(first.is_right or first.is_bottom)
        self.assertEqual((last.x0, last.y0, last.w, last.h), (467, 467, 733, 533))
        self.assertTrue(last.is_right and last.is_bottom)

    def test_zero_sized_image_is_refused(self):
        for w, h in [(0, 10), (10, 0), (-1, 5)]:
            with self.assertRaises(ValueError):
                tiling.tile_grid(w, h, 600, 133)


class TestMargin(unittest.TestCase):
    def test_the_widest_step_sets_the_margin(self):
        self.assertEqual(tiling.derive_margin_px(130.0, 60, 8.0, 100), 133)    # a whole cell body
        self.assertEqual(tiling.derive_margin_px(35.0, 60, 8.0, 100), 100)     # rolling ball
        self.assertEqual(tiling.derive_margin_px(35.0, 200, 8.0, 100), 200)    # Niblack window
        self.assertEqual(tiling.derive_margin_px(35.0, 10, 50.0, 10), 151)     # 3 sigma
        self.assertEqual(tiling.derive_margin_px(0.0, 0, 0.0, 0), 3)


class TestValidation(unittest.TestCase):
    def test_a_tile_must_hold_four_cell_diameters(self):
        with self.assertRaises(ValueError):
            tiling.plan_run([img(4000, 4000)], 400, 133, settings=SETTINGS)
        # an image that already fits in one tile is never padded, so nothing to check
        tiling.plan_run([img(300, 300)], 400, 133, settings=SETTINGS)
        tiling.plan_run([img(4000, 4000)], 0, 0, settings=SETTINGS)

    def test_margin_may_not_swamp_the_core(self):
        with self.assertRaises(ValueError):
            tiling.validate_tiling(600, 400, 130.0, 4000, 4000)
        with self.assertRaises(ValueError):
            tiling.validate_tiling(600, -1, 130.0)
        tiling.validate_tiling(600, 133, 130.0, 4000, 4000)


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rbpms-plan-")
        self.addCleanup(self.tmp.cleanup)

    def test_plan_run_only_redoes_the_missing_tiles(self):
        i = img(1200, 1000)
        names = [t.tile for t in tiling.plan_tiles(i, 600, 133)]
        self.assertEqual(len(names), 4)
        done = {("9000L", names[0]), "9000L/" + names[2]}       # both key shapes are accepted

        plan = tiling.plan_run([i], 600, 133, done=done, settings=SETTINGS)
        # the whole geometry is kept: the counting script needs it to crop and to draw the overview
        self.assertEqual([t.tile for t in plan.tiles], names)
        self.assertEqual([t.tile for t in plan.todo_tiles], [names[1], names[3]])

        redo = tiling.plan_run([i], 600, 133, done=done, overwrite=True, settings=SETTINGS)
        self.assertEqual([t.tile for t in redo.todo_tiles], names)

        nothing = tiling.plan_run([i], 600, 133, done={("9000L", n) for n in names},
                                  settings=SETTINGS)
        self.assertEqual(nothing.images, ())
        self.assertEqual(nothing.tiles, ())

    def test_unreadable_images_are_left_out(self):
        good, bad = img(800, 600, image="a1"), img(0, 0, image="a2", problem="Unknown format")
        plan = tiling.plan_run([good, bad], 600, 133, settings=SETTINGS)
        self.assertEqual([i.image for i in plan.images], ["a1"])

    def test_plan_json_is_what_the_groovy_reads(self):
        i = img(1200, 1000, file="C:/x/a1.czi", format="Zeiss CZI", z=2, channels=2,
                um_per_px=0.227)
        plan = tiling.plan_run([i], 600, 133, settings=SETTINGS, skip_empty_tiles=True,
                               tissue_fraction=0.1)
        path = tiling.write_plan(Path(self.tmp.name) / "plan.json", plan)
        obj = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((obj["tile_px"], obj["margin_px"]), (600, 133))
        self.assertEqual((obj["count_tiles"], obj["materialize_tiles"]), (True, False))
        self.assertEqual((obj["skip_empty_tiles"], obj["tissue_fraction"]), (True, 0.1))
        self.assertEqual(len(obj["images"]), 1)
        one = obj["images"][0]
        self.assertEqual((one["sample"], one["image"], one["um_per_px"]), ("9000L", "a1", 0.227))
        self.assertEqual(len(one["tiles"]), 4)
        for t in one["tiles"]:
            self.assertGreaterEqual(set(t), {"tile", "col", "row", "x0", "y0", "w", "h", "core_x0",
                                             "core_y0", "core_x1", "core_y1", "margin", "is_right",
                                             "is_bottom", "todo", "core_px"})
        self.assertEqual(sum(t["core_px"] for t in one["tiles"]), 1200 * 1000)


if __name__ == "__main__":
    unittest.main()
