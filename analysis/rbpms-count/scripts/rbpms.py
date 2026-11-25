"""Helpers used by rbpms_count.ipynb: find Fiji, survey the images, run the automated count,
install the review tool, and report progress. Works on Windows and macOS (and Linux).

Large images are counted in tiles. `tiling.py` works out the tile geometry and writes it to
`output/counts/plan.json`; `count_rgc.groovy` does the imaging work; the per-tile rows in
`counts/tiles.csv` are folded back into one row per image in `counts/auto_counts.csv`.

You can also run it from a terminal:
    python scripts/rbpms.py inspect                     # what is in data/, and how many tiles
    python scripts/rbpms.py count                       # images in data/, results in output/
    python scripts/rbpms.py count --data /path/to/images --tile-px 1024
    python scripts/rbpms.py tile                        # write the tiles without counting
    python scripts/rbpms.py install-review-tool
    python scripts/rbpms.py status
"""
from __future__ import annotations

import argparse
import contextlib
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import tiling  # noqa: E402  (sibling module, not a package)

# Settings tuned for 20x/0.4 widefield images at 0.227 um/px. See README, "Changing the settings".
DEFAULT_SETTINGS = dict(
    radius=60,          # Niblack local threshold radius (pixels)
    sigma=8.0,          # Gaussian blur
    min_diameter=35.0,  # smallest cell body (pixels), about 8 um
    max_diameter=130.0, # largest cell body (pixels), about 30 um
    min_contrast=1.15,  # a cell must be this many times brighter than the background; 1.0 = off
    channel=1,          # channel with the RGC stain
)
BG_RADIUS_PX = 100      # rolling-ball radius of the brightness filter's background estimate
DEFAULT_TILE_PX = 2048  # tile core size; 0 counts each image in one piece
MAX_TILES_WARN = 25     # above this, step 2 means reviewing an unreasonable number of fields
LOCK_STALE_HOURS = 12


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
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if line and not line.startswith(("[WARN]", "[INFO]", "Checking for master file")) and "Dichroic" not in line:
                show(line)
    finally:
        if proc.stdout is not None:
            proc.stdout.close()
    return proc.wait()


# ---------------------------------------------------------------- one run at a time
def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == 259        # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                                   # someone else's process, but it is there
    return True


@contextlib.contextmanager
def run_lock(output, stale_hours: float = LOCK_STALE_HOURS):
    """Only one count at a time per output folder: Fiji appends to counts/tiles.csv."""
    lock = Path(output) / "counts" / ".run.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists():
        try:
            pid = int(lock.read_text(encoding="utf-8").split()[0])
        except (ValueError, IndexError, OSError):
            pid = -1
        age_h = (time.time() - lock.stat().st_mtime) / 3600
        if pid != os.getpid() and _pid_alive(pid) and age_h < stale_hours:
            raise RuntimeError(
                f"A count is already running in {Path(output)} (process {pid}, started {age_h:.1f} h "
                f"ago). Wait for it to finish, or delete {lock} if that process is really gone.")
        print(f"Ignoring a stale lock (process {pid}, {age_h:.1f} h old): {lock}")
    lock.write_text(f"{os.getpid()} {datetime.now():%Y-%m-%d %H:%M:%S}\n", encoding="utf-8")
    try:
        yield lock
    finally:
        lock.unlink(missing_ok=True)


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


def derived_margin(settings: dict | None = None) -> int:
    """Padding a tile needs so that a cell is segmented exactly as it would be untiled."""
    s = {**DEFAULT_SETTINGS, **(settings or {})}
    return tiling.derive_margin_px(s["max_diameter"], s["radius"], s["sigma"], BG_RADIUS_PX)


def _dirs(data, output):
    data, output = Path(data).expanduser().resolve(), Path(output).expanduser().resolve()
    if not data.is_dir():
        raise FileNotFoundError(f"The images folder does not exist: {data}")
    (output / "counts").mkdir(parents=True, exist_ok=True)
    return data, output


