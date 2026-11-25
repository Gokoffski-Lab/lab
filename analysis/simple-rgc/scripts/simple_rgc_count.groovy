#@ String (persist=false) inputDir
#@ String (persist=false) outputDir
#@ Integer (value=1, persist=false) channel
#@ Double (value=35.0, persist=false) minDiameterPx
#@ Double (value=130.0, persist=false) maxDiameterPx
#@ Integer (value=20, persist=false) localThresholdRadius
#@ Double (value=3.0, persist=false) gaussianSigma
#@ Boolean (value=false, persist=false) removeAxons
#@ Boolean (value=false, persist=false) overwrite
#@ String (value="", persist=false) onlyFiles
#@ Boolean (value=true, persist=false) exitWhenDone
#@ Double (value=1.15, persist=false) minContrast
#@ Integer (value=100, persist=false) bgRadiusPx

/*
 * Headless Simple RGC counter.
 *
 * Re-implements simplergc.services.CellSegmentationService.extractCells
 * (Cross et al. 2021, JORS 9:15; github.com/sonjoonho/SimpleRGC) call-for-call,
 * using the Fiji components the plugin itself depends on, so it runs headless
 * without the plugin's dialogs or the plugin being installed:
 *   8-bit -> Niblack local threshold -> [axon removal] -> Gaussian blur ->
 *   autoThreshold -> EDM watershed -> ParticleAnalyzer (area from diameter range)
 *
 * Input:  every .czi/.tif/.tiff/.lif/.nd2 under inputDir (all series, Z max-projected).
 * Output (under outputDir):
 *   counts/field_counts.csv           one row per image/series (appended; resumable)
 *   cells/<sample>/<image>_cells.csv  per-cell measurements on the raw image
 *   rois/<sample>/<image>_rois.zip    ImageJ ROI sets
 *   overlays/<sample>/<image>_overlay.jpg  QC overlay (outlines on contrast-stretched raw)
 *   review/<sample>/<image>.tif       original pixels + calibration + outlines as an ImageJ overlay,
 *                                     opened by review_counts.groovy for manual correction
 *   logs/count_log.txt
 */

import ij.IJ
import ij.ImagePlus
import ij.Prefs
import ij.gui.Overlay
import ij.gui.PolygonRoi
import ij.gui.Roi
import ij.gui.ShapeRoi
import ij.plugin.filter.BackgroundSubtracter
import ij.io.RoiEncoder
import ij.measure.Calibration
import ij.measure.Measurements
import ij.measure.ResultsTable
import ij.plugin.ChannelSplitter
import ij.plugin.ZProjector
import ij.plugin.filter.Analyzer
import ij.plugin.filter.EDM
import ij.plugin.filter.ParticleAnalyzer
import ij.plugin.frame.RoiManager
import ij.process.AutoThresholder
import ij.process.FloatPolygon
import ij.process.ImageConverter
import fiji.threshold.Auto_Local_Threshold
import de.biomedical_imaging.ij.steger.LineDetector
import loci.plugins.BF
import loci.plugins.in.ImporterOptions
import java.awt.Color
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

// ---- constants copied from CellSegmentationService.kt ----
final int CONTRAST_LOW = 87
final int CONTRAST_HIGH = 230
final double THRESHOLD_MULTIPLIER = 0.17
final double AXON_WIDTH = 3.5

Prefs.blackBackground = true   // Fiji default; makes white = foreground for EDM/ParticleAnalyzer

def out = new File(outputDir)
["counts", "cells", "rois", "overlays", "review", "logs"].each { new File(out, it).mkdirs() }
def logFile = new File(out, "logs/count_log.txt")
def log = { String s -> def line = "[${new Date().format('yyyy-MM-dd HH:mm:ss')}] $s"; println line; logFile << line + "\n" }

def countsFile = new File(out, "counts/field_counts.csv")
def header = "sample,image,series,file,width_px,height_px,pixel_um,field_area_mm2,n_simplergc,density_simplergc_per_mm2," +
        "n_filtered,density_filtered_per_mm2,median_area_um2,median_diameter_um,channel,min_diam_px,max_diam_px,radius_px,sigma," +
        "remove_axons,min_contrast,seconds"
if (!countsFile.exists()) countsFile.text = header + "\n"
def done = [] as Set
countsFile.readLines().drop(1).each { def p = it.split(","); if (p.length > 2) done << (p[3] + "#" + p[2]) }

