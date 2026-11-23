# acquisition/ephys/

Plexon ephys processing (MATLAB). Docs: [docs/workflows/ephys-pl2-conversion.md](../../docs/workflows/ephys-pl2-conversion.md).

**Status: ⏳ to import.** Add:
- `pl2_to_mat.m`: batch `.pl2` → `.mat` conversion, plus renaming from a metadata CSV
- `summarize_recording_duration_triggers.m`: per-file duration + trigger count → CSV
- an example metadata CSV (headers + one fake row, no real animal data)

Ferret NeuroShank/NeuroGrid code goes in `ferret/` here once it exists.
