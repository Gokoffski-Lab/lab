#@ File (label="Results folder (for example results/simple_rgc)", style="directory", persist=true) runDir
#@ String (label="Your initials", persist=true) reviewer
#@ String (label="Only these retinas, separated by ; (blank = all)", value="", required=false, persist=false) samples
#@ Boolean (label="Review fields that are already reviewed again", value=false, persist=false) redo
#@ Boolean (value=false, visibility=INVISIBLE, persist=false) simulate

/*
 * Manual review of automated RGC counts (run in Fiji with its normal window, not headless).
 *
 * For every review TIFF written by simple_rgc_count.groovy (review/<sample>/<image>.tif):
 *   - opens the original image with the automated outlines
 *       magenta = counted by the pipeline, cyan = rejected by the brightness filter
 *   - places one yellow point on every counted cell
 *   - the reviewer corrects the points with the Multi-point tool:
 *       click            add a missed cell
 *       Alt + click      remove a point that is not a cell
 *       drag             move a point
 *   - "Save and next" stores the corrected points and moves on; "Skip" leaves the field
 *     unreviewed; Cancel ends the session. Progress is kept, so a session can be resumed.
 *
 * Output (under the results folder):
 *   manual/manual_counts.csv                 one row per reviewed field
 *   manual/<sample>/<image>_points.csv       every point: auto_kept, removed or added
 *   review/<sample>/<image>.tif              overlay updated with the final points (green)
 *
 * Install: copy this file to Fiji.app/scripts/Plugins/RGC/ and restart Fiji; it then appears as
 * Plugins > RGC > Review Counts Full. It can also be opened and run from File > Open.
 */

import ij.IJ
import ij.ImagePlus
import ij.gui.NonBlockingGenericDialog
import ij.gui.Overlay
import ij.gui.PointRoi
import ij.gui.Roi
import ij.gui.YesNoCancelDialog
import java.awt.Color

def run = runDir
def reviewDir = new File(run, "review")
def manualDir = new File(run, "manual")
manualDir.mkdirs()
if (!reviewDir.isDirectory()) {
    IJ.error("RGC review", "No review folder in\n${run}\n\nRun the counting step first (scripts/run_analysis.sh).")
    return
}

// ---------------- progress file ----------------
def countsFile = new File(manualDir, "manual_counts.csv")
def header = "sample,image,n_auto_kept,n_removed,n_added,n_final,reviewer,reviewed_at,seconds,note"
if (!countsFile.exists()) countsFile.text = header + "\n"
def reviewed = [] as Set
countsFile.readLines().drop(1).each { def p = it.split(",", -1); if (p.length > 1) reviewed << (p[0] + "/" + p[1]) }

def csvSafe = { String s -> (s ?: "").replace(",", ";").replace("\n", " ").trim() }

// ---------------- fields to review ----------------
def wanted = samples?.trim() ? (samples.split(";")*.trim().findAll { it } as Set) : null
def fields = []
reviewDir.eachFileRecurse { f ->
    if (f.isFile() && f.name.toLowerCase().endsWith(".tif")) {
        def sample = f.parentFile.name
        def image = f.name.replaceAll(/(?i)\.tif$/, "")
        if (wanted && !wanted.contains(sample)) return
        if (!redo && reviewed.contains(sample + "/" + image)) return
        fields << [file: f, sample: sample, image: image]
    }
}
fields.sort { it.file.absolutePath }
if (!fields) {
    if (!simulate) IJ.showMessage("RGC review", "Nothing to review: every selected field is already reviewed.")
    else println "nothing to review"
    return
}

// ---------------- helpers ----------------
List<double[]> autoPoints(Overlay ov) {
    def pts = []
    if (!ov) return pts
    for (Roi r : ov.toArray()) if (r.getName()?.startsWith("auto_kept_")) pts << r.getContourCentroid()
    return pts
}

List<double[]> previousFinal(Overlay ov) {
    if (!ov) return null
    for (Roi r : ov.toArray()) if (r.getName() == "manual_final" && r instanceof PointRoi) {
        def fp = r.getFloatPolygon()
        return (0..<fp.npoints).collect { [fp.xpoints[it], fp.ypoints[it]] as double[] }
    }
    return null
}

PointRoi makePoints(List<double[]> pts) {
    def pr = new PointRoi()
    pts.each { pr.addPoint((double) it[0], (double) it[1]) }
    pr.setPointType(PointRoi.DOT)
    pr.setSize(3)
    pr.setStrokeColor(Color.YELLOW)
    pr.setFillColor(Color.YELLOW)
    return pr
}

List<double[]> pointsOf(Roi r) {
    if (!(r instanceof PointRoi)) return null
    def fp = r.getFloatPolygon()
    return (0..<fp.npoints).collect { [fp.xpoints[it], fp.ypoints[it]] as double[] }
}

// pair each automated point with an unmoved final point (within 0.75 px)
def classify(List<double[]> auto, List<double[]> fin) {
    def used = new boolean[fin.size()]
    def kept = [], removed = []
    auto.each { a ->
        int hit = -1
        for (int j = 0; j < fin.size(); j++) {
            if (!used[j] && Math.abs(fin[j][0] - a[0]) < 0.75 && Math.abs(fin[j][1] - a[1]) < 0.75) { hit = j; break }
        }
        if (hit >= 0) { used[hit] = true; kept << fin[hit] } else removed << a
    }
    def added = []
    for (int j = 0; j < fin.size(); j++) if (!used[j]) added << fin[j]
    return [kept: kept, removed: removed, added: added]
}

