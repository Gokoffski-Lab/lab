# CLAUDE.md — behavior-video subproject (PDCT acquisition + analysis)

This subproject (`acquisition/behavior-video/` in the lab monorepo) contains two independent applications plus a shared schema
package that is the contract between them.

```
./
├── shared/schema/    contract: session_metadata.json, trials.csv, timestamp sidecars
├── acquisition/      behavioral video acquisition GUI — see acquisition/CLAUDE.md
└── analysis/         DeepLabCut analysis pipeline — see analysis/CLAUDE.md
```

Read `acquisition/CLAUDE.md` and `analysis/CLAUDE.md` before working in either
subdirectory — each carries its own domain context, architecture invariants,
and checkpoint list. Keep app-specific code inside its own subdirectory; the
only code shared between the two is `shared/schema/`.

`QUESTIONS.md` at the behavior-video root collects ambiguities logged during unattended runs.
`notes/OVERNIGHT_REPORT.md` is the summary of the initial unattended build (prompt: `notes/overnight-prompt.md`).