// ---------------- Simple RGC algorithm ----------------
double estimateSigma(double w) { w / (2 * Math.sqrt(3.0)) + 0.5 }
double estimateThreshold(double w, double sigma, int contrast, double mult) {
    Math.floor(Math.abs(-2 * contrast * (w / 2.0) / (Math.sqrt(2 * Math.PI) * Math.pow(sigma, 3)) *
            Math.exp(-((w / 2.0) * (w / 2.0)) / (2 * sigma * sigma))) * mult)
}

List<Roi> detectAxons(ImagePlus image, double axonWidth, int lo, int hi, double mult) {
    double sigma = estimateSigma(axonWidth)
    double lowerThresh = estimateThreshold(axonWidth, sigma, lo, mult)
    double upperThresh = estimateThreshold(axonWidth, sigma, hi, mult)
    def contours = new LineDetector().detectLines(image.getProcessor(), sigma, upperThresh, lowerThresh,
            0.0d, Double.MAX_VALUE, false, true, true, true)
    def axons = []
    for (c in contours) {
        def r = new PolygonRoi(new FloatPolygon(c.getXCoordinates(), c.getYCoordinates(), c.getNumber()), Roi.FREELINE)
        double sum = 0
        for (int j = 0; j < c.getLineWidthL().length; j++) sum += c.getLineWidthL()[j] + c.getLineWidthR()[j]
        r.setStrokeWidth((float) (sum / c.getXCoordinates().length))
        axons << r
    }
    return axons
}

Roi[] extractCells(ImagePlus image, double minD, double maxD, int radius, double sigma, boolean rmAxons) {
    def m = image.duplicate()
    // preprocessImage
    new ImageConverter(m).convertToGray8()
    new Auto_Local_Threshold().exec(m, "Niblack", radius, 0.0d, 0.0d, true)
    if (rmAxons) {
        m.getProcessor().setColor(Color.BLACK)
        detectAxons(m, AXON_WIDTH, CONTRAST_LOW, CONTRAST_HIGH, THRESHOLD_MULTIPLIER).each { it.drawPixels(m.getProcessor()) }
    }
    m.getChannelProcessor().blurGaussian(sigma)
    m.getProcessor().setAutoThreshold(AutoThresholder.Method.Otsu, true)
    m.getProcessor().autoThreshold()
    // segmentImage
    new EDM().toWatershed(m.getChannelProcessor())
    // identifyCells
    double minA = Math.pow(minD / 2, 2) * Math.PI
    double maxA = Math.pow(maxD / 2, 2) * Math.PI
    m.setCalibration(new Calibration())   // areas in px, as in the plugin's dialog units
    // The plugin collects ROIs with a DummyRoiManager; a RoiManager is an AWT Frame and
    // cannot be built headless, so collect the same traced outlines via the overlay instead.
    m.setOverlay(null)
    new ParticleAnalyzer(ParticleAnalyzer.SHOW_OVERLAY_OUTLINES,
            Measurements.ALL_STATS, new ResultsTable(), minA, maxA).analyze(m)
    def ov = m.getOverlay()
    Roi[] rois = ov ? ov.toArray().findAll { !(it instanceof ij.gui.TextRoi) } as Roi[] : new Roi[0]
    rois.each { it.setStrokeColor(null); it.setName(null) }
    m.close()
    return rois
}

// ---------------- helpers ----------------
def openAll(File f) {
    def o = new ImporterOptions()
    o.setId(f.absolutePath); o.setOpenAllSeries(true); o.setAutoscale(true)
    o.setVirtual(false); o.setQuiet(true); o.setWindowless(true)
    return BF.openImagePlus(o)
}

def morphologyChannel(ImagePlus imp, int ch) {
    if (imp.getNChannels() < ch) throw new IllegalArgumentException("channel $ch requested, image has ${imp.getNChannels()}")
    def c = imp.getNChannels() > 1 ? ChannelSplitter.split(imp)[ch - 1] : imp
    if (c.getNSlices() > 1) c = ZProjector.run(c, "max")
    c.resetDisplayRange()      // = BF autoscale (min..max) used by convertToGray8
    return c
}

def saveRois(Roi[] rois, File zip) {
    def zos = new ZipOutputStream(new FileOutputStream(zip))
    def dos = new DataOutputStream(new BufferedOutputStream(zos))
    def enc = new RoiEncoder(dos)
    rois.eachWithIndex { r, i ->
        zos.putNextEntry(new ZipEntry(String.format("cell_%04d.roi", i + 1)))
        enc.write(r); dos.flush()
    }
    dos.close()
}