def _args(data, output, s, *, mode, overwrite=False, animals=None) -> dict:
    return dict(inputDir=Path(data).as_posix(), outputDir=Path(output).as_posix(), mode=mode,
                channel=int(s["channel"]), localThresholdRadius=int(s["radius"]),
                gaussianSigma=float(s["sigma"]), minDiameterPx=float(s["min_diameter"]),
                maxDiameterPx=float(s["max_diameter"]), minContrast=float(s["min_contrast"]),
                bgRadiusPx=BG_RADIUS_PX, overwrite=bool(overwrite),
                onlyAnimals=";".join(str(a) for a in animals) if animals else "")


INSPECT_COLUMNS = ["sample", "image", "tiles", "width_px", "height_px", "z", "t", "channels",
                   "um_per_px", "format", "series", "rgb", "channel_names", "bytes", "tile_px",
                   "margin_px", "file", "problem"]


def _survey(data, output, s, fiji_dir, animals, memory):
    code = run_fiji_script(SCRIPTS / "count_rgc.groovy",
                           _args(data, output, s, mode="inspect", animals=animals),
                           fiji_dir, memory=memory or "2g")
    if code != 0:
        raise RuntimeError(f"Fiji stopped with an error (code {code}) while reading {data}.")
    return tiling.read_images_csv(Path(output) / "counts" / "images.csv")


def _tiles_per_image(images, tile_px, margin) -> dict:
    return {img.key: (0 if img.problem or img.width_px <= 0 or img.height_px <= 0
                      else len(tiling.plan_tiles(img, tile_px, margin)))
            for img in images}


def inspect(data=REPO / "data", output=REPO / "output", fiji_dir=None, tile_px=DEFAULT_TILE_PX,
            margin_px=None, animals=None, memory=None, **settings):
    """Look at the images without counting: size, channels, Z, pixel size, and how many tiles each
    would need. Writes `output/counts/images.csv` and returns it as a DataFrame."""
    import pandas as pd
    s = {**DEFAULT_SETTINGS, **settings}
    data, output = _dirs(data, output)
    images = _survey(data, output, s, fiji_dir, animals, memory)
    margin = int(margin_px if margin_px is not None else derived_margin(s))
    per_image = _tiles_per_image(images, tile_px, margin)
    df = pd.DataFrame([{**asdict(img), "tiles": per_image[img.key], "tile_px": int(tile_px),
                        "margin_px": margin} for img in images],
                      columns=INSPECT_COLUMNS)

    bad = df[df["problem"].astype(str).str.strip() != ""]
    for r in bad.itertuples():
        print(f"Cannot read {r.sample}/{r.image}: {r.problem}")
    worst = int(df["tiles"].max()) if len(df) else 0
    if worst > MAX_TILES_WARN:
        print(f"\nWarning: with tile_px={tile_px} one image needs {worst} tiles, so step 2 would mean "
              f"reviewing {worst} fields for that image alone. Raise tile_px (or review per animal) "
              "unless you really want that.")
    if len(df):
        print(f"{len(df)} image series, {int(df['tiles'].sum())} tiles at tile_px={tile_px}, "
              f"margin {margin} px")
    return df


