#@ String (persist=false) outDir
#@ Boolean (value=true, persist=false) exitWhenDone

/*
 * Synthetic images for tests/test_pipeline_fiji.py. Nothing binary is committed: the test asks
 * Fiji to build these in a temporary folder and throws them away afterwards.
 *
 * <outDir>/9000L/9000L_a1.tif       1200x1000, 16-bit, 2 channels, 2 Z slices, calibrated
 *                                   0.227 um/px. 35 disks of diameter 61 px on channel 1, spread
 *                                   over both Z slices (so the max projection is needed), on a
 *                                   150 px grid that puts cells exactly on the tile boundaries
 *                                   x=600 and y=500. Channel 2 holds four much larger blobs, so
 *                                   counting the wrong channel gives an obviously wrong answer.
 * <outDir>/9000L/9000L_a2.ics       400x300, written by Bio-Formats: a non-TIFF source that has
 *                                   to be normalized to .tif. 2 cells.
 * <outDir>/9000L/9000L_dpi.tif      300x300, no calibration at all: the pixel size must come out
 *                                   unknown rather than the 72-dpi "353 um". 2 cells.
 * <outDir>/9000L/9000L_broken.tif   not an image: inspect must record a problem and carry on.
 *
 * The disks are drawn symmetrically about an integer centre. A symmetric mask stays symmetric
 * through blurring and thresholding, so the traced outline has its centroid exactly on the axis
 * whatever threshold a tile happens to pick -- which is what makes the boundary cells land on one
 * side of the core bound and only one.
 */

import ij.IJ
import ij.ImagePlus
import ij.ImageStack
import ij.measure.Calibration
import ij.process.ShortProcessor
import loci.common.DataTools
import loci.formats.FormatTools
import loci.formats.ImageWriter
import loci.formats.MetadataTools

ShortProcessor flat(int w, int h, int value) {
    def ip = new ShortProcessor(w, h)
    def px = (short[]) ip.getPixels()
    short v = (short) value
    for (int i = 0; i < px.length; i++) px[i] = v
    return ip
}

void disk(ShortProcessor ip, int cx, int cy, int r, int value) {
    for (int y = Math.max(0, cy - r); y <= Math.min(ip.getHeight() - 1, cy + r); y++) {
        int dy = y - cy
        for (int x = Math.max(0, cx - r); x <= Math.min(ip.getWidth() - 1, cx + r); x++) {
            int dx = x - cx
            if (dx * dx + dy * dy <= r * r) ip.set(x, y, value)
        }
    }
}

int BG = 2000, FG = 40000, R = 30
def dir = new File(outDir, "9000L")
dir.mkdirs()

// ---- a1: the real test subject ----
def centres = []
[150, 300, 450, 600, 750, 900, 1050].each { int x ->
    [150, 300, 600, 750, 880].each { int y -> centres << [x, y] }
}
def stain = [flat(1200, 1000, BG), flat(1200, 1000, BG)]
centres.eachWithIndex { c, int i -> disk(stain[i % 2], (int) c[0], (int) c[1], R, FG) }
def other = [flat(1200, 1000, BG), flat(1200, 1000, BG)]
[[200, 200], [500, 700], [800, 400], [1000, 800]].eachWithIndex { c, int i ->
    disk(other[i % 2], (int) c[0], (int) c[1], 50, FG)
}
def st = new ImageStack(1200, 1000)
// the default dimension order is XYCZT, so the channel index runs fastest
for (int z = 0; z < 2; z++) { st.addSlice("c1z${z}", stain[z]); st.addSlice("c2z${z}", other[z]) }
def a1 = new ImagePlus("9000L_a1", st)
a1.setDimensions(2, 2, 1)
def cal = new Calibration()
cal.pixelWidth = 0.227d
cal.pixelHeight = 0.227d
cal.setUnit("micron")
a1.setCalibration(cal)
IJ.saveAsTiff(a1, new File(dir, "9000L_a1.tif").getAbsolutePath())
println "cells 9000L_a1=${centres.size()}"

// ---- a2: a non-TIFF source ----
def a2 = flat(400, 300, BG)
disk(a2, 120, 150, R, FG)
disk(a2, 280, 150, R, FG)
def meta = MetadataTools.createOMEXMLMetadata()
MetadataTools.populateMetadata(meta, 0, null, true, "XYZCT",
        FormatTools.getPixelTypeString(FormatTools.UINT16), 400, 300, 1, 1, 1, 1)
meta.setPixelsPhysicalSizeX(new ome.units.quantity.Length(0.227d, ome.units.UNITS.MICROMETER), 0)
meta.setPixelsPhysicalSizeY(new ome.units.quantity.Length(0.227d, ome.units.UNITS.MICROMETER), 0)
def writer = new ImageWriter()
writer.setMetadataRetrieve(meta)
writer.setId(new File(dir, "9000L_a2.ics").getAbsolutePath())
writer.saveBytes(0, DataTools.shortsToBytes((short[]) a2.getPixels(), true))
writer.close()
println "cells 9000L_a2=2"

// ---- dpi: no calibration ----
def dpi = flat(300, 300, BG)
disk(dpi, 100, 100, R, FG)
disk(dpi, 200, 200, R, FG)
IJ.saveAsTiff(new ImagePlus("9000L_dpi", dpi), new File(dir, "9000L_dpi.tif").getAbsolutePath())
println "cells 9000L_dpi=2"

// ---- broken ----
new File(dir, "9000L_broken.tif").setText("this file is deliberately not an image\n", "UTF-8")
println "done"
if (exitWhenDone) System.exit(0)
