// AxonQuantifier v2 - CTB axon density along a straightened, whole-mounted optic nerve
//
// Run on a STRAIGHTENED single-channel z-stack (nerve running left-right).
// Changes from v1 (3Macro.ijm):
//   - Each line samples a band (default 25 um) instead of a 1-pixel line
//   - Threshold is set per slice from a background ROI (mean + k*SD) or an auto method,
//     not typed in by hand; the threshold is subtracted (no jump at the cutoff)
//   - Pre-crush normalization is computed from the Pre line, not typed in by hand
//   - Slices outside the nerve are dropped automatically
//   - Post-crush lines are generated at set distances from the crush line
//   - A continuous intensity-vs-distance curve with AUC and reach distances is exported
//   - The ROI set and all settings are saved, so a run can be repeated exactly
//
// Interactive: Plugins > Macros > Run... with the straightened stack open.
// Batch / re-run: pass key=value arguments, e.g. from the command line
//   fiji --headless -macro AxonQuantifier_v2.ijm "image=[C:/n1.tif] out=[C:/out] roiset=[C:/RoiSet.zip]"
// Every run writes run_args.txt containing the exact argument string to reproduce it.

var VERSION = "2.0";
var ARG = "";

ARG = getArgument();
batch = (lengthOf(ARG) > 0);
ARG = ARG + " ";

// ---------------- settings ----------------
outRoot = "";
bandUm = 25;
thrMethod = "background";      // background | auto | manual
k = 2;
autoMethod = "Triangle";
manualT = 0;
belowMode = "subtract";        // subtract | hard
zMode = "auto";                // auto | all | manual
zFrac = 0.10;
zFirst = 1;
zLast = 0;
distStr = "250,500,750,1000,1250,1500,1750,2000";
aucMin = 250;
aucMax = 2000;
fracStr = "0.5,0.25,0.1,0.05";
roiSetPath = "";
keepWork = false;

if (batch) {
	imagePath = argVal("image", "");
	if (imagePath != "") open(imagePath);
	outRoot = argVal("out", "");
	bandUm = parseFloat(argVal("band", "" + bandUm));
	thrMethod = argVal("threshold", thrMethod);
	k = parseFloat(argVal("k", "" + k));
	autoMethod = argVal("automethod", autoMethod);
	manualT = parseFloat(argVal("manualt", "" + manualT));
	belowMode = argVal("below", belowMode);
	zMode = argVal("z", zMode);
	zFrac = parseFloat(argVal("zfrac", "" + zFrac));
	zFirst = parseInt(argVal("zfirst", "" + zFirst));
	zLast = parseInt(argVal("zlast", "0"));
	distStr = argVal("distances", distStr);
	aucMin = parseFloat(argVal("aucmin", "" + aucMin));
	aucMax = parseFloat(argVal("aucmax", "" + aucMax));
	fracStr = argVal("reach", fracStr);
	roiSetPath = argVal("roiset", "");
	keepStr = argVal("keep", "false");
	if (keepStr == "true") keepWork = true;
	if (outRoot == "") exit("Batch mode needs out=[folder]");
	if (roiSetPath == "") exit("Batch mode needs roiset=[RoiSet.zip]");
}

if (nImages == 0) exit("Open the straightened nerve stack first.");
origID = getImageID();
origTitle = getTitle();
getDimensions(W, H, nC, nZ, nT);
if (nC > 1) exit("Image has " + nC + " channels. Split channels and run on the CTB channel only.");
if (nT > 1) exit("Image has " + nT + " time points; expected a single z-stack.");
n = nSlices;
if (zLast <= 0 || zLast > n) zLast = n;

