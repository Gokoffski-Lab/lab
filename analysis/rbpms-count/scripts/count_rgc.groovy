#@ String (persist=false) inputDir
#@ String (persist=false) outputDir
#@ String (value="run", persist=false) mode
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
 * Two modes, both driven by scripts/rbpms.py:
 *
 * mode=inspect  Read the metadata of every image under <inputDir> with Bio-Formats and write
 *               counts/images.csv (one row per series). Nothing is decoded, so this is fast.
 *
 * mode=run      Do the work laid out in counts/plan.json (written by scripts/tiling.py):
 *                 normalized/<sample>/<image>.tif   the chosen channel, Z max-projected, plus a
 *                                                   .json sidecar recording where it came from
 *                 tiles/<sample>/<image>/<tile>.tif  padded tile, calibrated, TileSpec in "Info"
 *                 counted/<sample>/<tile>.tif/.jpg   core only, counted cells outlined
 *                 counted/<sample>/<image>.jpg       overview of a tiled image with the tile grid
 *                 rois/<sample>/<tile>_rois.csv      one row per detected object
 *                 counts/tiles.csv                   one row per tile
 *
 * A big image is cut into tiles whose *cores* partition it exactly once; each tile is segmented on
 * a window padded by plan.margin_px, and an object is counted by the one tile whose core holds its
 * centroid. That is why the per-tile counts add up to the untiled count.
 *
 * The source images are only ever read.
 */

import ij.IJ
import ij.ImagePlus
import ij.Prefs
import ij.gui.Overlay
import ij.gui.Roi
import ij.measure.Calibration
import ij.measure.Measurements
import ij.measure.ResultsTable
import ij.plugin.filter.BackgroundSubtracter
import ij.plugin.filter.EDM
import ij.plugin.filter.ParticleAnalyzer
import ij.process.AutoThresholder
import ij.process.ImageConverter
import ij.process.ImageProcessor
import ij.process.ImageStatistics
import fiji.threshold.Auto_Local_Threshold
import groovy.io.FileType
import groovy.io.FileVisitResult
import groovy.json.JsonOutput
import groovy.json.JsonSlurper
import loci.formats.ChannelSeparator
import loci.formats.MetadataTools
import loci.plugins.util.ImageProcessorReader
import loci.plugins.util.LociPrefs
import java.awt.Color
import java.awt.Font
import java.nio.file.Files
import java.nio.file.StandardCopyOption

// ---------------------------------------------------------------- methods
/** Simple RGC segmentation (CellSegmentationService.extractCells, without axon removal).
 *  dmin/dmax fix the 16-bit -> 8-bit mapping, so a tile and the whole image are thresholded
 *  identically instead of each being scaled to its own min and max. */
Roi[] extractCells(ImagePlus image, double minD, double maxD, int radius, double sigma,
                   double dmin, double dmax) {
    def m = image.duplicate()
    if (dmax > dmin) m.getProcessor().setMinAndMax(dmin, dmax)
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
    new ParticleAnalyzer(ParticleAnalyzer.SHOW_OVERLAY_OUTLINES, Measurements.AREA,
                         new ResultsTable(), minA, maxA).analyze(m)
    def ov = m.getOverlay()
    Roi[] rois = ov ? ov.toArray().findAll { !(it instanceof ij.gui.TextRoi) } as Roi[] : new Roi[0]
    m.close()
    return rois
}

/** One channel of one series as a single 2D plane: t=0, Z max-projected one plane at a time so a
 *  deep stack never sits in memory as a whole. */
ImagePlus readChannel(File f, int series, int channelIndex) {
    def r = new ImageProcessorReader(new ChannelSeparator(LociPrefs.makeImageReader()))
    try {
        r.setFlattenedResolutions(false)
        r.setId(f.getAbsolutePath())
        r.setSeries(series)
        int c = Math.min(Math.max(channelIndex, 0), Math.max(1, r.getSizeC()) - 1)
        int nz = Math.max(1, r.getSizeZ())
        ImageProcessor acc = null
        for (int z = 0; z < nz; z++) {
            def ip = r.openProcessors(r.getIndex(z, c, 0))[0]
            if (acc == null) { acc = ip; continue }
            int n = acc.getPixelCount()
            for (int i = 0; i < n; i++) { float b = ip.getf(i); if (b > acc.getf(i)) acc.setf(i, b) }
        }
        return new ImagePlus(f.getName(), acc)
    } finally {
        try { r.close() } catch (Throwable ignored) { }
    }
}