def instructions = """Correct the yellow points so that every RGC has exactly one point.

   Click on a cell                 add a missed cell
   Alt + click on a point          remove a point that is not a cell
   Drag a point                    move it

Magenta outline = counted automatically. Cyan outline = rejected as too dim.
Zoom with + and -, pan by holding the space bar and dragging.
Brightness: Image > Adjust > Brightness/Contrast (does not change the data)."""

// ---------------- review loop ----------------
int done = 0
for (int k = 0; k < fields.size(); k++) {
    def fld = fields[k]
    def imp = IJ.openImage(fld.file.absolutePath)
    if (imp == null) { IJ.log("Could not open ${fld.file}"); continue }
    def ov = imp.getOverlay()
    def auto = autoPoints(ov)
    def start = previousFinal(ov) ?: auto
    long t0 = System.currentTimeMillis()
    String note = ""
    List<double[]> fin

    if (simulate) {
        // test mode: remove the first 3 automated points and add 2 new ones
        fin = start.drop(Math.min(3, start.size())) + [[15.0d, 15.0d] as double[], [40.0d, 40.0d] as double[]]
    } else {
        // the final-points layer from an earlier review is replaced by the editable selection
        if (ov) ov.toArray().findAll { it.getName() == "manual_final" }.each { ov.remove(it) }
        imp.show()
        IJ.setTool("multipoint")
        imp.setRoi(makePoints(start))
        def action = null
        while (true) {
            def gd = new NonBlockingGenericDialog("Review ${fld.sample} ${fld.image}  (${k + 1} of ${fields.size()})")
            gd.addMessage("${start.size()} points to start with (${auto.size()} counted automatically).\n\n" + instructions)
            gd.addStringField("Note (optional)", "", 40)
            gd.enableYesNoCancel("Save and next", "Skip this field")
            gd.setCancelLabel("Stop reviewing")
            gd.showDialog()
            if (gd.wasCanceled()) { action = "stop"; break }
            note = gd.getNextString()
            if (!gd.wasOKed()) { action = "skip"; break }
            fin = pointsOf(imp.getRoi())
            if (fin != null) { action = "save"; break }
            def yn = new YesNoCancelDialog(IJ.getInstance(), "Points missing",
                    "The point selection was lost (another tool or a click outside the image may have cleared it).\n\n" +
                    "Yes: put back the points from the start of this field and keep reviewing.\n" +
                    "No: save this field with zero cells.")
            if (yn.yesPressed()) { IJ.setTool("multipoint"); imp.setRoi(makePoints(start)); continue }
            if (yn.cancelPressed()) continue
            fin = []; action = "save"; break
        }
        if (action != "save") {
            imp.changes = false; imp.close()
            if (action == "stop") break
            continue
        }
    }

    def c = classify(auto, fin)
    double secs = (System.currentTimeMillis() - t0) / 1000.0

    // per-point file
    def pDir = new File(manualDir, fld.sample); pDir.mkdirs()
    def sb = new StringBuilder("x_px,y_px,status\n")
    c.kept.each { sb << String.format(Locale.US, "%.2f,%.2f,auto_kept\n", it[0], it[1]) }
    c.added.each { sb << String.format(Locale.US, "%.2f,%.2f,added\n", it[0], it[1]) }
    c.removed.each { sb << String.format(Locale.US, "%.2f,%.2f,removed\n", it[0], it[1]) }
    new File(pDir, fld.image + "_points.csv").text = sb.toString()

    // summary row (replace an earlier review of the same field)
    def key = fld.sample + "/" + fld.image
    def keep = countsFile.readLines().findAll { line ->
        def p = line.split(",", -1); !(p.length > 1 && (p[0] + "/" + p[1]) == key)
    }
    keep << String.format(Locale.US, "%s,%s,%d,%d,%d,%d,%s,%s,%.0f,%s",
            fld.sample, fld.image, auto.size(), c.removed.size(), c.added.size(), fin.size(),
            csvSafe(reviewer), new Date().format("yyyy-MM-dd HH:mm"), secs, csvSafe(note))
    countsFile.text = keep.join("\n") + "\n"

    // store the final points on the image itself
    def ov2 = imp.getOverlay() ?: new Overlay()
    ov2.toArray().findAll { it.getName() == "manual_final" }.each { ov2.remove(it) }
    def finalRoi = makePoints(fin)
    finalRoi.setStrokeColor(Color.GREEN); finalRoi.setFillColor(Color.GREEN)
    finalRoi.setName("manual_final")
    ov2.add(finalRoi)
    imp.setOverlay(ov2)
    imp.deleteRoi()
    IJ.saveAsTiff(imp, fld.file.absolutePath)
    imp.changes = false
    imp.close()
    done++
    IJ.log(String.format("%s %s: %d automated, %d removed, %d added, %d final",
            fld.sample, fld.image, auto.size(), c.removed.size(), c.added.size(), fin.size()))
}

int total = 0, nRev = 0
reviewDir.eachFileRecurse { if (it.isFile() && it.name.toLowerCase().endsWith(".tif")) total++ }
nRev = countsFile.readLines().size() - 1
def msg = "Reviewed this session: ${done}\nReviewed in total: ${nRev} of ${total} fields"
if (simulate) { println msg; System.exit(0) } else IJ.showMessage("RGC review", msg)