def count(data=REPO / "data", output=REPO / "output", fiji_dir=None, overwrite=False, animals=None,
          tile_px=DEFAULT_TILE_PX, margin_px=None, skip_empty_tiles=False,
          min_tissue_fraction=0.05, keep_normalized=True, memory=None, **settings) -> int:
    """Step 1: count the images under `data`. Tiles already counted are skipped, so an interrupted
    run picks up where it stopped.
    animals: None counts every retina; a list such as ["1001", "1002"] counts only those animals."""
    s = {**DEFAULT_SETTINGS, **settings}
    if animals is not None and not animals:
        print("No animals selected, so nothing to count. Check ONLY_ANIMALS in the settings.")
        return 0
    data, output = _dirs(data, output)
    counts_dir = output / "counts"
    with run_lock(output):
        images = _survey(data, output, s, fiji_dir, animals, memory)
        for img in images:
            if img.problem:
                print(f"Skipping {img.sample}/{img.image}: {img.problem}")
        margin = int(margin_px if margin_px is not None else derived_margin(s))
        plan = tiling.plan_run(images, tile_px, margin, settings=s, overwrite=overwrite,
                               done=tiling.done_tile_keys(counts_dir / "tiles.csv"),
                               skip_empty_tiles=skip_empty_tiles,
                               tissue_fraction=min_tissue_fraction,
                               keep_normalized=keep_normalized)
        tiling.write_plan(counts_dir / "plan.json", plan)

        code = 0
        if plan.todo_tiles:
            print(f"Counting {len(plan.todo_tiles)} tiles over {len(plan.images)} images "
                  f"(tile {tile_px} px, margin {margin} px)")
            code = run_fiji_script(SCRIPTS / "count_rgc.groovy",
                                   _args(data, output, s, mode="run", overwrite=overwrite,
                                         animals=animals), fiji_dir, memory=memory or "4g")
            if code != 0:
                print(f"\nFiji stopped with an error (code {code}). The lines above say what went wrong.")
        else:
            print("Every tile is counted already. Nothing to do.")

        rows = tiling.fold_auto(tiling.read_tiles_csv(counts_dir / "tiles.csv"), images,
                                tile_px, margin)
        tiling.write_auto_counts_csv(counts_dir / "auto_counts.csv", rows)
        print(f"{len(rows)} images in {counts_dir / 'auto_counts.csv'}")
        if not keep_normalized:
            shutil.rmtree(output / "normalized", ignore_errors=True)
    return code


def tile(data=REPO / "data", output=REPO / "output", fiji_dir=None, tile_px=DEFAULT_TILE_PX,
         margin_px=None, animals=None, memory=None, **settings):
    """Write the padded tiles to `output/tiles/<sample>/<image>/<tile>.tif` without counting
    anything, for looking at them or for feeding another tool. Returns the tile table."""
    import pandas as pd
    s = {**DEFAULT_SETTINGS, **settings}
    data, output = _dirs(data, output)
    with run_lock(output):
        images = _survey(data, output, s, fiji_dir, animals, memory)
        margin = int(margin_px if margin_px is not None else derived_margin(s))
        plan = tiling.plan_run(images, tile_px, margin, settings=s, count_tiles=False,
                               materialize_tiles=True)
        tiling.write_plan(output / "counts" / "plan.json", plan)
        if not plan.tiles:
            print(f"No readable images in {data}.")
            return pd.DataFrame(columns=["sample", "image", "tile", "file"])
        code = run_fiji_script(SCRIPTS / "count_rgc.groovy",
                               _args(data, output, s, mode="run", animals=animals),
                               fiji_dir, memory=memory or "4g")
        if code != 0:
            print(f"\nFiji stopped with an error (code {code}). The lines above say what went wrong.")
    rows = [{**asdict(t), "file": str(output / "tiles" / t.sample / t.image / f"{t.tile}.tif")}
            for t in plan.tiles]
    print(f"{len(rows)} tiles in {output / 'tiles'}")
    return pd.DataFrame(rows).drop(columns=["todo"])


def install_review_tool(fiji_dir=None) -> Path:
    """Step 2 setup: put the review tool in Fiji's Plugins menu (Plugins > RGC > Review Counts)."""
    fiji = find_fiji(fiji_dir)
    target = fiji / "scripts" / "Plugins" / "RGC" / "Review_Counts.groovy"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SCRIPTS / "review_counts.groovy", target)
    return target


def sync_manual_counts(output=REPO / "output") -> Path:
    """Fold `counts/tile_manual_counts.csv` (one row per reviewed field) into
    `counts/manual_counts.csv` (one row per image). Safe to call repeatedly."""
    c = Path(output).expanduser() / "counts"
    man_csv = c / "manual_counts.csv"
    tile_man = tiling.read_manual_csv(c / "tile_manual_counts.csv")
    # rows with no `tiles` value were written straight into manual_counts.csv by the pre-tiling
    # review tool; they are passed through so an old output folder still reads
    legacy = [r for r in tiling.read_manual_csv(man_csv) if not str(r.get("tiles", "")).strip()]
    if not tile_man and not legacy:
        return man_csv
    rows = tiling.fold_manual(tile_man, tiling.read_tiles_csv(c / "tiles.csv"), legacy)
    return tiling.write_manual_counts_csv(man_csv, rows)


