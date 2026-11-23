# GokoffskiLab — Rat Visual Stimulus

A single-page web app for delivering calibrated visual stimuli to rats. Designed for an **iPad 5th gen (264 ppi)** at a **25 cm viewing distance**, giving 47.6 px/deg of visual angle.

Hosted via GitHub Pages from `docs/index.html`.
URL: https://winstonaluk.github.io/GokoffskiLab/

---

## Stimuli

### Flicker

Full-field square-wave flicker alternating between pure black (`#000`) and pure white (`#fff`).

| Parameter | Value |
|---|---|
| Temporal frequency | 5 Hz |
| Contrast (Michelson) | 100% |
| Waveform | Square wave |
| Timing | Time-based (no frame-count drift) |

The 5 Hz rate matches the peak of the rat contrast sensitivity function (CSF) for temporal modulation. Timing is derived from `performance.now()` so the phase stays locked regardless of frame rate.

---

### Grating

Full-screen sinusoidal drifting grating rendered in WebGL (2D canvas fallback when WebGL is unavailable).

**Luminance equation:** `L(x,t) = 0.5 + 0.5 · sin(2π · f · x + 2π · T · t)`

where `f` = cycles/pixel and `T` = temporal frequency (Hz).

| Parameter | Value |
|---|---|
| Temporal frequency | 5 Hz |
| Contrast (Michelson) | 100% |
| Orientation | Vertical (drifting horizontally) |
| Spatial frequency | Selectable — see presets below |

**Spatial frequency presets**

| Preset (cpd) | c/px at 25 cm | Note |
|---|---|---|
| 0.05 | 0.0011 | Suprathreshold |
| 0.10 | 0.0021 | Peak CSF |
| 0.20 | 0.0042 | Training start (default) |
| 0.35 | 0.0074 | Mid range |
| 0.50 | 0.0105 | Near acuity limit |
| 0.70 | 0.0147 | Acuity ceiling |
| 1.00 | 0.0210 | Above acuity ceiling — threshold sweeps only |

> **Display geometry:** iPad 5th gen, 264 ppi, 25 cm viewing distance.
> Screen width (landscape) = 2048 px / 264 ppi × 2.54 cm = 19.69 cm.
> Visual angle = 2 × atan(9.845/25) × (180/π) = 43.0°. px/deg = 47.6.
> If the viewing distance changes, update `PIXELS_PER_DEG` in `docs/index.html`.

---

### Calibration

Displays a static full-screen split for luminance measurement with a light meter.

| Region | Luminance |
|---|---|
| Left half | Pure white (`#fff`) |
| Right half | Pure black (`#000`) |

No timing or protocol runs. Press **Stop Calibration** to return to the setup panel. Use the white reading and black reading to compute Michelson contrast: `(L_max − L_min) / (L_max + L_min)`.

---

## Session Protocol (Flicker & Grating)

Both stimulus modes run the same 30-minute blocked protocol:

| Phase | Type | Duration |
|---|---|---|
| Baseline | Black screen | 5 min |
| Block 1–10 ON | Stimulus | 1 min each |
| Block 1–10 OFF | Black screen | 1 min each |
| Recovery | Black screen | 5 min |
| **Total** | | **30 min** |

A progress bar runs along the bottom of the screen. The current phase name is shown in a label at the top.

---

## Data Export

After a session, press **Export CSV** to download a timestamped log file (`rat_stim_YYYYMMDD_HHMM.csv`).

| Column | Description |
|---|---|
| `timestamp_s` | Seconds since session start |
| `event` | `session_start`, `phase_start`, `phase_end`, `session_end` |
| `phase` | Phase name (e.g. `Block 3 ON`) |
| `mode` | `flicker` or `grating` |
| `sf_cpd` | Spatial frequency in cycles/degree |
| `tf_hz` | Temporal frequency in Hz |
