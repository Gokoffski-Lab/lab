# stimuli/ptb: Psychtoolbox-3 visual stimuli

> **Status:** ⏳ missing code · **Owner:** @winstonaluk · **Language:** MATLAB + Psychtoolbox-3 ·
> **Runs on:** stimulus Mac (Apple Silicon) during ephys sessions ·
> **Docs:** [Visual stimuli](https://gokoffski-lab.github.io/lab/workflows/visual-stimuli/) · [PTB-3 on Apple Silicon](https://gokoffski-lab.github.io/lab/setup/ptb3-apple-silicon/)

Full-field stimulus for electrophysiology: pre/post rest phases and alternating stimulus / black-screen
cycles with 10 Hz flicker.

## Missing code
| File | Where it probably is | Notes |
|---|---|---|
| PTB stimulus script (`.m`) | Mac used for ephys stimulus, MATLAB folder | Includes the `KbCheck(-1)` keyboard-index fallback and redraw-during-wait fixes |

When adding it:
- Put tunable values (durations, flicker frequency, cycle counts) at the top of the script, or in a `params` struct, and list them in a table here.
- Write logs and timestamps outside the repo, using `shared/matlab/lab_filename.m` for names.

## Run
```matlab
% from the repo root
addpath('acquisition/stimuli/ptb'); addpath('shared/matlab');
% <script name>   % fill in once committed
```

## History
Imported from `winstonaluk/ptb-visualstim` (archived), which only had a README.
