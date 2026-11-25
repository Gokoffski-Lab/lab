# Visual stimuli

## iPad web stimulus (rats)
**Code:** [`acquisition/stimuli/web/`](https://github.com/Gokoffski-Lab/lab/tree/main/acquisition/stimuli/web) ·
**Live page:** https://gokoffski-lab.github.io/lab/stimuli/

Full-field 5 Hz square-wave flicker and a drifting sinusoidal grating (WebGL), calibrated for an
iPad 5th gen (264 ppi) at 25 cm (47.6 px/deg). Parameters and spatial-frequency presets are in that folder's README.

!!! warning "Moved"
    The page used to be served from Winston's personal GitHub Pages. Update the iPad bookmarks / home-screen shortcuts to the new address.

## Psychtoolbox-3 (ephys sessions)
**Code:** [`acquisition/stimuli/ptb/`](https://github.com/Gokoffski-Lab/lab/tree/main/acquisition/stimuli/ptb)

Pre/post rest phases with alternating stimulus / black-screen cycles and 10 Hz flicker.
Runs on Apple Silicon with the fixes in [PTB-3 on Apple Silicon](../setup/ptb3-apple-silicon.md).

!!! note "TODO"
    The PTB script isn't committed yet. See [Migration status](../migration.md).
