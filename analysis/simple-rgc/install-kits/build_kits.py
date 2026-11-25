"""Build the Windows and Mac (Apple chip) install kits for rbpms-count.

Each kit = Fiji (review tool pre-installed) + rbpms-count (main, committed files) + Miniforge installer
+ double-click Set up / Start / Open Fiji scripts + READ ME FIRST.txt.
Fiji entries are copied zip-to-zip so the Mac symlinks and executable bits survive.
"""
import io, subprocess, sys, time, zipfile
from pathlib import Path

HERE = Path(__file__).parent
DL = HERE / "downloads"
REPO = Path.home() / "Documents" / "rbpms-count"
OUT = Path(__file__).resolve().parent
NOW = time.localtime()[:6]

PKGS = '"pandas>=2.0" "matplotlib>=3.7" jinja2 jupyterlab ipykernel'

# ------------------------------------------------------------------ Windows scripts (CRLF)
WIN_SETUP = r'''@echo off
setlocal
title RBPMS count - set up
cd /d "%~dp0"
set "KIT=%~dp0"
set "KIT=%KIT:~0,-1%"
set "PY=%KIT%\python"

echo.
echo  RBPMS count - one-time set up
echo  ==============================
echo.

if not "%KIT%"=="%KIT: =%" goto spaces
if not "%PY:~95%"=="" goto toolong

if exist "%PY%\python.exe" goto packages
echo  Step 1 of 2: installing Python into this folder. This takes a few minutes...
start /wait "" "%KIT%\installers\Miniforge3-Windows-x86_64.exe" /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /NoRegistry=1 /NoShortcuts=1 /S /D=%PY%
if not exist "%PY%\python.exe" goto failed

:packages
echo  Step 2 of 2: installing the notebook packages. This needs internet and takes a few minutes...
echo.
call "%PY%\Scripts\conda.exe" install -y -p "%PY%" --override-channels -c conda-forge __PKGS__
if errorlevel 1 goto failed
"%PY%\python.exe" -c "import pandas, matplotlib, jupyterlab" || goto failed

echo.
echo  ==============================================================
echo   Set up finished. From now on, double-click 2-Start.
echo  ==============================================================
echo.
pause
exit /b 0

:spaces
echo  This folder's location has a space in it:
echo     %KIT%
echo  Python does not install reliably there. Move the whole RBPMS-Count-Windows folder
echo  to a place without spaces, for example C:\RBPMS-Count-Windows, and run 1-Setup again.
echo.
pause
exit /b 1

:toolong
echo  This folder is too deep inside other folders for Python to install:
echo     %KIT%
echo  Move the whole RBPMS-Count-Windows folder to C:\RBPMS-Count-Windows
echo  or to Documents, and run 1-Setup again.
echo.
pause
exit /b 1

:failed
echo.
echo  Set up did not finish. Check the internet connection and run 1-Setup again.
echo  If it fails again, send a photo of this window to whoever gave you this kit.
echo.
pause
exit /b 1
'''.replace("__PKGS__", PKGS)

WIN_START = r'''@echo off
setlocal
title RBPMS count - notebook (keep this window open)
set "KIT=%~dp0"
set "KIT=%KIT:~0,-1%"
set "PY=%KIT%\python"
if not exist "%PY%\python.exe" goto nosetup
"%PY%\python.exe" -c "import jupyterlab" 2>nul || goto nosetup

set "FIJI_DIR=%KIT%\Fiji"
set "PATH=%PY%;%PY%\Library\mingw-w64\bin;%PY%\Library\usr\bin;%PY%\Library\bin;%PY%\Scripts;%PATH%"
cd /d "%KIT%\rbpms-count"
echo.
echo  The notebook opens in your web browser in a few seconds.
echo  Keep this window open while you work. Close it when you are done.
echo.
"%PY%\python.exe" -m jupyterlab rbpms_count.ipynb
exit /b 0

:nosetup
echo.
echo  Set up has not been run yet. Double-click 1-Setup first.
echo.
pause
exit /b 1
'''