def median(List<Double> v) {
    if (!v) return Double.NaN
    def s = v.sort(false); int n = s.size()
    n % 2 ? s[n.intdiv(2)] : (s[n.intdiv(2) - 1] + s[n.intdiv(2)]) / 2
}

// ---------------- main loop ----------------
def exts = ~/(?i).*\.(czi|tif|tiff|lif|nd2|ome\.tif)$/
def files = []
new File(inputDir).eachFileRecurse { if (it.isFile() && it.name ==~ exts) files << it }
files.sort { it.absolutePath }
if (onlyFiles?.trim()) {
    def want = onlyFiles.split(";")*.trim() as Set
    files = files.findAll { want.contains(it.name) }
}
log("Simple RGC headless: ${files.size()} files; ch=$channel diam=${minDiameterPx}-${maxDiameterPx}px radius=$localThresholdRadius sigma=$gaussianSigma axons=$removeAxons")

files.each { File f ->
    def sample = f.getParentFile().getName()
    ImagePlus[] series
    try { series = openAll(f) } catch (e) { log("ERROR opening ${f}: ${e}"); return }
    series.eachWithIndex { ImagePlus imp, int s ->
        def key = f.absolutePath.replace(",", "_") + "#" + s
        if (!overwrite && done.contains(key)) { log("skip (done) ${f.name} s$s"); return }
        long t0 = System.currentTimeMillis()
        try {
            def base = f.name.replaceAll(/\.[^.]+$/, "") + (series.length > 1 ? "_s${s}" : "")
            def ch = morphologyChannel(imp, channel)
            def cal = imp.getCalibration()
            double um = (cal.scaled() && cal.getUnit() in ["micron", "µm", "um", "microns"]) ? cal.pixelWidth : Double.NaN
            def rois = extractCells(ch, minDiameterPx, maxDiameterPx, localThresholdRadius, gaussianSigma, removeAxons)

            // per-cell measurements on the raw (unscaled-intensity) morphology channel
            ch.setCalibration(new Calibration())
            def cellRows = new StringBuilder("cell,x_px,y_px,area_px,area_um2,eq_diameter_um,perimeter_px,circularity,solidity,feret_px,mean_intensity,integrated_density,bg_mean,contrast,pass_contrast\n")
            def areasUm = []
            def pass = new boolean[rois.length]
            // Background model: rolling-ball (radius >> soma radius) estimate of the diffuse
            // widefield haze. contrast = soma mean / background mean under the soma.
            def bgIp = ch.getProcessor().convertToFloat().duplicate()
            new BackgroundSubtracter().rollingBallBackground(bgIp, bgRadiusPx, true, false, false, true, true)
            def bgImp = new ImagePlus("bg", bgIp)
            rois.eachWithIndex { Roi r, int i ->
                bgImp.setRoi(r)
                double ringMed = bgImp.getStatistics(Measurements.MEAN).mean
                ch.setRoi(r)
                def st = ch.getStatistics(Measurements.AREA | Measurements.MEAN | Measurements.CENTROID)
                double contrast = (ringMed > 0) ? st.mean / ringMed : Double.NaN
                pass[i] = Double.isNaN(contrast) || contrast >= minContrast
                double per = r.getLength()
                double circ = per > 0 ? 4 * Math.PI * st.area / (per * per) : 0
                def hull = r.getFloatConvexHull()
                double hullA = hull ? new PolygonRoi(hull, Roi.POLYGON).getStatistics().area : st.area
                double aUm = Double.isNaN(um) ? Double.NaN : st.area * um * um
                areasUm << aUm
                cellRows << String.format(Locale.US, "%d,%.1f,%.1f,%.0f,%.2f,%.2f,%.1f,%.3f,%.3f,%.1f,%.1f,%.0f,%.1f,%.4f,%d\n",
                        i + 1, st.xCentroid, st.yCentroid, st.area, aUm, 2 * Math.sqrt(aUm / Math.PI), per,
                        Math.min(circ, 1.0), hullA > 0 ? st.area / hullA : 1, r.getFeretValues()[0], st.mean, st.mean * st.area,
                        ringMed, contrast, pass[i] ? 1 : 0)
            }
            int nPass = 0
            for (boolean b : pass) if (b) nPass++
            ch.killRoi()
            def cellsDir = new File(out, "cells/$sample"); cellsDir.mkdirs()
            new File(cellsDir, base + "_cells.csv").text = cellRows.toString()
            def roiDir = new File(out, "rois/$sample"); roiDir.mkdirs()
            saveRois(rois, new File(roiDir, base + "_rois.zip"))

            // Review TIFF: the original pixel data (as acquired, with spatial calibration) with the
            // automated outlines stored as an ImageJ overlay. scripts/review_counts.groovy opens these
            // for manual correction, and the reviewed points are saved back into the same overlay.
            def rev = new ImagePlus(base, ch.getProcessor().duplicate())
            rev.setCalibration(cal.copy())
            def rov = new Overlay()
            rois.eachWithIndex { Roi r, int i ->
                def c = (Roi) r.clone()
                c.setStrokeColor(pass[i] ? Color.MAGENTA : Color.CYAN)
                c.setStrokeWidth(pass[i] ? 1.5 : 1.0)
                c.setName((pass[i] ? "auto_kept_" : "auto_rejected_") + (i + 1))
                rov.add(c)
            }
            rev.setOverlay(rov)
            rev.resetDisplayRange(); IJ.run(rev, "Enhance Contrast", "saturated=0.35")   // display only
            rev.setProperty("Info", "source=${f.absolutePath}\nseries=${s}\nchannel=${channel}\n" +
                    "radius_px=${localThresholdRadius}\nsigma=${gaussianSigma}\nmin_diam_px=${minDiameterPx}\n" +
                    "max_diam_px=${maxDiameterPx}\nmin_contrast=${minContrast}\nn_auto_kept=${nPass}\nn_auto_all=${rois.length}\n")
            def revDir = new File(out, "review/$sample"); revDir.mkdirs()
            IJ.saveAsTiff(rev, new File(revDir, base + ".tif").absolutePath)
            rev.close()

            // QC overlay
            def vis = ch.duplicate(); vis.resetDisplayRange()
            IJ.run(vis, "Enhance Contrast", "saturated=0.35"); IJ.run(vis, "8-bit", ""); IJ.run(vis, "RGB Color", "")
            def ov = new Overlay()
            rois.eachWithIndex { Roi r, int i ->
                def c = (Roi) r.clone(); c.setStrokeColor(pass[i] ? Color.MAGENTA : Color.CYAN); c.setStrokeWidth(2); ov.add(c)
            }
            vis.setOverlay(ov)
            def flat = vis.flatten()
            def ip = flat.getProcessor(); ip.setColor(Color.YELLOW); ip.setFont(new java.awt.Font("SansSerif", java.awt.Font.BOLD, 40))
            ip.drawString("${base}  SimpleRGC n=${rois.length}  contrast>=${minContrast}: n=${nPass}  (magenta=kept, cyan=rejected)", 20, 60)
            def ovDir = new File(out, "overlays/$sample"); ovDir.mkdirs()
            IJ.saveAs(flat, "Jpeg", new File(ovDir, base + "_overlay.jpg").absolutePath)

            double areaMm2 = Double.isNaN(um) ? Double.NaN : ch.getWidth() * ch.getHeight() * um * um / 1e6
            double medA = median(areasUm.findAll { !Double.isNaN(it) })
            double secs = (System.currentTimeMillis() - t0) / 1000.0
            countsFile << String.format(Locale.US, "%s,%s,%d,%s,%d,%d,%.4f,%.5f,%d,%.1f,%d,%.1f,%.1f,%.2f,%d,%.1f,%.1f,%d,%.2f,%s,%.2f,%.1f\n",
                    sample, base, s, f.absolutePath.replace(",", "_"), ch.getWidth(), ch.getHeight(), um, areaMm2,
                    rois.length, rois.length / areaMm2, nPass, nPass / areaMm2, medA, 2 * Math.sqrt(medA / Math.PI),
                    channel, minDiameterPx, maxDiameterPx, localThresholdRadius, gaussianSigma, removeAxons, minContrast, secs)
            log(String.format(Locale.US, "%s: SimpleRGC %d cells (%.0f /mm2); contrast-filtered %d (%.0f /mm2) in %.1fs",
                    base, rois.length, rois.length / areaMm2, nPass, nPass / areaMm2, secs))
            vis.close(); flat.close(); ch.close()
        } catch (e) {
            log("ERROR ${f.name} s$s: ${e}")
            e.printStackTrace()
        }
        imp.close()
    }
}
log("done")
if (exitWhenDone) System.exit(0)   // Bio-Formats/AWT threads otherwise keep the headless JVM alive