def counts(output=REPO / "output", level="image"):
    """Everything known about the counts, as one DataFrame.

    level="image"  one row per source image: the automated count, the review, and the final count.
    level="tile"   one row per tile, with its review if it has one.
    """
    import pandas as pd
    output = Path(output).expanduser().resolve()
    c = output / "counts"
    sync_manual_counts(output)

    if level == "tile":
        tiles = pd.DataFrame(tiling.read_tiles_csv(c / "tiles.csv"), columns=tiling.TILES_COLUMNS)
        man = pd.DataFrame(tiling.read_manual_csv(c / "tile_manual_counts.csv"))
        if man.empty or tiles.empty:
            return tiles
        man = man.rename(columns={"image": "tile"})
        keep = ["sample", "tile", "removed", "added", "final_count", "reviewer", "reviewed_at",
                "seconds", "note"]
        return tiles.merge(man[[k for k in keep if k in man.columns]], on=["sample", "tile"], how="left")
    if level != "image":
        raise ValueError(f'level must be "image" or "tile", got {level!r}')

    auto_csv = c / "auto_counts.csv"
    if not auto_csv.exists():
        raise FileNotFoundError("No counts yet. Run step 1 first.")
    auto = pd.read_csv(auto_csv, dtype={"sample": str}).drop_duplicates(["sample", "image"], keep="last")
    man_csv = c / "manual_counts.csv"
    keep = ["sample", "image", "removed", "added", "final_count", "reviewer", "reviewed_at",
            "seconds", "note", "tiles_reviewed"]
    if man_csv.exists():
        man = pd.read_csv(man_csv, dtype={"sample": str}).drop_duplicates(["sample", "image"], keep="last")
        man = man[[k for k in keep if k in man.columns]]
    else:
        man = pd.DataFrame(columns=keep)
    d = auto.merge(man, on=["sample", "image"], how="left")
    d["reviewed"] = d["final_count"].notna()
    d["count"] = d["final_count"].where(d["reviewed"], d["auto_count"])
    return d


def review_status(output=REPO / "output"):
    """Step 2 progress: how many images of each retina have been reviewed."""
    import pandas as pd
    output = Path(output)
    auto_csv = output / "counts" / "auto_counts.csv"
    if not auto_csv.exists():
        raise FileNotFoundError("No counts yet. Run step 1 first.")
    sync_manual_counts(output)
    auto = pd.read_csv(auto_csv, dtype={"sample": str}).drop_duplicates(["sample", "image"], keep="last")
    man_csv = output / "counts" / "manual_counts.csv"
    reviewed = (pd.read_csv(man_csv, dtype={"sample": str})[["sample", "image"]].drop_duplicates()
                if man_csv.exists() else pd.DataFrame(columns=["sample", "image"]))
    reviewed["reviewed"] = True
    d = auto.merge(reviewed, on=["sample", "image"], how="left")
    d["reviewed"] = d["reviewed"].fillna(False).astype(bool)
    agg = dict(images=("image", "count"), reviewed=("reviewed", "sum"))
    if "tiles" in d.columns:
        agg["fields"] = ("tiles", "sum")       # how many .tif files there are to click through
    t = d.groupby("sample").agg(**agg)
    t["still_to_review"] = t["images"] - t["reviewed"]
    return t.reset_index().rename(columns={"sample": "retina"})


# ---------------------------------------------------------------- tracking log
IMAGE_EXTS = {".czi", ".lif", ".nd2", ".tif", ".tiff", ".btf", ".oib", ".oif", ".oir", ".lsm",
              ".ims", ".vsi", ".ics", ".zvi", ".lei", ".dv", ".stk", ".nd"}
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