WIN_FIJI = r'''@echo off
start "" "%~dp0Fiji\fiji-windows-x64.exe"
'''

# ------------------------------------------------------------------ Mac scripts (LF)
MAC_SETUP = r'''#!/bin/bash
# RBPMS count - one-time set up (Mac, Apple chip)
cd "$(dirname "$0")" || exit 1
KIT="$(pwd)"
PY="$KIT/python"
finish() { echo; read -n 1 -s -r -p "  Press any key to close this window."; echo; exit "$1"; }

echo
echo "  RBPMS count - one-time set up"
echo "  =============================="
echo

if [ "$(uname -m)" != "arm64" ]; then
  echo "  This kit is for Macs with an Apple chip (M1, M2, M3, M4...). This Mac has an Intel chip."
  echo "  Ask for the Intel version of the kit."
  finish 1
fi
case "$KIT" in *" "*)
  echo "  This folder's location has a space in it:"
  echo "     $KIT"
  echo "  Python does not install reliably there. Move the whole RBPMS-Count-Mac folder into your"
  echo "  home folder or Documents (if those have no space), and run 1-Setup again."
  finish 1;;
esac

echo "  Allowing the programs in this folder to open (they were downloaded, so the Mac blocks them)..."
xattr -dr com.apple.quarantine "$KIT" 2>/dev/null
chmod +x "$KIT"/*.command "$KIT/Fiji/fiji" 2>/dev/null

if [ ! -x "$PY/bin/python" ]; then
  echo "  Step 1 of 2: installing Python into this folder. This takes a few minutes..."
  bash "$KIT/installers/Miniforge3-MacOSX-arm64.sh" -b -p "$PY" > "$KIT/installers/python-install.log" 2>&1
  if [ ! -x "$PY/bin/python" ]; then
    echo "  Python did not install. Details are in installers/python-install.log"
    finish 1
  fi
fi

echo "  Step 2 of 2: installing the notebook packages. This needs internet and takes a few minutes..."
echo
if ! "$PY/bin/conda" install -y -p "$PY" --override-channels -c conda-forge __PKGS__ \
   || ! "$PY/bin/python" -c "import pandas, matplotlib, jupyterlab"; then
  echo
  echo "  Set up did not finish. Check the internet connection and run 1-Setup again."
  echo "  If it fails again, send a screenshot of this window to whoever gave you this kit."
  finish 1
fi

echo
echo "  =============================================================="
echo "   Set up finished. From now on, double-click 2-Start."
echo "  =============================================================="
finish 0
'''.replace("__PKGS__", PKGS)

MAC_START = r'''#!/bin/bash
# RBPMS count - open the notebook (keep this window open while you work)
cd "$(dirname "$0")" || exit 1
KIT="$(pwd)"
PY="$KIT/python"
if [ ! -x "$PY/bin/python" ] || ! "$PY/bin/python" -c "import jupyterlab" 2>/dev/null; then
  echo
  echo "  Set up has not been run yet. Double-click 1-Setup first."
  echo
  read -n 1 -s -r -p "  Press any key to close this window."
  exit 1
fi
export FIJI_DIR="$KIT/Fiji"
export PATH="$PY/bin:$PATH"
cd "$KIT/rbpms-count" || exit 1
echo
echo "  The notebook opens in your web browser in a few seconds."
echo "  Keep this window open while you work. Close it when you are done."
echo
exec "$PY/bin/python" -m jupyterlab rbpms_count.ipynb
'''

MAC_FIJI = r'''#!/bin/bash
open "$(dirname "$0")/Fiji/Fiji.app"
'''

