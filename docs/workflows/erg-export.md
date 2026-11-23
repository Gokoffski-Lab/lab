# ERG / VEP export (Diagnosys Celeris / Espion)

**Owner:** Winston · **Projects:** all ERG/VEP projects · **Code:** [`acquisition/erg/`](https://github.com/Gokoffski-Lab/lab/tree/main/acquisition/erg) (to build, Python)

## Protocols and points of interest (POIs)
| Protocol | POIs |
|---|---|
| fVEP | P1 and N1 amplitude + latency |
| pERG | (TBD) |
| PhNR | a-wave, b-wave amplitude; PhNR amplitude |

Espion's automatic peak detection isn't reliable. Analysts place the cursors on the true response, and
the values come from the exported **Marker Tables**, so every value has been checked by a person.

## Current manual path
1. In Espion, place cursors on the POIs and export the Marker Table (CSV) for each protocol.
2. Bulk export: **Transfer** → `.exp` files → Diagnosys **eXporter** → TXT/CSV.

## Systems
- Acquisition consoles are AVR-based, so they stay on **Espion V6** (late build, Firebird 4 / ODS 13.0 `.fd4`).
- Analysis PCs should run the **same late-V6 build**. Espion V6 with Firebird 2.5 can't open ODS 13.0 databases (ISC 335544379).

!!! note "TODO"
    Add marker-table template CSVs per protocol (to `acquisition/erg/templates/`) and the parser. Add an inter-analyst consistency check, since several analysts currently compile POIs by hand.
