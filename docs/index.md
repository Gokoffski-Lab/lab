# Gokoffski Lab

SOPs, workflows and software documentation for the Gokoffski lab (UC Irvine, Gavin Herbert Eye Institute).

| I want to… | Go to |
|---|---|
| Know where my data goes and how to name files | [Data organization](sops/data-organization.md) · [File naming](sops/file-naming.md) |
| Get onto CRSP | [CRSP access](sops/crsp-access.md) |
| Run an assay's analysis | [Workflows](workflows/index.md) |
| Set up a rig or computer | Setup: [PTB-3](setup/ptb3-apple-silicon.md) · [Blackfly S](setup/blackfly-spinnaker.md) · [HPC3](setup/hpc3.md) |
| Show the rat visual stimulus on the iPad | [Stimulus page](https://gokoffski-lab.github.io/lab/stimuli/) · [Visual stimuli](workflows/visual-stimuli.md) |
| Fix or add a page | [Getting started](getting-started.md) |

!!! warning "Data never goes in git"
    Raw and processed data live on CRSP. This site and the repo hold code and instructions only.

## Projects

| Project | Data types |
|---|---|
| WET – Rat | metadata, OKN, PRT, ERG/PhNR/VEP, LFP, RBPMS, optic nerve |
| WET – Pig (**GLP**) | metadata, impedance, ERG, behavior + surgery video, flatmount RBPMS, optic nerve (CTB), fundus |
| DOD | metadata, PhNR, fVEP, flatmount RBPMS, optic nerve, LFP |
| GCR (Glaucoma) | metadata, PhNR, fVEP, flatmount rabies, optic nerve, LFP |
| Amblyopia – Rats | metadata, PhNR, fVEP, pERG, LFP, behavior (PDCT) |
| Amblyopia – Ferrets | metadata, behavior, ephys (NeuroShank / NeuroGrid) |
| mTOR/Rheb | metadata, PhNR, fVEP, pERG, LFP, behavior (VCA) |

Abbreviations: WET whole eye transplant · GCR glaucoma · PRT pupillary reflex test · VCA visual cliff assay ·
PDCT pole descent task · NS/NG NeuroShank/NeuroGrid.
