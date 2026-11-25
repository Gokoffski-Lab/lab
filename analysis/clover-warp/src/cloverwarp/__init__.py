"""cloverwarp -- reconstruct retinal clover flatmounts from their vasculature.

The idea in one paragraph: a clover flatmount has been cut and flattened, so
its geometry no longer matches the eye it came from. But the same eye's in
vivo angiogram shows that retina's vascular tree *intact*. Register each
petal to the angiogram using vessel bifurcations as correspondences, and two
things fall out at once -- the clover is reassembled (every petal now sits in
one common frame), and every cell counted in the flatmount acquires a real
retinal position. The angiogram is the reference, not the petals' cut edges.

Start here::

    from cloverwarp.config import load_config
    from cloverwarp.pipeline import register_from_landmarks

    cfg = load_config("config/example.yaml")
    result = register_from_landmarks(cfg, {"L1": "L1.csv", "L2": "L2.csv"})
    print(result.qc)

and read ``docs/METHOD.md`` before trusting a number.
"""

__version__ = "0.1.0.dev0"

__all__ = [
    "__version__",
    "config",
    "frames",
    "graph",
    "io",
    "landmarks",
    "match",
    "petals",
    "pipeline",
    "points",
    "qc",
    "synth",
    "vessels",
    "warp",
]