void saveTiffAtomic(ImagePlus imp, File target) {
    target.getParentFile().mkdirs()
    def tmp = new File(target.getParentFile(), "partial_" + target.getName())
    IJ.saveAsTiff(imp, tmp.getAbsolutePath())
    Files.move(tmp.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING)
}

void saveJpegAtomic(ImagePlus imp, File target) {
    target.getParentFile().mkdirs()
    def tmp = new File(target.getParentFile(), "partial_" + target.getName())
    IJ.saveAs(imp, "Jpeg", tmp.getAbsolutePath())
    Files.move(tmp.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING)
}

/** Intensity that separates tissue from background in the whole image, in raw pixel values.
 *  Taken once per image so every tile is judged against the same level. */
double tissueLevel(ImageProcessor ip) {
    def st = ImageStatistics.getStatistics(ip, Measurements.MIN_MAX, null)
    if (!(st.max > st.min)) return Double.MAX_VALUE
    int[] hist = new int[256]
    int w = ip.getWidth(), h = ip.getHeight()
    double span = st.max - st.min
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        int b = (int) ((ip.getf(x, y) - st.min) * 255.0d / span)
        hist[b < 0 ? 0 : (b > 255 ? 255 : b)]++
    }
    return st.min + (ip.getAutoThreshold(hist) + 0.5d) * span / 256.0d
}

double tissueFraction(ImageProcessor ip, int x0, int y0, int w, int h, double level) {
    long n = 0
    for (int y = y0; y < y0 + h; y++) for (int x = x0; x < x0 + w; x++) if (ip.getf(x, y) > level) n++
    return (double) n / ((long) w * (long) h)
}

/** Downsampled whole image with the tile cores and their counts drawn on it, so a tiled image
 *  can still be checked at a glance. */
void writeOverview(ImagePlus parent, List tiles, Map perTile, int total, String label, File target) {
    int w = parent.getWidth(), h = parent.getHeight()
    double scale = Math.min(1.0d, 1800.0d / Math.max(w, h))
    def ip = parent.getProcessor().duplicate()
    ip.setInterpolationMethod(ImageProcessor.BILINEAR)
    def o = new ImagePlus(label, ip.resize((int) Math.max(1, Math.round(w * scale)),
                                           (int) Math.max(1, Math.round(h * scale))))
    o.resetDisplayRange()
    IJ.run(o, "Enhance Contrast", "saturated=0.35")
    IJ.run(o, "8-bit", "")
    IJ.run(o, "RGB Color", "")
    def p = o.getProcessor()
    p.setFont(new Font("SansSerif", Font.BOLD, 18))
    tiles.each { t ->
        int x = (int) Math.round((t.core_x0 as int) * scale)
        int y = (int) Math.round((t.core_y0 as int) * scale)
        int tw = (int) Math.round(((t.core_x1 as int) - (t.core_x0 as int)) * scale)
        int th = (int) Math.round(((t.core_y1 as int) - (t.core_y0 as int)) * scale)
        def v = perTile[t.tile as String]
        p.setColor(v == null ? Color.GRAY : Color.YELLOW)
        p.drawRect(x, y, tw, th)
        p.drawString(v == null ? "not counted" : v.toString(), x + 8, y + 26)
    }
    p.setColor(Color.YELLOW)
    p.setFont(new Font("SansSerif", Font.BOLD, 26))
    p.drawString("${label}   ${tiles.size()} tiles   automated count ${total}", 12, o.getHeight() - 14)
    saveJpegAtomic(o, target)
    o.close()
}

String csvSafe(Object o) {
    return (o == null ? "" : o.toString()).replace(",", "_").replace("\n", " ").replace("\r", " ").trim()
}

