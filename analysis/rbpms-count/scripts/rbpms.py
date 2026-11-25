"""Helpers used by analysis.ipynb: find Fiji, run the automated count, install the review tool,
and report review progress. Works on Windows and macOS (and Linux).

You can also run the count from a terminal:
    python scripts/rbpms.py count                       # images in data/, results in output/
    python scripts/rbpms.py count --data /path/to/images
    python scripts/rbpms.py install-review-tool
    python scripts/rbpms.py status
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"

# Settings tuned for 20x/0.4 widefield images at 0.227 um/px. See README, "Changing the settings".
DEFAULT_SETTINGS = dict(
    radius=60,          # Niblack local threshold radius (pixels)
    sigma=8.0,          # Gaussian blur
    min_diameter=35.0,  # smallest cell body (pixels), about 8 um
    max_diameter=130.0, # largest cell body (pixels), about 30 um
    min_contrast=1.15,  # a cell must be this many times brighter than the background; 1.0 = off
    channel=1,          # channel with the RGC stain
)


# ---------------------------------------------------------------- finding Fiji
def _candidate_fiji_dirs():
    home = Path.home()
    names = ["Fiji.app", "Fiji", "fiji", "fiji-latest", "Fiji.app.latest"]
    places = [Path("/Applications"), home / "Applications", home, home / "Documents", home / "Desktop",
              home / "Downloads", Path("C:/"), Path("C:/Program Files")]
    for place in places:
        for name in names:
            yield place / name


def _is_fiji(d: Path) -> bool:
    return d.is_dir() and (d / "jars").is_dir()


def find_fiji(fiji_dir: str | os.PathLike | None = None) -> Path:
    """Return the Fiji folder. Uses fiji_dir if given, then the FIJI_DIR environment variable,
    then the usual install locations."""
    tried = []
    for c in ([fiji_dir] if fiji_dir else []) + ([os.environ["FIJI_DIR"]] if os.environ.get("FIJI_DIR") else []):
        p = Path(c).expanduser()
        for d in (p, p.with_name(p.name + ".app")):
            tried.append(d)
            if _is_fiji(d):
                return d
    for d in _candidate_fiji_dirs():
        tried.append(d)
        if _is_fiji(d):
            return d
    raise FileNotFoundError(
        "Could not find Fiji. Set FIJI_FOLDER in the settings cell to the folder that contains Fiji "
        "(on a Mac usually /Applications/Fiji.app). Looked in:\n  " + "\n  ".join(map(str, tried[:12])))


def find_java(fiji: Path) -> Path:
    """The Java that comes with Fiji."""
    exe = "java.exe" if os.name == "nt" else "java"
    found = sorted(p for p in (fiji / "java").rglob(exe) if p.parent.name == "bin" and p.is_file())
    # prefer a JDK/JRE whose path matches this computer (arm64 vs x64 on Mac)
    arch = platform.machine().lower()
    want = "arm64" if arch in ("arm64", "aarch64") else ("x64" if "64" in arch else "")
    found.sort(key=lambda p: (want not in str(p).lower(), "jre" in str(p).lower()))
    if found:
        return found[0]
    system_java = shutil.which("java")
    if system_java:
        return Path(system_java)
    raise FileNotFoundError(f"No Java found inside {fiji / 'java'}. Open Fiji once normally, or reinstall Fiji.")


def _java_major(java: Path) -> int:
    try:
        out = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=60).stderr
        m = re.search(r'version "(\d+)(?:\.(\d+))?', out)
        if m:
            major = int(m.group(1))
            return int(m.group(2)) if major == 1 else major
    except Exception:  # noqa: BLE001
        pass
    return 21


def run_fiji_script(script: Path, args: dict, fiji_dir=None, memory="4g", show=None) -> int:
    """Run a Fiji script without opening Fiji's window. `show(line)` receives each output line."""
    fiji = find_fiji(fiji_dir)
    java = find_java(fiji)
    major = _java_major(java)
    sep = ";" if os.name == "nt" else ":"
    cp = sep.join(str(fiji / p) for p in ["jars/*", "jars/bio-formats/*", "plugins/*"])
    cmd = [str(java), f"-Xmx{memory}", "-Djava.awt.headless=true", "-Dapple.awt.UIElement=true",
           f"-Dplugins.dir={fiji}", f"-Dimagej.dir={fiji}", f"-Dij.dir={fiji}", f"-Dfiji.dir={fiji}",
           f"-Dscijava.app.directory={fiji}", "-Dscijava.log.level=warn", "-Dpython.cachedir.skip=true"]
    if major >= 9:
        cmd.append("--add-opens=java.base/java.lang=ALL-UNNAMED")
    if major >= 21:
        cmd.append("--enable-native-access=ALL-UNNAMED")
    libs = [d for d in (fiji / "lib").glob("*") if d.is_dir()] if (fiji / "lib").is_dir() else []
    if libs:
        cmd.append("-Djava.library.path=" + sep.join(map(str, libs)))
    arg_text = ",".join(f"{k}='{v}'" if isinstance(v, (str, Path)) else f"{k}={str(v).lower() if isinstance(v, bool) else v}"
                        for k, v in args.items())
    cmd += ["-cp", cp, "net.imagej.Main", "--headless", "--run", Path(script).as_posix(), arg_text]

    show = show or (lambda line: print(line, flush=True))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    for line in proc.stdout:
        line = line.rstrip()
        if line and not line.startswith(("[WARN]", "[INFO]", "Checking for master file")) and "Dichroic" not in line:
            show(line)
    return proc.wait()


