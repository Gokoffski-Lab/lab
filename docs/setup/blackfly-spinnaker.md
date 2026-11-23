# Blackfly S GigE / Spinnaker

Used by the PDCT acquisition GUI ([Behavior video](../workflows/behavior-video-pdct.md)).

- Camera settings live in the camera's onboard **UserSet1**, set up in SpinView.
- PySpin (Python bindings) is installed from the Spinnaker SDK download, matching your Python version and OS. It isn't on PyPI.
- Design notes: `acquisition/behavior-video/acquisition/acquisition/SPINNAKER_PLAN.md`.

!!! note "TODO"
    Add NIC / jumbo-frame settings, the GPIO trigger wiring for Plexon sync, and the B650 PC build notes.