// ---------------------------------------------------------------- set-up
Prefs.blackBackground = true
def out = new File(outputDir)
new File(out, "counts").mkdirs()
def logFile = new File(out, "log.txt")
def log = { String s -> def line = "[${new Date().format('yyyy-MM-dd HH:mm:ss')}] $s"; println line; logFile << line + "\n" }

def inRoot = new File(inputDir).getCanonicalFile()
def outRoot = out.getCanonicalFile()
def wantAnimals = onlyAnimals?.trim() ? (onlyAnimals.split(/[;, ]+/)*.trim().findAll { it } as Set) : null

def underOutput = { File f ->
    def p = f.getCanonicalPath()
    p == outRoot.getPath() || p.startsWith(outRoot.getPath() + File.separator)
}
// retina = the folder the image is in; an image directly in inputDir is its own retina
def sampleOf = { File f ->
    def atRoot = f.getParentFile().getCanonicalPath() == inRoot.getPath()
    (atRoot ? f.name.replaceAll(/\.[^.]+$/, "") : f.getParentFile().getName()).replace(",", "_")
}
def animalWanted = { String sample ->
    if (!wantAnimals) return true
    def m = (sample =~ /^(\d+)/)
    return m.find() && wantAnimals.contains(m.group(1))
}

// every container format Bio-Formats is likely to meet on a lab microscope
def exts = ~/(?i).*\.(czi|lif|nd2|tif|tiff|btf|oib|oif|oir|lsm|ims|vsi|ics|zvi|lei|dv|stk|nd)$/
def files = []
if (inRoot.isDirectory()) {
    // outputDir often sits inside inputDir: skipping it keeps our own .tif output out of the survey
    inRoot.traverse(type: FileType.FILES,
                    preDir: { File d ->
                        (d.name.startsWith(".") || underOutput(d)) ? FileVisitResult.SKIP_SUBTREE
                                                                   : FileVisitResult.CONTINUE
                    }) { File f ->
        // skip hidden files, including the "._" copies macOS leaves on shared and USB drives
        if (f.name ==~ exts && !f.name.startsWith(".") && !underOutput(f)) files << f
    }
}
files.sort { it.absolutePath }
if (wantAnimals) log("Only animals: ${wantAnimals.sort().join(', ')}")