# ---------------------------------------------------------------- the three steps
def listed_animals(priority: str | None = None) -> list[str]:
    """Animals in tracking/animals.csv; only those with this priority (e.g. "today") if given."""
    import csv
    p = TRACKING / "animals.csv"
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8-sig") as fh:
        return [r["animal"].strip() for r in csv.DictReader(fh)
                if r.get("animal", "").strip() and (priority is None or r.get("priority", "").strip() == priority)]


def count(data=REPO / "data", output=REPO / "output", fiji_dir=None, overwrite=False, animals=None, **settings) -> int:
    """Step 1: count the images under `data`. Images already counted are skipped.
    animals: None counts every retina; a list such as ["1001", "1002"] counts only those animals."""
    s = {**DEFAULT_SETTINGS, **settings}
    data, output = Path(data).expanduser().resolve(), Path(output).expanduser().resolve()
    if not data.is_dir():
        raise FileNotFoundError(f"The images folder does not exist: {data}")
    output.mkdir(parents=True, exist_ok=True)
    args = dict(inputDir=data.as_posix(), outputDir=output.as_posix(), channel=int(s["channel"]),
                localThresholdRadius=int(s["radius"]), gaussianSigma=float(s["sigma"]),
                minDiameterPx=float(s["min_diameter"]), maxDiameterPx=float(s["max_diameter"]),
                minContrast=float(s["min_contrast"]), bgRadiusPx=100, overwrite=bool(overwrite),
                onlyAnimals=";".join(str(a) for a in animals) if animals else "")
    if animals is not None and not animals:
        print("No animals selected, so nothing to count. Check ONLY_ANIMALS in the settings.")
        return 0
    code = run_fiji_script(SCRIPTS / "count_rgc.groovy", args, fiji_dir)
    if code != 0:
        print(f"\nFiji stopped with an error (code {code}). The lines above say what went wrong.")
    return code


def install_review_tool(fiji_dir=None) -> Path:
    """Step 2 setup: put the review tool in Fiji's Plugins menu (Plugins > RGC > Review Counts)."""
    fiji = find_fiji(fiji_dir)
    target = fiji / "scripts" / "Plugins" / "RGC" / "Review_Counts.groovy"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SCRIPTS / "review_counts.groovy", target)
    return target


def review_status(output=REPO / "output"):
    """Step 2 progress: how many images of each retina have been reviewed."""
    import pandas as pd
    output = Path(output)
    auto_csv = output / "counts" / "auto_counts.csv"
    if not auto_csv.exists():
        raise FileNotFoundError("No counts yet. Run step 1 first.")
    auto = pd.read_csv(auto_csv).drop_duplicates(["sample", "image"], keep="last")
    man_csv = output / "counts" / "manual_counts.csv"
    reviewed = (pd.read_csv(man_csv)[["sample", "image"]].drop_duplicates()
                if man_csv.exists() else pd.DataFrame(columns=["sample", "image"]))
    reviewed["reviewed"] = True
    d = auto.merge(reviewed, on=["sample", "image"], how="left")
    d["reviewed"] = d["reviewed"].fillna(False).astype(bool)
    t = d.groupby("sample").agg(images=("image", "count"), reviewed=("reviewed", "sum"))
    t["still_to_review"] = t["images"] - t["reviewed"]
    return t.reset_index().rename(columns={"sample": "retina"})


