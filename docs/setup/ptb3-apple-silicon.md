# Psychtoolbox-3 on Apple Silicon

Known issues and the fixes used in the lab's PTB stimulus scripts:

| Symptom | Fix |
|---|---|
| `KbCheck(-1)` fails / keyboard not detected | Fall back to an explicit keyboard device index |
| Flip timeouts (Vulkan/Metal) during long waits | Keep redrawing the screen during waits instead of idling between flips |

!!! note "TODO"
    Add the MATLAB and PTB versions known to work, and the install steps.
