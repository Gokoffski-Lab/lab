#@ String (persist=false) inputDir
#@ String (persist=false) outputDir
#@ Integer (value=1, persist=false) channel
#@ Double (value=35.0, persist=false) minDiameterPx
#@ Double (value=130.0, persist=false) maxDiameterPx
#@ Integer (value=60, persist=false) localThresholdRadius
#@ Double (value=8.0, persist=false) gaussianSigma
#@ Double (value=1.15, persist=false) minContrast
#@ Integer (value=100, persist=false) bgRadiusPx
#@ Boolean (value=false, persist=false) overwrite
#@ Boolean (value=true, persist=false) exitWhenDone
#@ String (value="", required=false, persist=false) onlyAnimals

/*
 * Automated RGC count with the Simple RGC method (Cross et al. 2021, J Open Res Softw 9:15).
 *
 * Runs the same steps as the plugin's CellSegmentationService.extractCells, without the plugin's
 * dialogs, so it works headless and without installing the plugin:
 *   8-bit -> Niblack local threshold -> Gaussian blur -> Otsu threshold -> watershed -> size filter
 * then keeps objects at least `minContrast` x brighter than the local background.
 *
 * Input:  every .czi/.tif/.tiff/.lif/.nd2 in <inputDir>/<sample>/ (Z-stacks are max-projected)
 * Output (in outputDir):
 *   counted/<sample>/<image>.tif   original image with the counted cells outlined (open in Fiji)
 *   counted/<sample>/<image>.jpg   quick-look picture of the same
 *   counts/auto_counts.csv         one row per image
 *   log.txt
 * Images already in auto_counts.csv are skipped unless overwrite=true.
 */

import ij.IJ
import ij.ImagePlus
import ij.Prefs
import ij.gui.Overlay
import ij.gui.Roi
import ij.measure.Calibration
import ij.measure.Measurements
import ij.measure.ResultsTable
import ij.plugin.ChannelSplitter
import ij.plugin.ZProjector
import ij.plugin.filter.BackgroundSubtracter
import ij.plugin.filter.EDM
import ij.plugin.filter.ParticleAnalyzer
import ij.process.AutoThresholder
import ij.process.ImageConverter
import fiji.threshold.Auto_Local_Threshold
import loci.plugins.BF
import loci.plugins.in.ImporterOptions
import java.awt.Color

Prefs.blackBackground = true

def out = new File(outputDir)
["counted", "counts"].each { new File(out, it).mkdirs() }
def logFile = new File(out, "log.txt")
def log = { String s -> def line = "[${new Date().format('yyyy-MM-dd HH:mm:ss')}] $s"; println line; logFile << line + "\n" }

def countsFile = new File(out, "counts/auto_counts.csv")
def header = "sample,image,auto_count,objects_detected,file,counted_at"
if (!countsFile.exists()) countsFile.text = header + "\n"
def done = [] as Set
countsFile.readLines().drop(1).each { def p = it.split(","); if (p.length > 1) done << (p[0] + "/" + p[1]) }

// ---- Simple RGC segmentation (CellSegmentationService.extractCells, without axon removal) ----
Roi[] extractCells(ImagePlus image, double minD, double maxD, int radius, double sigma) {
    def m = image.duplicate()
    new ImageConverter(m).convertToGray8()
    new Auto_Local_Threshold().exec(m, "Niblack", radius, 0.0d, 0.0d, true)
    m.getChannelProcessor().blurGaussian(sigma)
    m.getProcessor().setAutoThreshold(AutoThresholder.Method.Otsu, true)
    m.getProcessor().autoThreshold()
    new EDM().toWatershed(m.getChannelProcessor())
    double minA = Math.pow(minD / 2, 2) * Math.PI
    double maxA = Math.pow(maxD / 2, 2) * Math.PI
    m.setCalibration(new Calibration())
    m.setOverlay(null)
    // outlines are collected from the overlay because the ROI Manager cannot open headless
    new ParticleAnalyzer(ParticleAnalyzer.SHOW_OVERLAY_OUTLINES, Measurements.AREA, new ResultsTable(), minA, maxA).analyze(m)
    def ov = m.getOverlay()
    Roi[] rois = ov ? ov.toArray().findAll { !(it instanceof ij.gui.TextRoi) } as Roi[] : new Roi[0]
    m.close()
    return rois
}

def openAll(File f) {
    def o = new ImporterOptions()
    o.setId(f.absolutePath); o.setOpenAllSeries(true); o.setAutoscale(true)
    o.setVirtual(false); o.setQuiet(true); o.setWindowless(true)
    return BF.openImagePlus(o)
}

