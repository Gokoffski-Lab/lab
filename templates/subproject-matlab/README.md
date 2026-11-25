# <name>: <one-line purpose>

> **Status:** 🧪 experimental · **Owner:** @<github-handle> · **Language:** MATLAB <R20xx+> (+ toolboxes) ·
> **Runs on:** <machine> · **Docs:** [<workflow page>](https://gokoffski-lab.github.io/lab/workflows/<page>/)

<Two sentences: input → output, and what the output is used for.>

## Layout
```
<name>/
├── <main_function>.m   entry point: a function with name/value options, not a script with hard-coded paths
├── +<name>/            optional package for helpers
└── tests/              function-based tests (runtests)
```

## Run
```matlab
% from the repo root
addpath('<path/to/name>'); addpath('shared/matlab');
<main_function>('InputDir', '<CRSP path>', 'OutputDir', '<CRSP path>');
```

## Test
```matlab
runtests('<path/to/name>/tests')
```

## Required toolboxes / SDKs
- <e.g. Signal Processing Toolbox, Plexon PL2 SDK>