README = '''RBPMS COUNT - {title}
{rule}

This folder has everything the RGC counting workflow needs:
  Fiji           the image program, with the review tool already in its Plugins menu
  rbpms-count    the notebook and scripts (images go in rbpms-count{s}data)
  installers     Python, installed into this folder by 1-Setup

Nothing is installed anywhere else on the computer. To remove it all, delete this folder.


FIRST TIME ONLY
---------------
1. {unzip}
   The folder's location must not contain a space ({example}).
2. {setup}
   It installs Python into this folder (5 to 10 minutes, needs internet).
   Wait for "Set up finished", then press any key.


EVERY TIME
----------
1. Copy your images into rbpms-count{s}data, one folder per retina,
   for example  rbpms-count{s}data{s}R000L{s}R000L_20x_a1.czi
2. Double-click 2-Start. The notebook opens in your web browser.
   Keep the {window} open while you work; close it when you are done.
3. Run the notebook from top to bottom (Run > Run All Cells, or Shift+Enter box by box).
4. For step 2 (review), double-click 3-Open-Fiji, then choose
   Plugins > RGC > Review Counts.

Results are saved in rbpms-count{s}output.
The full instructions are in rbpms-count{s}README.md. Skip its "Before you start" section:
this kit has already done that part.


IF SOMETHING GOES WRONG
-----------------------
{trouble}
- Moved this folder somewhere else? Delete the "python" folder inside it and run 1-Setup again.
- The notebook says it cannot find Fiji: make sure you opened it with 2-Start, not another way.

Kit contents: Fiji (latest, {fiji_name}), Miniforge {mf} ({mf_file}), rbpms-count main at commit {commit}.
Built {date}.
'''

WIN_TROUBLE = '''- "Windows protected your PC" when opening 1-Setup or 2-Start: click "More info", then "Run anyway".
  Windows asks this once for files that came from the internet.
- 1-Setup says the location has a space or is too deep: move the whole folder to C:\\RBPMS-Count-Windows.'''

MAC_TROUBLE = '''- "1-Setup cannot be opened" or "Apple could not verify...": open System Settings > Privacy & Security,
  scroll down, and click "Open Anyway" next to 1-Setup. You only need to do this once; 1-Setup then
  unblocks everything else in this folder.
  Another way: open the Terminal app, type  bash  and a space, drag 1-Setup onto the Terminal window,
  and press Return.
- This kit is for Macs with an Apple chip (M1 or later). Check under Apple menu > About This Mac.'''


def add_text(z, name, text, mode=0o644, crlf=False, unix=True):
    data = text.replace("\r\n", "\n")
    if crlf:
        data = data.replace("\n", "\r\n")
    info = zipfile.ZipInfo(name, NOW)
    info.compress_type = zipfile.ZIP_DEFLATED
    if unix:
        info.create_system = 3
        info.external_attr = (0o100000 | mode) << 16
    z.writestr(info, data.encode("utf-8"))


def add_file(z, name, path, mode=0o644, unix=True):
    info = zipfile.ZipInfo(name, NOW)
    info.compress_type = zipfile.ZIP_DEFLATED
    if unix:
        info.create_system = 3
        info.external_attr = (0o100000 | mode) << 16
    with open(path, "rb") as f, z.open(info, "w") as dst:
        while chunk := f.read(1 << 20):
            dst.write(chunk)


def copy_zip(z, src_path, old_prefix, new_prefix, unix=True):
    with zipfile.ZipFile(src_path) as src:
        for i in src.infolist():
            if not i.filename.startswith(old_prefix):
                continue
            info = zipfile.ZipInfo(new_prefix + i.filename[len(old_prefix):], i.date_time)
            info.external_attr = i.external_attr
            info.create_system = i.create_system if unix else 0
            if not unix:  # keep only the DOS bits on Windows
                info.external_attr = i.external_attr & 0xFFFF
                if i.is_dir():
                    info.external_attr |= 0x10
            if i.is_dir():
                z.writestr(info, b"")
                continue
            ext = info.filename.rsplit(".", 1)[-1].lower()
            info.compress_type = zipfile.ZIP_STORED if ext in {"jar", "zip", "gz", "png", "jpg", "jmod"} else zipfile.ZIP_DEFLATED
            with src.open(i) as s, z.open(info, "w") as d:
                while chunk := s.read(1 << 20):
                    d.write(chunk)