def exts = ~/(?i).*\.(czi|tif|tiff|lif|nd2)$/
def files = []
// skip hidden files, including the "._" copies macOS leaves on shared and USB drives
new File(inputDir).eachFileRecurse { if (it.isFile() && it.name ==~ exts && !it.name.startsWith(".")) files << it }
files.sort { it.absolutePath }
int skipped = 0
def wantAnimals = onlyAnimals?.trim() ? (onlyAnimals.split(/[;, ]+/)*.trim().findAll { it } as Set) : null
if (wantAnimals) log("Only animals: ${wantAnimals.sort().join(', ')}")
log("Counting ${files.size()} files: diameter ${minDiameterPx}-${maxDiameterPx} px, radius ${localThresholdRadius}, sigma ${gaussianSigma}, brightness >= ${minContrast}")

files.each { File f ->
    // retina = the folder the image is in; an image directly in inputDir is its own retina
    def inRoot = f.getParentFile().getCanonicalPath() == new File(inputDir).getCanonicalPath()
    def sample = (inRoot ? f.name.replaceAll(/\.[^.]+$/, "") : f.getParentFile().getName()).replace(",", "_")
    if (wantAnimals) {   // only the listed animals: the number at the start of the retina name
        def m = (sample =~ /^(\d+)/)
        if (!m.find() || !wantAnimals.contains(m.group(1))) return
    }
    def base = f.name.replaceAll(/\.[^.]+$/, "").replace(",", "_")
    if (!overwrite && (done.contains(sample + "/" + base) || done.contains(sample + "/" + base + "_s0"))) { skipped++; return }
    ImagePlus[] series
    try { series = openAll(f) } catch (e) { log("ERROR opening ${f}: ${e}"); return }
    series.eachWithIndex { ImagePlus imp, int s ->
        def image = (f.name.replaceAll(/\.[^.]+$/, "") + (series.length > 1 ? "_s${s}" : "")).replace(",", "_")
        if (!overwrite && done.contains(sample + "/" + image)) { imp.close(); return }
        try {
            def ch = imp.getNChannels() > 1 ? ChannelSplitter.split(imp)[channel - 1] : imp
            if (ch.getNSlices() > 1) ch = ZProjector.run(ch, "max")
            ch.resetDisplayRange()
            def cal = imp.getCalibration().copy()
            def rois = extractCells(ch, minDiameterPx, maxDiameterPx, localThresholdRadius, gaussianSigma)

            // brightness filter: object mean / rolling-ball background under the object
            ch.setCalibration(new Calibration())
            def bgIp = ch.getProcessor().convertToFloat().duplicate()
            new BackgroundSubtracter().rollingBallBackground(bgIp, bgRadiusPx, true, false, false, true, true)
            def bgImp = new ImagePlus("bg", bgIp)
            def pass = rois.collect { Roi r ->
                bgImp.setRoi(r); double bg = bgImp.getStatistics(Measurements.MEAN).mean
                ch.setRoi(r); double mean = ch.getStatistics(Measurements.MEAN).mean
                bg <= 0 || mean / bg >= minContrast
            }
            ch.killRoi()
            int n = pass.count { it }

            // counted image: original pixels, calibration, outlines as an overlay
            def tif = new ImagePlus(image, ch.getProcessor().duplicate())
            tif.setCalibration(cal)
            def ov = new Overlay()
            rois.eachWithIndex { Roi r, int i ->
                def c = (Roi) r.clone()
                c.setStrokeColor(pass[i] ? Color.MAGENTA : Color.CYAN)
                c.setStrokeWidth(pass[i] ? 1.5 : 1.0)
                c.setName((pass[i] ? "auto_kept_" : "auto_rejected_") + (i + 1))
                ov.add(c)
            }
            tif.setOverlay(ov)
            tif.resetDisplayRange(); IJ.run(tif, "Enhance Contrast", "saturated=0.35")   // display only
            def dir = new File(out, "counted/$sample"); dir.mkdirs()
            IJ.saveAsTiff(tif, new File(dir, image + ".tif").absolutePath)

            def jpg = tif.duplicate(); jpg.setOverlay(ov.duplicate())
            IJ.run(jpg, "8-bit", ""); IJ.run(jpg, "RGB Color", "")
            def flat = jpg.flatten()
            def ip = flat.getProcessor(); ip.setColor(Color.YELLOW); ip.setFont(new java.awt.Font("SansSerif", java.awt.Font.BOLD, 40))
            ip.drawString("${image}   automated count ${n}   (magenta counted, cyan too dim)", 20, 60)
            IJ.saveAs(flat, "Jpeg", new File(dir, image + ".jpg").absolutePath)

            countsFile << "${sample},${image},${n},${rois.length},${f.absolutePath.replace(',', '_')},${new Date().format('yyyy-MM-dd HH:mm')}\n"
            log("$image: $n cells")
            [tif, jpg, flat, ch].each { it.close() }
        } catch (e) {
            log("ERROR ${image}: ${e}")
        }
        imp.close()
    }
}
if (skipped) log("${skipped} files were counted before and were skipped")
log("done")
if (exitWhenDone) System.exit(0)