def images_in(data: Path, output: Path | None = None) -> dict:
    """{retina folder name: number of source images} for every retina in the images folder.

    Prefers `output/counts/images.csv`, which has one row per image *series*, so a multi-series
    .czi or .lif counts as the several images it really holds -- and so the tracking log compares
    counted images against source images, not against the number of tiles. Falls back to counting
    files when there is no survey yet. Images that cannot be read are left out: they can never be
    counted, so keeping them would pin a retina at "counting" for ever.
    """
    if output is not None:
        survey = Path(output) / "counts" / "images.csv"
        if survey.exists():
            found = {}
            for img in tiling.read_images_csv(survey):
                if not img.problem and img.sample:
                    found[img.sample] = found.get(img.sample, 0) + 1
            if found:
                return found
    found = {}
    data = Path(data)
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
    with contextlib.suppress(OSError):
        sync_manual_counts(output)
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

    found = images_in(data, output)
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

    md = [f"# Tracking log",
          "",
          f"Updated {datetime.now():%Y-%m-%d %H:%M} from images in `{data.name}/` and results in `{output.name}/`. "
          "Do not edit this file: edit `tracking/animals.csv`, then update the log from the notebook "
          "(or `python scripts/rbpms.py log`).",
          "",
          "One row per retina (animal + eye). An eye with no images in the images folder is **not mounted** yet. "
          "`images` and `counted` are whole images, not tiles.",
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


# ---------------------------------------------------------------- command line
def _add_common(p, with_settings=True):
    p.add_argument("--data", default=str(REPO / "data"))
    p.add_argument("--output", default=str(REPO / "output"))
    p.add_argument("--fiji", default=None, help="Fiji folder, if it is not found automatically")
    p.add_argument("--animals", default=None, help='only these animals, e.g. "1001,1002"')
    p.add_argument("--priority", default=None,
                   help='only animals with this priority in tracking/animals.csv, e.g. "today"')
    p.add_argument("--tile-px", type=int, default=DEFAULT_TILE_PX,
                   help="tile core size in pixels (0 counts each image in one piece)")
    p.add_argument("--margin-px", type=int, default=None,
                   help="padding around each tile; derived from the settings when not given")
    p.add_argument("--memory", default=None, help="Java heap for Fiji, e.g. 8g")
    if with_settings:
        for k, v in DEFAULT_SETTINGS.items():
            p.add_argument("--" + k.replace("_", "-"), type=type(v), default=v)


def _chosen_animals(a):
    return (a.animals.replace(";", ",").split(",") if a.animals
            else listed_animals(a.priority) if a.priority else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("count", help="step 1: automated count")
    _add_common(c)
    c.add_argument("--overwrite", action="store_true", help="count every tile again")
    c.add_argument("--skip-empty-tiles", action="store_true",
                   help="do not count tiles that are almost all background")
    c.add_argument("--min-tissue-fraction", type=float, default=0.05,
                   help="with --skip-empty-tiles, how much tissue a tile needs (0-1)")
    c.add_argument("--no-keep-normalized", action="store_false", dest="keep_normalized",
                   help="delete output/normalized/ when the count is done")
    i = sub.add_parser("inspect", help="list the images and how many tiles they need, without counting")
    _add_common(i)
    t = sub.add_parser("tile", help="write the padded tiles without counting")
    _add_common(t)
    ir = sub.add_parser("install-review-tool", help="add Plugins > RGC > Review Counts to Fiji")
    ir.add_argument("--fiji", default=None)
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
    if a.cmd in ("count", "inspect", "tile"):
        settings = {k: getattr(a, k) for k in DEFAULT_SETTINGS}
        common = dict(fiji_dir=a.fiji, animals=_chosen_animals(a), tile_px=a.tile_px,
                      margin_px=a.margin_px, memory=a.memory, **settings)
        if a.cmd == "count":
            code = count(a.data, a.output, overwrite=a.overwrite,
                         skip_empty_tiles=a.skip_empty_tiles,
                         min_tissue_fraction=a.min_tissue_fraction,
                         keep_normalized=a.keep_normalized, **common)
            update_log(a.data, a.output)
            sys.exit(code)
        df = (inspect if a.cmd == "inspect" else tile)(a.data, a.output, **common)
        print(df.to_string(index=False))
    if a.cmd == "install-review-tool":
        print("Installed:", install_review_tool(a.fiji), "\nRestart Fiji to see Plugins > RGC > Review Counts.")
    if a.cmd == "status":
        print(review_status(a.output).to_string(index=False))


if __name__ == "__main__":
    main()
