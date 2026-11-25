# acquisition/

Code that runs **at the rig**: it records, presents stimuli, or exports straight from an instrument.

| Subproject | What | Language | Status |
|---|---|---|---|
| [`behavior-video/`](behavior-video/) | PDCT multi-camera acquisition GUI + DeepLabCut analysis | Python | ✅ active |
| [`stimuli/web/`](stimuli/web/) | iPad rat stimulus (flicker / drifting grating), live at `/stimuli/` | HTML/JS (WebGL) | ✅ active |
| [`stimuli/ptb/`](stimuli/ptb/) | Psychtoolbox-3 stimuli for ephys sessions | MATLAB | ⏳ missing code |
| [`ephys/`](ephys/) | Plexon `.pl2` → `.mat` conversion, recording summaries | MATLAB | ⏳ missing code |
| [`erg/`](erg/) | Diagnosys Celeris/Espion export + marker-table parsing | Python | ⏳ to build |

Analysis that runs on already-recorded data goes in [`../analysis/`](../analysis/).