// ---------------------------------------------------------------- mode=inspect
if (mode == "inspect") {
    def imagesCsv = new File(out, "counts/images.csv")
    def header = "sample,image,file,series,format,width_px,height_px,z,t,channels,channel_names,rgb,um_per_px,bytes,problem"
    // an animal-filtered run must not shrink the survey, so other samples keep their rows
    def keep = []
    if (wantAnimals && imagesCsv.exists()) {
        keep = imagesCsv.readLines().drop(1).findAll { String line ->
            def p = line.split(",", -1)
            return p.length > 1 && !animalWanted(p[0])
        }
    }
    def rows = []
    def seen = [] as Set
    files.each { File f ->
        if (seen.contains(f.getCanonicalPath())) return
        def sample = sampleOf(f)
        def base = f.name.replaceAll(/\.[^.]+$/, "").replace(",", "_")
        if (!animalWanted(sample)) { seen << f.getCanonicalPath(); return }
        def reader = LociPrefs.makeImageReader()
        def omexml = MetadataTools.createOMEXMLMetadata()
        try {
            reader.setMetadataStore(omexml)
            reader.setFlattenedResolutions(false)   // sub-resolutions are not separate images
            reader.setId(f.getAbsolutePath())
            // a multi-file image (.oif, .nd/.stk, .vsi) is one image, not one per file on disk
            def used = reader.getUsedFiles()
            if (!used) used = [f.getAbsolutePath()] as String[]
            long bytes = 0
            used.each { seen << new File(it).getCanonicalPath(); bytes += new File(it).length() }
            int ns = reader.getSeriesCount()
            for (int s = 0; s < ns; s++) {
                reader.setSeries(s)
                double um = 0
                try {
                    def phys = omexml.getPixelsPhysicalSizeX(s)
                    if (phys != null) {
                        def v = null
                        try { v = phys.value(ome.units.UNITS.MICROMETER) } catch (Throwable ignored) { }
                        if (v != null) {
                            um = v.doubleValue()
                        } else {
                            // a unit that will not convert: take the raw number and its symbol
                            double raw = phys.value() == null ? 0 : phys.value().doubleValue()
                            def sym = phys.unit()?.getSymbol()
                            um = sym == "nm" ? raw / 1000.0d : (sym == "mm" ? raw * 1000.0d : raw)
                        }
                    }
                } catch (Throwable ignored) { }
                // a plain TIFF carrying only a 72-dpi resolution tag reports 1 inch / 72 px =
                // 353 um per pixel; no flat-mount rig is remotely near that, so call it unknown
                if (!(um > 0) || um > 50) um = 0
                def names = []
                try {
                    int nc = omexml.getChannelCount(s)
                    for (int c = 0; c < nc; c++) names << csvSafe(omexml.getChannelName(s, c)).replace("|", "_")
                } catch (Throwable ignored) { }
                rows << [sample, base + (ns > 1 ? "_s${s}" : ""), csvSafe(f.getAbsolutePath()), s,
                         csvSafe(reader.getFormat()), reader.getSizeX(), reader.getSizeY(),
                         reader.getSizeZ(), reader.getSizeT(), reader.getSizeC(),
                         names.join("|"), reader.isRGB() ? 1 : 0,
                         um > 0 ? String.format(Locale.US, "%.6f", um) : "", bytes, ""].join(",")
            }
        } catch (Throwable e) {
            seen << f.getCanonicalPath()
            rows << [sample, base, csvSafe(f.getAbsolutePath()), 0, "", 0, 0, 0, 0, 0, "", 0, "",
                     f.length(), csvSafe(e.getMessage() ?: e.toString())].join(",")
            log("PROBLEM ${f.name}: ${e}")
        } finally {
            try { reader.close() } catch (Throwable ignored) { }
        }
    }
    imagesCsv.setText(([header] + keep + rows).join("\n") + "\n", "UTF-8")
    log("inspected ${rows.size()} image series in ${files.size()} files")
    if (exitWhenDone) System.exit(0)
    return
}

// ---------------------------------------------------------------- mode=run
if (mode != "run") {
    log("ERROR unknown mode '${mode}' (expected 'inspect' or 'run')")
    if (exitWhenDone) System.exit(2)
    return
}

def planFile = new File(out, "counts/plan.json")
if (!planFile.exists()) {
    log("ERROR no counts/plan.json in ${out}")
    if (exitWhenDone) System.exit(2)
    return
}
def plan = new JsonSlurper().parseText(planFile.getText("UTF-8"))
boolean countTiles = plan.count_tiles as boolean
boolean skipEmpty = plan.skip_empty_tiles as boolean
double minTissue = (plan.tissue_fraction ?: 0) as double

def tilesCsv = new File(out, "counts/tiles.csv")
def tilesHeader = "sample,image,tile,col,row,x0,y0,w,h,core_x0,core_y0,core_x1,core_y1,margin," +
                  "auto_count,objects_detected,rejected_dim,outside_core,core_px,tissue_fraction," +
                  "skipped_empty,um_per_px,source_format,file,counted_at,problem"
if (countTiles && !tilesCsv.exists()) tilesCsv.setText(tilesHeader + "\n", "UTF-8")
// counts from earlier runs too, so the overview of a resumed image shows the whole picture
def totals = [:]
if (tilesCsv.exists()) tilesCsv.readLines().drop(1).each { String line ->
    def p = line.split(",", -1)
    if (p.length > 14) totals[p[0] + "/" + p[2]] = (p[14]?.trim() ?: "0") as Integer
}

int nImages = 0, nTiles = 0, nSkipped = 0
log("Counting ${plan.images.size()} images: tile ${plan.tile_px} px, margin ${plan.margin_px} px, " +
    "diameter ${minDiameterPx}-${maxDiameterPx} px, radius ${localThresholdRadius}, " +
    "sigma ${gaussianSigma}, brightness >= ${minContrast}")