def repo_archive():
    commit = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "--short", "main"], text=True).strip()
    data = subprocess.check_output(["git", "-C", str(REPO), "archive", "--format=zip", "main"])
    return commit, data


def build(kind):
    win = kind == "win"
    root = "RBPMS-Count-Windows/" if win else "RBPMS-Count-Mac/"
    fiji_zip = DL / ("fiji-latest-win64-jdk.zip" if win else "fiji-latest-macos-arm64-jdk.zip")
    mf = DL / ("Miniforge3-Windows-x86_64.exe" if win else "Miniforge3-MacOSX-arm64.sh")
    out = OUT / ("RBPMS-Count-Windows.zip" if win else "RBPMS-Count-Mac-AppleChip.zip")
    commit, repo_zip = repo_archive()
    unix = not win
    s = "\\" if win else "/"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        readme = README.format(
            title="WINDOWS KIT" if win else "MAC KIT (Apple chip)",
            rule="=" * (len("RBPMS COUNT - ") + len("WINDOWS KIT" if win else "MAC KIT (Apple chip)")),
            s=s,
            unzip=("Right-click the zip and choose Extract All. Do not run anything from inside the zip."
                   if win else "Double-click the zip to unzip it, and move the RBPMS-Count-Mac folder to Documents."),
            example="C:\\RBPMS-Count-Windows works" if win else "Documents works",
            setup=("Double-click 1-Setup. If Windows asks, click More info > Run anyway." if win else
                   "Double-click 1-Setup. If the Mac blocks it, see IF SOMETHING GOES WRONG below."),
            window="black window" if win else "Terminal window",
            trouble=WIN_TROUBLE if win else MAC_TROUBLE,
            fiji_name=fiji_zip.name, mf="26.9.4-2", mf_file=mf.name, commit=commit,
            date=time.strftime("%Y-%m-%d"))
        add_text(z, root + "READ ME FIRST.txt", readme, crlf=win, unix=unix)
        if win:
            add_text(z, root + "1-Setup.bat", WIN_SETUP, crlf=True, unix=False)
            add_text(z, root + "2-Start.bat", WIN_START, crlf=True, unix=False)
            add_text(z, root + "3-Open-Fiji.bat", WIN_FIJI, crlf=True, unix=False)
        else:
            add_text(z, root + "1-Setup.command", MAC_SETUP, 0o755)
            add_text(z, root + "2-Start.command", MAC_START, 0o755)
            add_text(z, root + "3-Open-Fiji.command", MAC_FIJI, 0o755)
        add_file(z, root + "installers/" + mf.name, mf, 0o755, unix=unix)
        # rbpms-count, committed files of main
        with zipfile.ZipFile(io.BytesIO(repo_zip)) as rz:
            for i in rz.infolist():
                info = zipfile.ZipInfo(root + "rbpms-count/" + i.filename, i.date_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                if unix:
                    info.create_system = 3
                    info.external_attr = ((0o040755 if i.is_dir() else 0o100644) << 16) | (0x10 if i.is_dir() else 0)
                elif i.is_dir():
                    info.external_attr = 0x10
                z.writestr(info, b"" if i.is_dir() else rz.read(i))
        # Fiji with the review tool pre-installed
        copy_zip(z, fiji_zip, "Fiji/", root + "Fiji/", unix=unix)
        tool = subprocess.check_output(["git", "-C", str(REPO), "show", "main:scripts/review_counts.groovy"])
        add_text(z, root + "Fiji/scripts/Plugins/RGC/Review_Counts.groovy", tool.decode("utf-8"), unix=unix)
    tmp.replace(out)
    print(f"{out}  {out.stat().st_size / 1e9:.2f} GB")


if __name__ == "__main__":
    for k in sys.argv[1:] or ["win", "mac"]:
        build(k)