# ---------------------------------------------------------------- tracking log
IMAGE_EXTS = {".czi", ".tif", ".tiff", ".lif", ".nd2"}
# Tracking log folder. Defaults to tracking/ next to the notebook (local, not committed: the lab repo is public).
# Set RBPMS_TRACKING to a shared folder (e.g. on CRSP) so everyone sees the same log.
TRACKING = Path(os.environ.get("RBPMS_TRACKING", REPO / "tracking")).expanduser()
RETINA_RE = re.compile(r"^(?P<animal>\d+)(?P<eye>[LR])?", re.I)


def parse_retina(name: str):
    """'1001L - XY' -> ('1001', 'L'); '1003' -> ('1003', '?'); 'pig retina 1' -> ('pig retina 1', '?')"""
    m = RETINA_RE.match(name.strip())
    if not m:
        return name.strip(), "?"
    return m.group("animal"), (m.group("eye") or "?").upper()


def images_in(data: Path) -> dict:
    """{retina folder name: number of image files} for every retina in the images folder."""
    found = {}
    if not data.is_dir():
        return found
    for f in data.rglob("*"):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS and not f.name.startswith("."):   # skip macOS "._" files
            retina = f.stem if f.parent == data else f.parent.name
            found[retina] = found.get(retina, 0) + 1
    return found


def _stage(images, counted, reviewed, analysed):
    if images == 0:
        return "1 not mounted (no images)"
    if counted == 0:
        return "2 imaged, not counted"
    if counted < images:
        return f"3 counting ({counted} of {images})"
    if reviewed == 0:
        return "4 counted, review not started"
    if reviewed < counted:
        return f"5 reviewing ({reviewed} of {counted})"
    if not analysed:
        return "6 reviewed, run step 3"
    return "7 done"