plan.images.each { img ->
    def sample = img.sample as String
    def imageName = img.image as String
    if (!animalWanted(sample)) return
    def srcFile = new File(img.file as String)
    def allTiles = (img.tiles ?: []) as List
    def todo = allTiles.findAll { it.todo }
    if (!allTiles) return

    // ---- normalize: chosen channel, t=0, Z max-projected, with a provenance sidecar ----
    def normTif = new File(out, "normalized/${sample}/${imageName}.tif")
    def normJson = new File(out, "normalized/${sample}/${imageName}.json")
    def prov = [tool: "count_rgc.groovy", plan_version: plan.version, sample: sample, image: imageName,
                source: srcFile.getAbsolutePath(), source_format: (img.format ?: ""),
                series: (img.series ?: 0), channel: channel, channels: (img.channels ?: 1),
                z: (img.z ?: 1), t_index: 0, projection: (((img.z ?: 1) as int) > 1 ? "max" : "none"),
                width_px: img.width_px, height_px: img.height_px, um_per_px: img.um_per_px]
    boolean reuse = false
    if (normTif.exists() && normJson.exists() && !overwrite) {
        try {
            def old = new JsonSlurper().parseText(normJson.getText("UTF-8"))
            reuse = ["source", "series", "channel", "z", "width_px", "height_px"].every { String k ->
                String.valueOf(old[k]) == String.valueOf(prov[k])
            }
        } catch (Throwable ignored) { reuse = false }
    }

    double um = (img.um_per_px == null) ? 0 : (img.um_per_px as double)
    def cal = new Calibration()
    if (um > 0) { cal.pixelWidth = um; cal.pixelHeight = um; cal.setUnit("micron") }

    ImagePlus normalized = null
    try {
        if (reuse) normalized = IJ.openImage(normTif.getAbsolutePath())
        if (normalized == null) {
            normalized = readChannel(srcFile, (img.series ?: 0) as int, channel - 1)
            normalized.setCalibration(cal.copy())
            saveTiffAtomic(normalized, normTif)
            normJson.setText(JsonOutput.prettyPrint(JsonOutput.toJson(
                    prov + [created_at: new Date().format("yyyy-MM-dd HH:mm:ss")])), "UTF-8")
        }
        normalized.setCalibration(cal.copy())
    } catch (Throwable e) {
        // no row is written, so the next run tries this image again instead of recording a zero
        log("ERROR normalising ${sample}/${imageName}: ${e}")
        if (normalized != null) normalized.close()
        return
    }

    // one display range for the whole image: every tile is thresholded on the same 8-bit mapping
    normalized.resetDisplayRange()
    double dmin = normalized.getProcessor().getMin(), dmax = normalized.getProcessor().getMax()
    double level = skipEmpty ? tissueLevel(normalized.getProcessor()) : 0

    // ---- write the padded tiles ----
    boolean multi = allTiles.size() > 1
    boolean materialize = multi || (plan.materialize_tiles as boolean)
    def tileFiles = [:]
    allTiles.each { t ->
        def tf = new File(out, "tiles/${sample}/${imageName}/${t.tile}.tif")
        tileFiles[t.tile as String] = tf
        if (!materialize || (tf.exists() && !overwrite)) return
        def ip = normalized.getProcessor().duplicate()
        ip.setRoi(t.x0 as int, t.y0 as int, t.w as int, t.h as int)
        def crop = new ImagePlus(t.tile as String, ip.crop())
        crop.setCalibration(cal.copy())
        crop.setProperty("Info", JsonOutput.toJson(
                [sample: sample, image: imageName, tile: t.tile, col: t.col, row: t.row,
                 x0: t.x0, y0: t.y0, w: t.w, h: t.h, core_x0: t.core_x0, core_y0: t.core_y0,
                 core_x1: t.core_x1, core_y1: t.core_y1, margin: t.margin,
                 is_right: t.is_right, is_bottom: t.is_bottom, um_per_px: img.um_per_px,
                 parent_width_px: img.width_px, parent_height_px: img.height_px,
                 source: srcFile.getAbsolutePath(), source_format: (img.format ?: "")]))
        saveTiffAtomic(crop, tf)
        crop.close()
    }

    if (!countTiles) {
        log("${sample}/${imageName}: ${allTiles.size()} tiles written")
        normalized.close()
        nImages++
        return
    }

    // ---- count ----
    todo.each { t ->
        def tileName = t.tile as String
        int tx0 = t.x0 as int, ty0 = t.y0 as int, tw = t.w as int, th = t.h as int
        int cx0 = t.core_x0 as int, cy0 = t.core_y0 as int, cx1 = t.core_x1 as int, cy1 = t.core_y1 as int
        boolean isRight = t.is_right as boolean, isBottom = t.is_bottom as boolean
        int coreW = cx1 - cx0, coreH = cy1 - cy0
        long corePx = (long) coreW * (long) coreH
        double frac = -1

        if (skipEmpty) {
            frac = tissueFraction(normalized.getProcessor(), cx0, cy0, coreW, coreH, level)
            if (frac < minTissue) {
                tilesCsv << ([sample, imageName, tileName, t.col, t.row, tx0, ty0, tw, th,
                              cx0, cy0, cx1, cy1, t.margin, 0, 0, 0, 0, corePx,
                              String.format(Locale.US, "%.4f", frac), 1,
                              um > 0 ? String.format(Locale.US, "%.6f", um) : "",
                              csvSafe(img.format), csvSafe(srcFile.getAbsolutePath()),
                              new Date().format("yyyy-MM-dd HH:mm"),
                              String.format(Locale.US, "empty: tissue %.4f < %.4f", frac, minTissue)]
                             ).join(",") + "\n"
                totals[sample + "/" + tileName] = 0
                nSkipped++
                return
            }
        }

        ImagePlus tileImp = null
        try {
            // a tiled image is counted from the tile .tif on disk, one tile at a time; a
            // single-tile image is counted straight off the normalized image
            tileImp = multi ? IJ.openImage(tileFiles[tileName].getAbsolutePath())
                            : new ImagePlus(tileName, normalized.getProcessor().duplicate())
            if (tileImp == null) throw new RuntimeException("could not open ${tileFiles[tileName]}")
            tileImp.setCalibration(new Calibration())       // measure in pixels
            def rois = extractCells(tileImp, minDiameterPx, maxDiameterPx, localThresholdRadius,
                                    gaussianSigma, dmin, dmax)

            // brightness filter: object mean / rolling-ball background under the object
            def bgIp = tileImp.getProcessor().convertToFloat().duplicate()
            new BackgroundSubtracter().rollingBallBackground(bgIp, bgRadiusPx, true, false, false, true, true)
            def bgImp = new ImagePlus("bg", bgIp)
            def recs = []
            rois.each { Roi r ->
                def c = r.getContourCentroid()
                double px = tx0 + c[0], py = ty0 + c[1]
                boolean inCore = (px >= cx0 && (isRight ? px <= cx1 : px < cx1)) &&
                                 (py >= cy0 && (isBottom ? py <= cy1 : py < cy1))
                bgImp.setRoi(r)
                double bg = bgImp.getStatistics(Measurements.MEAN).mean
                tileImp.setRoi(r)
                def st = tileImp.getStatistics(Measurements.MEAN | Measurements.AREA)
                boolean kept = (bg <= 0) || (st.mean / bg >= minContrast)
                recs << [roi: r, px: px, py: py, inCore: inCore, bg: bg, mean: st.mean,
                         area: st.area, contrast: (bg > 0 ? st.mean / bg : 0), kept: kept]
            }
            tileImp.killRoi()
            bgImp.close()
            int nKept = recs.count { it.inCore && it.kept }
            int nDetected = recs.count { it.inCore }
            int nDim = recs.count { it.inCore && !it.kept }
            int nOutside = recs.count { !it.inCore }

            // counted image: the core only, original pixels, outlines as an overlay
            def cp = tileImp.getProcessor().duplicate()
            cp.setRoi(cx0 - tx0, cy0 - ty0, coreW, coreH)
            def outImp = new ImagePlus(tileName, cp.crop())
            outImp.setCalibration(cal.copy())
            def ov = new Overlay()
            int idx = 0
            recs.each { rec ->
                if (!rec.inCore) return
                idx++
                def c2 = (Roi) rec.roi.clone()
                c2.setLocation(c2.getXBase() + tx0 - cx0, c2.getYBase() + ty0 - cy0)
                c2.setStrokeColor(rec.kept ? Color.MAGENTA : Color.CYAN)
                c2.setStrokeWidth(rec.kept ? 1.5 : 1.0)
                c2.setName((rec.kept ? "auto_kept_" : "auto_rejected_") + idx)
                ov.add(c2)
            }
            outImp.setOverlay(ov)
            outImp.resetDisplayRange()
            IJ.run(outImp, "Enhance Contrast", "saturated=0.35")    // display only
            saveTiffAtomic(outImp, new File(out, "counted/${sample}/${tileName}.tif"))

            def jpg = outImp.duplicate()
            jpg.setOverlay(ov.duplicate())
            IJ.run(jpg, "8-bit", "")
            IJ.run(jpg, "RGB Color", "")
            def flat = jpg.flatten()
            def fip = flat.getProcessor()
            fip.setColor(Color.YELLOW)
            fip.setFont(new Font("SansSerif", Font.BOLD, 40))
            fip.drawString("${tileName}   automated count ${nKept}   (magenta counted, cyan too dim)", 20, 60)
            saveJpegAtomic(flat, new File(out, "counted/${sample}/${tileName}.jpg"))

            def roiFile = new File(out, "rois/${sample}/${tileName}_rois.csv")
            roiFile.getParentFile().mkdirs()
            def sb = new StringBuilder("cell,x_px,y_px,parent_x_px,parent_y_px,area_px," +
                                       "mean_intensity,bg_mean,contrast,kept,in_core\n")
            recs.eachWithIndex { rec, int i ->
                sb.append(String.format(Locale.US, "%d,%.2f,%.2f,%.2f,%.2f,%.1f,%.2f,%.2f,%.4f,%d,%d\n",
                        i + 1, rec.px - cx0, rec.py - cy0, rec.px, rec.py, rec.area, rec.mean,
                        rec.bg, rec.contrast, rec.kept ? 1 : 0, rec.inCore ? 1 : 0))
            }
            roiFile.setText(sb.toString(), "UTF-8")

            tilesCsv << ([sample, imageName, tileName, t.col, t.row, tx0, ty0, tw, th,
                          cx0, cy0, cx1, cy1, t.margin, nKept, nDetected, nDim, nOutside, corePx,
                          frac < 0 ? "" : String.format(Locale.US, "%.4f", frac), 0,
                          um > 0 ? String.format(Locale.US, "%.6f", um) : "",
                          csvSafe(img.format), csvSafe(srcFile.getAbsolutePath()),
                          new Date().format("yyyy-MM-dd HH:mm"), ""]).join(",") + "\n"
            totals[sample + "/" + tileName] = nKept
            nTiles++
            log("${tileName}: ${nKept} cells" + (nOutside ? " (${nOutside} outside the core)" : ""))
            [outImp, jpg, flat, tileImp].each { if (it != null) it.close() }
        } catch (Throwable e) {
            log("ERROR ${sample}/${tileName}: ${e}")
            if (tileImp != null) tileImp.close()
        }
    }

    if (multi) {
        def perTile = [:]
        int total = 0
        allTiles.each { t ->
            def v = totals[sample + "/" + (t.tile as String)]
            if (v != null) { perTile[t.tile as String] = v; total += v }
        }
        try {
            writeOverview(normalized, allTiles, perTile, total, imageName,
                          new File(out, "counted/${sample}/${imageName}.jpg"))
        } catch (Throwable e) {
            log("ERROR overview ${sample}/${imageName}: ${e}")
        }
        log("${sample}/${imageName}: ${total} cells over ${allTiles.size()} tiles")
    }
    normalized.close()
    nImages++
}

log("done: ${nTiles} tiles counted over ${nImages} images" + (nSkipped ? ", ${nSkipped} empty tiles skipped" : ""))
if (exitWhenDone) System.exit(0)