if (!batch) {
	thrChoices = newArray("Background ROI (mean + k*SD)", "Auto (per slice)", "Manual value");
	belowChoices = newArray("Subtract threshold (recommended)", "Hard cutoff (v1 behavior)");
	zChoices = newArray("Auto (drop slices outside nerve)", "All slices", "Manual range");
	Dialog.create("AxonQuantifier v" + VERSION);
	Dialog.addDirectory("Output folder", "");
	Dialog.addNumber("Band width (um)", bandUm);
	Dialog.addMessage("Background threshold");
	Dialog.addChoice("Method", thrChoices, thrChoices[0]);
	Dialog.addNumber("k (SDs above background mean)", k);
	Dialog.addChoice("Auto method", getList("threshold.methods"), autoMethod);
	Dialog.addNumber("Manual threshold", manualT);
	Dialog.addChoice("Below threshold", belowChoices, belowChoices[0]);
	Dialog.addMessage("Z slices");
	Dialog.addChoice("Slices", zChoices, zChoices[0]);
	Dialog.addNumber("Auto: keep slices with Pre signal >= fraction of max", zFrac);
	Dialog.addNumber("Manual: first slice", 1);
	Dialog.addNumber("Manual: last slice", n);
	Dialog.addMessage("Outputs");
	Dialog.addString("Post-crush distances (um)", distStr, 40);
	Dialog.addNumber("AUC from (um)", aucMin);
	Dialog.addNumber("AUC to (um)", aucMax);
	Dialog.addString("Reach levels (fraction of Pre)", fracStr, 20);
	Dialog.addFile("Reuse ROI set (optional)", "");
	Dialog.addCheckbox("Keep processed stack open", false);
	Dialog.show();
	outRoot = Dialog.getString();
	bandUm = Dialog.getNumber();
	c = Dialog.getChoice();
	if (c == thrChoices[0]) thrMethod = "background";
	else if (c == thrChoices[1]) thrMethod = "auto";
	else thrMethod = "manual";
	k = Dialog.getNumber();
	autoMethod = Dialog.getChoice();
	manualT = Dialog.getNumber();
	if (Dialog.getChoice() == belowChoices[0]) belowMode = "subtract"; else belowMode = "hard";
	c = Dialog.getChoice();
	if (c == zChoices[0]) zMode = "auto";
	else if (c == zChoices[1]) zMode = "all";
	else zMode = "manual";
	zFrac = Dialog.getNumber();
	zFirst = Dialog.getNumber();
	zLast = Dialog.getNumber();
	distStr = Dialog.getString();
	aucMin = Dialog.getNumber();
	aucMax = Dialog.getNumber();
	fracStr = Dialog.getString();
	roiSetPath = Dialog.getString();
	keepWork = Dialog.getCheckbox();
	if (outRoot == "") exit("Choose an output folder.");
}

// ---------------- output folder ----------------
getDateAndTime(yr, mo, dw, dy, hr, mi, sc, ms);
stamp = "" + yr + IJ.pad(mo + 1, 2) + IJ.pad(dy, 2) + "_" + IJ.pad(hr, 2) + IJ.pad(mi, 2) + IJ.pad(sc, 2);
safeTitle = replace(origTitle, "[^A-Za-z0-9_.-]", "_");
outDir = outRoot + File.separator + "AQ2_" + safeTitle + "_" + stamp;
File.makeDirectory(outDir);
if (!File.isDirectory(outDir)) exit("Could not create output folder:\n" + outDir);

getPixelSize(unit, pw, ph);
if (unit == "pixel" || unit == "pixels" || unit == "") print("WARNING: image is not calibrated; distances are in pixels.");
bandPx = maxOf(1, round(bandUm / pw));

// ---------------- ROIs ----------------
roiManager("reset");
selectImage(origID);
if (roiSetPath != "") {
	roiManager("open", roiSetPath);
} else {
	run("Select None");
	setTool("line");
	captureLine("Draw a straight line across the nerve at the PRE-CRUSH site, then click OK.", "Pre");
	captureLine("Draw a straight line across the nerve at the CRUSH site, then click OK.", "Crush");
	if (thrMethod == "background") {
		setTool("rectangle");
		captureArea("Draw a rectangle on BACKGROUND outside the nerve (no tissue), then click OK.", "Background");
	}
	addPostLines(distStr);
	run("Select None");
	setTool("line");
	waitForUser("Review lines", "Check the lines in the ROI Manager.\nMove, delete or add straight lines as needed.\n" +
		"Every straight line other than Pre and Crush is measured;\nits distance is taken from its midpoint.\nClick OK to measure.");
}
roiManager("remove slice info");

preIdx = findRoi("Pre");
crushIdx = findRoi("Crush");
bgIdx = findRoi("Background");
if (preIdx < 0 || crushIdx < 0) exit("ROI set must contain straight lines named Pre and Crush.");
if (thrMethod == "background" && bgIdx < 0) exit("Background threshold needs an area ROI named Background.");

roiManager("deselect");
roiManager("save", outDir + File.separator + "RoiSet.zip");

