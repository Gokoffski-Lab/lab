"""Vessel mask -> skeleton -> bifurcation graph, with matchable descriptors.

The matching problem is solved on *graphs*, not on pixels. A retinal vascular
tree is a near-binary tree rooted at the optic disc, and the quantity that
makes a bifurcation identifiable across two modalities is not its position
(the petal has moved) nor its brightness (the stains differ) but its place in
the tree: how many branch points lie between it and the disc, how the
daughter branches split, and the ratio of their calibres. Those survive
flattening, fixation and a change of imaging modality. That is the whole
reason this approach can work where intensity-based registration cannot.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

try:  # networkx is a hard dependency, but keep the import failure legible
    import networkx as nx
except ImportError as exc:  # pragma: no cover
    raise ImportError("cloverwarp.graph requires networkx") from exc

from skimage import morphology
from skimage.graph import pixel_graph

__all__ = [
    "VesselGraph",
    "build_graph",
    "bifurcation_descriptors",
    "DESCRIPTOR_NAMES",
]


@dataclass
class VesselGraph:
    """A rooted vessel tree.

    Nodes are skeleton branch points and endpoints, carrying ``xy``,
    ``degree``, ``radius_px`` (distance-transform estimate) and, once
    :meth:`root_at` has run, ``depth`` (branch points to the disc) and
    ``path_length_px``.
    """

    graph: nx.Graph
    root: int | None = None
    meta: dict = field(default_factory=dict)

    # --- construction helpers ---------------------------------------------

    @property
    def nodes_xy(self) -> np.ndarray:
        order = sorted(self.graph.nodes)
        return np.array([self.graph.nodes[n]["xy"] for n in order], dtype=float)

    @property
    def node_ids(self) -> list[int]:
        return sorted(self.graph.nodes)

    def bifurcations(self, min_degree: int = 3) -> list[int]:
        return [n for n, d in self.graph.degree() if d >= min_degree]

    def endpoints(self) -> list[int]:
        return [n for n, d in self.graph.degree() if d == 1]

    def root_at(self, xy) -> VesselGraph:
        """Set the root to the node nearest ``xy`` and annotate depths.

        Pass the optic disc centre. For a petal, pass the point on the petal
        that corresponds to the disc -- the petals of a clover all meet at
        the disc, so that corner is identifiable on each petal, and it is the
        one landmark you get for free.
        """
        xy = np.asarray(xy, dtype=float).reshape(2)
        ids = self.node_ids
        if not ids:
            raise ValueError("graph has no nodes")
        pts = self.nodes_xy
        root = ids[int(np.argmin(((pts - xy) ** 2).sum(1)))]
        self.root = root
        lengths = nx.single_source_dijkstra_path_length(
            self.graph, root, weight="length_px"
        )
        # branch-point depth: count degree>=3 nodes along the path to root
        for n in self.graph.nodes:
            self.graph.nodes[n]["path_length_px"] = float(lengths.get(n, np.inf))
        for n in self.graph.nodes:
            if n not in lengths:
                self.graph.nodes[n]["depth"] = -1
                continue
            try:
                path = nx.shortest_path(self.graph, root, n, weight="length_px")
            except nx.NetworkXNoPath:  # pragma: no cover
                self.graph.nodes[n]["depth"] = -1
                continue
            self.graph.nodes[n]["depth"] = int(
                sum(1 for m in path[:-1] if self.graph.degree(m) >= 3)
            )
        return self

    def prune_spurs(self, max_length_px: float = 20.0) -> VesselGraph:
        """Drop short terminal twigs, which are usually skeletonisation noise.

        Runs to a fixed point, because removing one spur can expose another.
        """
        changed = True
        while changed:
            changed = False
            for n in list(self.graph.nodes):
                if n == self.root or self.graph.degree(n) != 1:
                    continue
                nbrs = list(self.graph.neighbors(n))
                if not nbrs:
                    self.graph.remove_node(n)
                    changed = True
                    continue
                edge = self.graph.edges[n, nbrs[0]]
                if edge.get("length_px", 0.0) <= max_length_px:
                    self.graph.remove_node(n)
                    changed = True
        return self


def _skeleton_to_graph(skel: np.ndarray, radius: np.ndarray) -> nx.Graph:
    """Collapse a pixel skeleton into a node/edge graph.

    Nodes are pixels with degree != 2 (branch points and endpoints); edges
    are the degree-2 runs between them, with ``length_px`` the run length and
    ``radius_px`` the median distance-transform value along it.
    """
    g_px, nodes_px = pixel_graph(skel, connectivity=2)
    g_px = g_px.tocoo()
    adj: dict[int, list[int]] = {}
    for i, j in zip(g_px.row, g_px.col, strict=True):
        if i == j:
            continue
        adj.setdefault(int(i), []).append(int(j))
    coords = np.column_stack(np.unravel_index(nodes_px, skel.shape))  # (row, col)

    deg = {i: len(v) for i, v in adj.items()}
    special = {i for i, d in deg.items() for _ in [0] if d != 2}
    # an isolated loop has no degree != 2 pixel; seed one arbitrarily
    if not special and adj:
        special = {next(iter(adj))}

    g = nx.Graph()
    for i in special:
        r, c = coords[i]
        g.add_node(
            i,
            xy=(float(c), float(r)),  # (x, y) == (col, row)
            radius_px=float(radius[r, c]),
            degree=deg.get(i, 0),
        )

    visited_edges: set[tuple[int, int]] = set()
    for start in special:
        for first in adj.get(start, []):
            key = (min(start, first), max(start, first))
            if key in visited_edges:
                continue
            prev, cur = start, first
            run = [start, first]
            while cur not in special:
                nxt = [k for k in adj.get(cur, []) if k != prev]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
                run.append(cur)
            for a, b in zip(run, run[1:], strict=False):
                visited_edges.add((min(a, b), max(a, b)))
            end = run[-1]
            if end not in special:
                continue
            pts = coords[run]
            seg = np.sqrt((np.diff(pts, axis=0) ** 2).sum(1)).sum()
            rad = float(np.median(radius[pts[:, 0], pts[:, 1]]))
            if g.has_edge(start, end):
                if seg < g.edges[start, end]["length_px"]:
                    g.edges[start, end].update(length_px=float(seg), radius_px=rad)
            else:
                g.add_edge(
                    start,
                    end,
                    length_px=float(max(seg, 1e-6)),
                    radius_px=rad,
                    n_pixels=len(run),
                )
    return g


def _merge_close_nodes(g: nx.Graph, merge_px: float) -> nx.Graph:
    """Collapse nodes within ``merge_px`` of each other into one.

    Skeletonisation turns a single anatomical bifurcation into a small
    *cluster* of adjacent pixels that each have degree > 2, so the raw graph
    contains two or three near-identical nodes per real branch point. Left
    alone they inflate the bifurcation count, fragment the descriptors, and
    let one FA node absorb several petal nodes during matching.
    """
    if merge_px <= 0 or g.number_of_nodes() < 2:
        return g
    ids = list(g.nodes)
    pts = np.array([g.nodes[n]["xy"] for n in ids], dtype=float)

    parent = {n: n for n in ids}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    from scipy.spatial import cKDTree

    tree = cKDTree(pts)
    for i, j in tree.query_pairs(merge_px):
        union(ids[i], ids[j])

    groups: dict[int, list[int]] = {}
    for n in ids:
        groups.setdefault(find(n), []).append(n)

    out = nx.Graph()
    rep_of = {}
    for rep, members in groups.items():
        mpts = np.array([g.nodes[m]["xy"] for m in members], dtype=float)
        out.add_node(
            rep,
            xy=tuple(mpts.mean(axis=0)),
            radius_px=float(max(g.nodes[m].get("radius_px", 0.0) for m in members)),
            degree=0,
        )
        for m in members:
            rep_of[m] = rep

    for a, b, data in g.edges(data=True):
        ra, rb = rep_of[a], rep_of[b]
        if ra == rb:
            continue  # internal to a merged cluster
        if out.has_edge(ra, rb):
            if data.get("length_px", 0.0) > out.edges[ra, rb].get("length_px", 0.0):
                continue
        out.add_edge(ra, rb, **data)

    for n in out.nodes:
        out.nodes[n]["degree"] = out.degree(n)
    return out


def _connect_at_root(g: nx.Graph, disc_xy) -> nx.Graph:
    """Join every component to a node at the optic disc.

    This encodes real anatomy: every retinal vessel enters at the disc, so a
    tree that has fragmented into separate components is a *segmentation*
    failure, not a biological fact. Vesselness filters reliably drop out
    exactly at the disc, where many large vessels converge and the ridge
    structure breaks down, which otherwise leaves each primary branch as its
    own island -- and then ``depth`` and ``path_length`` become meaningless
    and the matcher has nothing structural to work with.

    The bridging edges are marked ``bridged=True`` so QC can report how much
    of the tree's connectivity was assumed rather than observed.
    """
    disc = np.asarray(disc_xy, dtype=float).reshape(2)
    comps = list(nx.connected_components(g))
    if len(comps) <= 1 and any(
        np.allclose(g.nodes[n]["xy"], disc, atol=1.0) for n in g.nodes
    ):
        return g

    root_id = -1
    while root_id in g.nodes:  # pragma: no cover
        root_id -= 1
    g.add_node(root_id, xy=tuple(disc), radius_px=0.0, degree=0, is_disc=True)

    for comp in comps:
        members = list(comp)
        pts = np.array([g.nodes[n]["xy"] for n in members], dtype=float)
        d = np.hypot(*(pts - disc).T)
        nearest = members[int(np.argmin(d))]
        g.add_edge(
            root_id,
            nearest,
            length_px=float(max(d.min(), 1e-6)),
            radius_px=float(g.nodes[nearest].get("radius_px", 1.0)),
            bridged=True,
        )
    for n in g.nodes:
        g.nodes[n]["degree"] = g.degree(n)
    return g


def build_graph(
    mask: np.ndarray,
    disc_xy=None,
    prune_px: float = 20.0,
    merge_px: float = 5.0,
    min_component_nodes: int = 3,
    connect_at_root: bool = True,
) -> VesselGraph:
    """Build a :class:`VesselGraph` from a binary vessel mask.

    Parameters
    ----------
    disc_xy
        Optic disc position. Strongly recommended: it is the root, and with
        ``connect_at_root`` it is also what holds a fragmented segmentation
        together.
    merge_px
        Collapse branch-point pixel clusters closer than this. Roughly the
        half-width of the largest vessel.
    min_component_nodes
        Drop components smaller than this. Fragments of two nodes are noise.
    connect_at_root
        Bridge each component to the disc (see :func:`_connect_at_root`).
        Turn this off only if you want to see how fragmented the raw
        segmentation really is -- the ``n_components`` entry in ``meta``
        reports that either way.
    """
    mask = np.asarray(mask, dtype=bool)
    if not mask.any():
        raise ValueError("empty vessel mask: nothing to skeletonise")
    from scipy import ndimage as ndi

    radius = ndi.distance_transform_edt(mask)
    skel = morphology.skeletonize(mask)
    g = _skeleton_to_graph(skel, radius)
    g = _merge_close_nodes(g, merge_px)

    comps = list(nx.connected_components(g))
    n_raw = len(comps)
    keep = [c for c in comps if len(c) >= min_component_nodes]
    if keep:
        g = g.subgraph(set().union(*keep)).copy()
    n_kept = len(keep)

    if disc_xy is not None and connect_at_root and g.number_of_nodes():
        g = _connect_at_root(g, disc_xy)

    vg = VesselGraph(
        g,
        meta={
            "n_skeleton_px": int(skel.sum()),
            "n_components_raw": n_raw,
            "n_components_kept": n_kept,
            "bridged_edges": sum(
                1 for *_, d in g.edges(data=True) if d.get("bridged")
            ),
        },
    )
    if prune_px > 0:
        vg.prune_spurs(prune_px)
    if disc_xy is not None:
        vg.root_at(disc_xy)
    return vg


#: Names of the descriptor dimensions, in order. Keep this in step with
#: :data:`cloverwarp.match.MatchParams.feature_weights` -- they are indexed
#: together, and a silent length mismatch would reweight the wrong features.
DESCRIPTOR_NAMES = (
    "depth",
    "log_radius_px",
    "n_branches",
    "sin_a1_rel",
    "cos_a1_rel",
    "sin_a2_rel",
    "cos_a2_rel",
    "log_daughter_radius_ratio",
    "path_length_frac",
    "radial_frac",
)


def bifurcation_descriptors(
    vg: VesselGraph, min_degree: int = 3, disc_xy=None
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Describe each bifurcation by properties invariant to the warp.

    Returns ``(xy, features, node_ids)`` with features named by
    :data:`DESCRIPTOR_NAMES`.

    Two invariances are load-bearing and were both learned the hard way on
    synthetic data:

    **Rotation.** Branch angles are measured *relative to the direction back
    toward the optic disc*, not in image coordinates. A petal is rotated by
    an unknown amount when it is mounted, so absolute branch angles differ
    between the petal and the FA for the same anatomical bifurcation, and a
    descriptor built on them actively misleads the matcher. Angles relative
    to the root-ward direction are unaffected.

    **Scale.** ``path_length_frac`` and ``radial_frac`` are normalised by the
    graph's own extent, so an FA at one pixel size and a confocal mosaic at
    another are comparable. ``log_radius_px`` is *not* normalised -- it stays
    in pixels and is weighted low by default. Raise its weight only once the
    two modalities' pixel sizes are matched.

    Absolute *image position* is still excluded. ``radial_frac`` -- normalised
    eccentricity from the disc -- is included, because unlike x and y it is
    rotation-invariant and genuinely comparable across the two modalities.
    Angular position is what the matcher must discover, and that is left to
    the geometric consensus step and the sector prior in
    :mod:`cloverwarp.match`.
    """
    nodes = list(vg.bifurcations(min_degree))
    n_feat = len(DESCRIPTOR_NAMES)
    if not nodes:
        return np.zeros((0, 2)), np.zeros((0, n_feat)), []

    all_xy = vg.nodes_xy
    if disc_xy is not None:
        disc = np.asarray(disc_xy, dtype=float).reshape(2)
    elif vg.root is not None:
        disc = np.asarray(vg.graph.nodes[vg.root]["xy"], dtype=float)
    else:
        disc = all_xy.mean(axis=0)

    max_path = max(
        (
            vg.graph.nodes[n].get("path_length_px", 0.0)
            for n in vg.graph.nodes
            if np.isfinite(vg.graph.nodes[n].get("path_length_px", np.inf))
        ),
        default=1.0,
    )
    if not np.isfinite(max_path) or max_path <= 0:
        max_path = 1.0
    max_radial = float(np.hypot(*(all_xy - disc).T).max()) or 1.0

    xy, feats = [], []
    for n in nodes:
        node = vg.graph.nodes[n]
        here = np.asarray(node["xy"], dtype=float)

        # direction from this node back toward the disc: the local reference
        # axis that makes the angle features rotation-invariant
        to_disc = disc - here
        ref = float(np.arctan2(to_disc[1], to_disc[0]))

        nbrs = list(vg.graph.neighbors(n))
        rel_angles, radii = [], []
        for m in nbrs:
            vec = np.asarray(vg.graph.nodes[m]["xy"], dtype=float) - here
            a = float(np.arctan2(vec[1], vec[0])) - ref
            rel_angles.append((a + np.pi) % (2 * np.pi) - np.pi)
            radii.append(float(vg.graph.edges[n, m].get("radius_px", 1.0)))

        order = np.argsort(radii)[::-1]
        a_sorted = [rel_angles[i] for i in order]
        r_sorted = [radii[i] for i in order]
        a1 = a_sorted[0] if a_sorted else 0.0
        a2 = a_sorted[1] if len(a_sorted) > 1 else 0.0
        r1 = max(r_sorted[0] if r_sorted else 1.0, 1e-6)
        r2 = max(r_sorted[1] if len(r_sorted) > 1 else r1, 1e-6)

        radial = float(np.hypot(*(here - disc))) / max_radial
        path = node.get("path_length_px", 0.0)
        path_frac = float(path / max_path) if np.isfinite(path) else -1.0

        xy.append(here)
        feats.append(
            [
                float(node.get("depth", -1)),
                float(np.log(max(node.get("radius_px", 1.0), 1e-6))),
                float(len(nbrs)),
                np.sin(a1),
                np.cos(a1),
                np.sin(a2),
                np.cos(a2),
                float(np.log(r1 / r2)),
                path_frac,
                radial,
            ]
        )
    return np.asarray(xy, dtype=float), np.asarray(feats, dtype=float), nodes
