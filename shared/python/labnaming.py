"""Build and parse lab file names.

Convention (docs/sops/file-naming.md):
    sub-<id>_ses-<YYYYMMDD>[_eye-<eye>][_stim-<label>][_run-<NN>]_<modality>.<ext>

Allowed eye and modality values come from shared/vocab.json.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from functools import lru_cache
from pathlib import Path

VOCAB_PATH = Path(__file__).resolve().parent.parent / "vocab.json"

_LABEL = re.compile(r"^[A-Za-z0-9]+$")
_EXT = re.compile(r"^[A-Za-z0-9]+(\.[A-Za-z0-9]+)*$")
_PATTERN = re.compile(
    r"^sub-(?P<sub>[A-Za-z0-9]+)"
    r"_ses-(?P<ses>\d{8})"
    r"(?:_eye-(?P<eye>[A-Za-z0-9]+))?"
    r"(?:_stim-(?P<stim>[A-Za-z0-9]+))?"
    r"(?:_run-(?P<run>\d{2}))?"
    r"_(?P<modality>[A-Za-z0-9]+)"
    r"\.(?P<ext>[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)$"
)


@lru_cache(maxsize=None)
def load_vocab(path: str | None = None) -> dict:
    with open(path or VOCAB_PATH, encoding="utf-8") as f:
        return json.load(f)


def _session_str(ses: str | _dt.date) -> str:
    if isinstance(ses, _dt.date):
        return ses.strftime("%Y%m%d")
    s = str(ses).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return _dt.datetime.strptime(s, fmt).strftime("%Y%m%d")
        except ValueError:
            pass
    raise ValueError(f"session date must be YYYY-MM-DD or YYYYMMDD, got {ses!r}")


def _check_label(name: str, value: str) -> str:
    value = str(value)
    if not _LABEL.match(value):
        raise ValueError(f"{name} must be letters/digits only, got {value!r}")
    return value


def _check_vocab(name: str, value: str, vocab: dict) -> str:
    allowed = vocab[name]
    if value not in allowed:
        raise ValueError(f"{name} {value!r} not in vocab.json (allowed: {', '.join(allowed)})")
    return value


def build_filename(
    sub: str,
    ses: str | _dt.date,
    modality: str,
    ext: str,
    *,
    eye: str | None = None,
    stim: str | None = None,
    run: int | None = None,
    vocab: dict | None = None,
) -> str:
    """Return a convention-compliant file name. Raises ValueError on bad input."""
    vocab = vocab or load_vocab()
    parts = [f"sub-{_check_label('sub', sub)}", f"ses-{_session_str(ses)}"]
    if eye is not None:
        parts.append(f"eye-{_check_vocab('eye', eye, vocab)}")
    if stim is not None:
        parts.append(f"stim-{_check_label('stim', stim)}")
    if run is not None:
        if not isinstance(run, int) or isinstance(run, bool) or not 1 <= run <= 99:
            raise ValueError(f"run must be an int 1-99, got {run!r}")
        parts.append(f"run-{run:02d}")
    parts.append(_check_vocab("modality", modality, vocab))
    ext = str(ext).lstrip(".")
    if not _EXT.match(ext):
        raise ValueError(f"bad extension {ext!r}")
    return "_".join(parts) + "." + ext


def parse_filename(name: str, *, vocab: dict | None = None) -> dict:
    """Split a file name into its fields. Raises ValueError if it doesn't follow the convention."""
    vocab = vocab or load_vocab()
    m = _PATTERN.match(Path(name).name)
    if not m:
        raise ValueError(f"not a convention-compliant file name: {name!r}")
    d = m.groupdict()
    _session_str(d["ses"])  # validates it is a real date
    if d["eye"] is not None:
        _check_vocab("eye", d["eye"], vocab)
    _check_vocab("modality", d["modality"], vocab)
    d["run"] = int(d["run"]) if d["run"] is not None else None
    return d


def is_valid(name: str) -> bool:
    try:
        parse_filename(name)
        return True
    except ValueError:
        return False