roiManager("select", crushIdx);
getLine(cx1, cy1, cx2, cy2, lw);
crushX = (cx1 + cx2) / 2;
roiManager("select", preIdx);
getLine(px1, py1, px2, py2, lw);
preX = (px1 + px2) / 2;
if (preX < crushX) sgn = 1; else sgn = -1;

// collect the lines to measure, ordered by distance from the crush
nR = roiManager("count");
tmpIdx = newArray(nR);
tmpDist = newArray(nR);
m = 0;
for (i = 0; i < nR; i++) {
	roiManager("select", i);
	if (selectionType() != 5) continue;
	getLine(x1, y1, x2, y2, lw);
	tmpIdx[m] = i;
	tmpDist[m] = ((x1 + x2) / 2 - crushX) * sgn * pw;
	m++;
}
tmpIdx = Array.trim(tmpIdx, m);
tmpDist = Array.trim(tmpDist, m);
rank = Array.rankPositions(tmpDist);
lineIdx = newArray(m);
lineDist = newArray(m);
lineName = newArray(m);
lineLen = newArray(m);
for (j = 0; j < m; j++) {
	lineIdx[j] = tmpIdx[rank[j]];
	lineDist[j] = tmpDist[rank[j]];
	roiManager("select", lineIdx[j]);
	lineName[j] = Roi.getName;
	getLine(x1, y1, x2, y2, lw);
	lineLen[j] = sqrt((x2 - x1) * (x2 - x1) * pw * pw + (y2 - y1) * (y2 - y1) * ph * ph);
}
preCol = -1;
for (j = 0; j < m; j++) if (lineIdx[j] == preIdx) preCol = j;

// ---------------- per-slice background removal ----------------
setBatchMode(true);
selectImage(origID);
run("Select None");
run("Duplicate...", "title=AQ2_processed duplicate");
workID = getImageID();
run("32-bit");
thr = newArray(n);
bgMean = newArray(n);
bgSD = newArray(n);
for (z = 1; z <= n; z++) {
	selectImage(workID);
	setSlice(z);
	if (bgIdx >= 0) {
		roiManager("select", bgIdx);
		getStatistics(area, mean, min, max, std);
		bgMean[z - 1] = mean;
		bgSD[z - 1] = std;
	}
	run("Select None");
	if (thrMethod == "background") {
		t = bgMean[z - 1] + k * bgSD[z - 1];
	} else if (thrMethod == "auto") {
		setAutoThreshold(autoMethod + " dark");
		getThreshold(lo, hi);
		resetThreshold();
		t = lo;
	} else {
		t = manualT;
	}
	thr[z - 1] = t;
	if (belowMode == "subtract") {
		run("Subtract...", "value=" + t + " slice");
		run("Min...", "value=0 slice");
	} else {
		run("Macro...", "code=[if (v < " + t + ") v = 0;] slice");
	}
}

// ---------------- line measurements ----------------
run("Line Width...", "line=" + bandPx);
perSlice = newArray(n * m);   // integrated signal along each line (intensity x um), band-averaged
for (z = 1; z <= n; z++) {
	selectImage(workID);
	setSlice(z);
	for (j = 0; j < m; j++) {
		roiManager("select", lineIdx[j]);
		Roi.setStrokeWidth(bandPx);
		p = getProfile();
		s = 0;
		for (q = 0; q < p.length; q++) s += p[q];
		perSlice[(z - 1) * m + j] = s * pw;
	}
}
run("Line Width...", "line=1");

// ---------------- choose slices ----------------
include = newArray(n);
preMax = 0;
for (z = 0; z < n; z++) preMax = maxOf(preMax, perSlice[z * m + preCol]);
nInc = 0;
for (z = 0; z < n; z++) {
	if (zMode == "all") include[z] = 1;
	else if (zMode == "manual") include[z] = (z + 1 >= zFirst && z + 1 <= zLast);
	else include[z] = (preMax > 0 && perSlice[z * m + preCol] >= zFrac * preMax);
	nInc += include[z];
}
if (nInc == 0) exit("No slices selected. Pre-crush signal is zero after thresholding; check the threshold settings.");

tot = newArray(m);
for (z = 0; z < n; z++) if (include[z]) for (j = 0; j < m; j++) tot[j] += perSlice[z * m + j];
preTot = tot[preCol];