def update_log(data=REPO / "data", output=REPO / "output", tracking=TRACKING, eyes=None):
    """Write tracking/status.csv and tracking/STATUS.md from the animal list, the images folder and the results.
    eyes: None logs every eye; "L" logs only left eyes (and folders whose name has no L/R, marked "?").
    Returns the status table."""
    import pandas as pd
    eye_filter = sorted({e.upper() for e in str(eyes).replace(",", " ").split()}) if eyes else None
    data, output, tracking = Path(data).expanduser(), Path(output).expanduser(), Path(tracking)
    tracking.mkdir(parents=True, exist_ok=True)
    plan_csv = tracking / "animals.csv"
    plan = (pd.read_csv(plan_csv, dtype=str).fillna("") if plan_csv.exists()
            else pd.DataFrame(columns=["animal", "eyes", "priority", "requested", "notes"]))

    def read(p, cols):
        return pd.read_csv(p, dtype={"sample": str}).drop_duplicates(cols, keep="last") if p.exists() else None
    auto = read(output / "counts" / "auto_counts.csv", ["sample", "image"])
    man = read(output / "counts" / "manual_counts.csv", ["sample", "image"])
    res = read(output / "results" / "counts_per_image.csv", ["sample", "image"])
    n_auto = auto.groupby("sample").size().to_dict() if auto is not None else {}
    n_man = man.groupby("sample").size().to_dict() if man is not None else {}
    n_res = res.groupby("sample").size().to_dict() if res is not None else {}

    found = images_in(data)
    retinas = set(found) | set(n_auto)
    by_key = {}
    for r in retinas:
        by_key.setdefault(parse_retina(r), []).append(r)

    rows = []
    planned_keys = set()
    for p in plan.itertuples():
        eyes = (p.eyes or "L R").split()
        for eye in eyes:
            key = (str(p.animal), eye.upper())
            planned_keys.add(key)
            rows.append(dict(animal=key[0], eye=key[1], priority=p.priority, requested=p.requested,
                             notes=p.notes, folders=by_key.get(key, [])))
        for key, folders in by_key.items():   # folders of a listed animal without L/R in the name
            if key[0] == str(p.animal) and key[1] not in [e.upper() for e in eyes] and key not in planned_keys:
                planned_keys.add(key)
                rows.append(dict(animal=key[0], eye=key[1], priority=p.priority, requested=p.requested,
                                 notes="folder name has no L/R", folders=folders))
    for key, folders in by_key.items():
        if key not in planned_keys:
            rows.append(dict(animal=key[0], eye=key[1], priority="", requested="", notes="", folders=folders))

    for r in rows:
        f = r["folders"]
        r["images"] = sum(found.get(x, 0) for x in f)
        r["counted"] = sum(n_auto.get(x, 0) for x in f)
        r["reviewed"] = sum(n_man.get(x, 0) for x in f)
        analysed = r["reviewed"] > 0 and sum(n_res.get(x, 0) for x in f) >= r["reviewed"]
        r["stage"] = _stage(r["images"], r["counted"], r["reviewed"], analysed)
        r["folders"] = "; ".join(sorted(f))
    st = pd.DataFrame(rows, columns=["animal", "eye", "priority", "requested", "stage", "images", "counted",
                                     "reviewed", "folders", "notes"])
    if eye_filter:
        st = st[st["eye"].isin(eye_filter + ["?"])]
    st["_listed"] = st["priority"].ne("") | st["requested"].ne("")
    st = st.sort_values(["_listed", "priority", "animal", "eye"], ascending=[False, True, True, True])
    listed, others = st[st._listed].drop(columns="_listed"), st[~st._listed].drop(columns="_listed")
    st = st.drop(columns="_listed")
    st.to_csv(tracking / "status.csv", index=False)

    def md_table(df):
        cols = ["animal", "eye", "priority", "stage", "images", "counted", "reviewed", "folders", "notes"]
        out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for r in df[cols].itertuples(index=False):
            out.append("| " + " | ".join(str(v)[2:] if c == "stage" else str(v) for c, v in zip(cols, r)) + " |")
        return "\n".join(out)

    def stage_counts(df):
        c = df["stage"].str.replace(r"\s*\(.*\)", "", regex=True).value_counts().sort_index()
        return "\n".join(f"- {k[2:]}: {v}" for k, v in c.items())

    from datetime import datetime
    md = [f"# Tracking log",
          "",
          f"Updated {datetime.now():%Y-%m-%d %H:%M} from images in `{data.name}/` and results in `{output.name}/`. "
          "Do not edit this file: edit `tracking/animals.csv`, then update the log from the notebook "
          "(or `python scripts/rbpms.py log`).",
          "",
          "One row per retina (animal + eye). An eye with no images in the images folder is **not mounted** yet.",
          "",
          *([f"Only {' and '.join({'L': 'left', 'R': 'right'}.get(e, e) for e in eye_filter)} eyes are shown "
             "(plus folders whose name has no L/R, marked `?`).", ""] if eye_filter else []),
          "## Animals on the list",
          "",
          stage_counts(listed) if len(listed) else "No animals listed in `tracking/animals.csv` yet.",
          "",
          md_table(listed) if len(listed) else "",
          "",
          f"## Other retinas in the images folder ({len(others)})",
          "",
          "Not on the list in `tracking/animals.csv`. Full details are in `tracking/status.csv`.",
          "",
          stage_counts(others) if len(others) else "None.",
          ""]
    (tracking / "STATUS.md").write_text("\n".join(md), encoding="utf-8")
    return st


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("count", help="step 1: automated count")
    c.add_argument("--data", default=str(REPO / "data"))
    c.add_argument("--output", default=str(REPO / "output"))
    c.add_argument("--fiji", default=None, help="Fiji folder, if it is not found automatically")
    c.add_argument("--overwrite", action="store_true", help="count every image again")
    c.add_argument("--animals", default=None, help='only these animals, e.g. "1001,1002"')
    c.add_argument("--priority", default=None, help='only animals with this priority in tracking/animals.csv, e.g. "today"')
    for k, v in DEFAULT_SETTINGS.items():
        c.add_argument("--" + k.replace("_", "-"), type=type(v), default=v)
    i = sub.add_parser("install-review-tool", help="add Plugins > RGC > Review Counts to Fiji")
    i.add_argument("--fiji", default=None)
    s = sub.add_parser("status", help="step 2: review progress")
    s.add_argument("--output", default=str(REPO / "output"))
    lg = sub.add_parser("log", help="update tracking/STATUS.md and tracking/status.csv")
    lg.add_argument("--data", default=str(REPO / "data"))
    lg.add_argument("--output", default=str(REPO / "output"))
    lg.add_argument("--eyes", default=None, help='only these eyes, e.g. "L"')
    a = ap.parse_args()
    if a.cmd == "log":
        update_log(a.data, a.output, eyes=a.eyes)
        print((TRACKING / "STATUS.md").read_text(encoding="utf-8"))
    if a.cmd == "count":
        settings = {k: getattr(a, k) for k in DEFAULT_SETTINGS}
        animals = (a.animals.replace(";", ",").split(",") if a.animals
                   else listed_animals(a.priority) if a.priority else None)
        code = count(a.data, a.output, a.fiji, a.overwrite, animals=animals, **settings)
        update_log(a.data, a.output)
        sys.exit(code)
    if a.cmd == "install-review-tool":
        print("Installed:", install_review_tool(a.fiji), "\nRestart Fiji to see Plugins > RGC > Review Counts.")
    if a.cmd == "status":
        print(review_status(a.output).to_string(index=False))


if __name__ == "__main__":
    main()