// ---------------- continuous curve ----------------
col = newArray(W);
for (z = 1; z <= n; z++) {
	if (!include[z - 1]) continue;
	selectImage(workID);
	setSlice(z);
	makeRectangle(0, 0, W, H);
	p = getProfile();      // column means
	for (x = 0; x < W; x++) col[x] += p[x] * H * ph;
	run("Select None");
}
colDist = newArray(W);
for (x = 0; x < W; x++) colDist[x] = (x + 0.5 - crushX) * sgn * pw;
half = floor(bandPx / 2);
preRef = 0; cnt = 0;
for (x = maxOf(0, round(preX) - half); x <= minOf(W - 1, round(preX) + half); x++) { preRef += col[x]; cnt++; }
preRef = preRef / cnt;
colNorm = newArray(W);
colSmooth = newArray(W);
for (x = 0; x < W; x++) if (preRef > 0) colNorm[x] = col[x] / preRef;
for (x = 0; x < W; x++) {
	s = 0; cnt = 0;
	for (q = maxOf(0, x - half); q <= minOf(W - 1, x + half); q++) { s += colNorm[q]; cnt++; }
	colSmooth[x] = s / cnt;
}
auc = 0;
for (x = 0; x < W; x++) if (colDist[x] >= aucMin && colDist[x] <= aucMax) auc += colNorm[x] * pw;
maxDist = 0;
for (x = 0; x < W; x++) maxDist = maxOf(maxDist, colDist[x]);
fracs = splitNumbers(fracStr);
reach = newArray(fracs.length);
for (f = 0; f < fracs.length; f++) {
	for (x = 0; x < W; x++) if (colDist[x] > 0 && colSmooth[x] >= fracs[f]) reach[f] = maxOf(reach[f], colDist[x]);
}

// ---------------- write outputs ----------------
sep = File.separator;

fh = File.open(outDir + sep + "summary.csv");
print(fh, "roi,distance_um,line_length_um,integrated_signal,signal_per_um_of_line,percent_of_pre");
for (j = 0; j < m; j++) {
	pct = 0;
	if (preTot > 0) pct = 100 * tot[j] / preTot;
	print(fh, lineName[j] + "," + d2s(lineDist[j], 1) + "," + d2s(lineLen[j], 1) + "," + d2s(tot[j], 2) + "," +
		d2s(tot[j] / lineLen[j], 4) + "," + d2s(pct, 2));
}
File.close(fh);

fh = File.open(outDir + sep + "per_slice.csv");
hdr = "slice,included,threshold,bg_mean,bg_sd";
for (j = 0; j < m; j++) hdr = hdr + "," + lineName[j];
print(fh, hdr);
for (z = 0; z < n; z++) {
	row = "" + (z + 1) + "," + include[z] + "," + d2s(thr[z], 3) + "," + d2s(bgMean[z], 3) + "," + d2s(bgSD[z], 3);
	for (j = 0; j < m; j++) row = row + "," + d2s(perSlice[z * m + j], 2);
	print(fh, row);
}
File.close(fh);

fh = File.open(outDir + sep + "curve.csv");
print(fh, "x_px,distance_um,integrated_signal,fraction_of_pre,fraction_of_pre_smoothed");
for (x = 0; x < W; x++)
	print(fh, "" + x + "," + d2s(colDist[x], 2) + "," + d2s(col[x], 2) + "," + d2s(colNorm[x], 5) + "," + d2s(colSmooth[x], 5));
File.close(fh);

fh = File.open(outDir + sep + "curve_metrics.csv");
print(fh, "metric,value");
print(fh, "auc_" + aucMin + "_to_" + aucMax + "um (fraction_of_pre x um)," + d2s(auc, 2));
for (f = 0; f < fracs.length; f++) print(fh, "farthest_um_at_or_above_" + fracs[f] + "_of_pre," + d2s(reach[f], 1));
print(fh, "max_measurable_distance_um," + d2s(maxDist, 1));
print(fh, "slices_included," + nInc + " of " + n);
File.close(fh);

runArgs = "out=[" + outRoot + "] roiset=[" + outDir + sep + "RoiSet.zip] band=" + bandUm + " threshold=" + thrMethod +
	" k=" + k + " automethod=" + autoMethod + " manualt=" + manualT + " below=" + belowMode + " z=" + zMode +
	" zfrac=" + zFrac + " zfirst=" + zFirst + " zlast=" + zLast + " distances=[" + distStr + "] aucmin=" + aucMin +
	" aucmax=" + aucMax + " reach=[" + fracStr + "]";
File.saveString(runArgs + "\n", outDir + sep + "run_args.txt");

fh = File.open(outDir + sep + "params.txt");
print(fh, "AxonQuantifier v" + VERSION);
print(fh, "image: " + origTitle);
print(fh, "pixel size: " + pw + " x " + ph + " " + unit);
print(fh, "band width: " + bandUm + " um (" + bandPx + " px)");
print(fh, "threshold: " + thrMethod + "  k=" + k + "  auto=" + autoMethod + "  manual=" + manualT + "  below=" + belowMode);
print(fh, "z selection: " + zMode + "  frac=" + zFrac + "  range=" + zFirst + "-" + zLast + "  included " + nInc + " of " + n);
print(fh, "crush x (px): " + d2s(crushX, 1) + "  pre x (px): " + d2s(preX, 1) + "  post direction: " + sgn);
print(fh, "To re-run exactly with the saved ROIs (open the same image first, or add image=[path]):");
print(fh, runArgs);
File.close(fh);

// ---------------- log + cleanup ----------------
print("AxonQuantifier v" + VERSION + "  " + origTitle);
print("Slices included: " + nInc + " of " + n);
for (j = 0; j < m; j++) {
	pct = 0;
	if (preTot > 0) pct = 100 * tot[j] / preTot;
	print("  " + lineName[j] + "  (" + d2s(lineDist[j], 0) + " um): " + d2s(pct, 1) + "% of Pre");
}
print("AUC " + aucMin + "-" + aucMax + " um: " + d2s(auc, 1));
for (f = 0; f < fracs.length; f++) print("Farthest distance >= " + fracs[f] + " of Pre: " + d2s(reach[f], 0) + " um");
print("Results: " + outDir);

if (keepWork) {
	setBatchMode("exit and display");
} else {
	selectImage(workID);
	close();
	setBatchMode(false);
}
selectImage(origID);

// ---------------- functions ----------------
function argVal(key, def) {
	return call("ij.Macro.getValue", ARG, key, def);
}

function captureLine(msg, name) {
	while (true) {
		waitForUser(name, msg);
		if (selectionType() == 5) break;
		showMessage("Need a straight line", "Use the Straight Line tool, then click OK.");
	}
	roiManager("add");
	roiManager("select", roiManager("count") - 1);
	roiManager("rename", name);
	run("Select None");
}

function captureArea(msg, name) {
	while (true) {
		waitForUser(name, msg);
		tp = selectionType();
		if (tp >= 0 && tp <= 4) break;
		showMessage("Need an area selection", "Draw a rectangle (or other area) on background, then click OK.");
	}
	roiManager("add");
	roiManager("select", roiManager("count") - 1);
	roiManager("rename", name);
	run("Select None");
}

// Add lines parallel to the crush line at each distance, on the side away from Pre
function addPostLines(distStr) {
	ci = findRoi("Crush");
	pi = findRoi("Pre");
	roiManager("select", ci);
	getLine(ax1, ay1, ax2, ay2, w);
	roiManager("select", pi);
	getLine(bx1, by1, bx2, by2, w);
	cxm = (ax1 + ax2) / 2;
	if ((bx1 + bx2) / 2 < cxm) dir = 1; else dir = -1;
	getPixelSize(u, pxw, pxh);
	getDimensions(iw, ih, ic, iz, ifr);
	ds = splitNumbers(distStr);
	for (d = 0; d < ds.length; d++) {
		dx = dir * ds[d] / pxw;
		if (cxm + dx < 0 || cxm + dx >= iw) {
			print("Skipped " + ds[d] + " um: outside the image.");
			continue;
		}
		makeLine(ax1 + dx, ay1, ax2 + dx, ay2);
		roiManager("add");
		roiManager("select", roiManager("count") - 1);
		roiManager("rename", "Post_" + ds[d] + "um");
	}
}

function findRoi(name) {
	for (r = 0; r < roiManager("count"); r++) {
		roiManager("select", r);
		if (Roi.getName == name) return r;
	}
	return -1;
}

function splitNumbers(s) {
	parts = split(s, ", ");
	out = newArray(parts.length);
	c = 0;
	for (i = 0; i < parts.length; i++) {
		v = parseFloat(parts[i]);
		if (!isNaN(v)) { out[c] = v; c++; }
	}
	return Array.trim(out, c);
}
