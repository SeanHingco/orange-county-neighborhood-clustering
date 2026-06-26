"""
Spatially-constrained neighborhood clustering pipeline.

General-purpose technique code: H3 hex generation, adjacency-constrained
Ward clustering, barrier-aware connectivity, and boundary repair.

This is the public, generalized version of the technique — no
production tuning constants or proprietary signal sets included.
See docs/WRITEUP.md for the full narrative.
"""

from .hexgrid import generate_hex_grid, join_signals_to_hexes
from .connectivity import build_adjacency_graph, apply_barrier_cuts, add_barrier_side_feature
from .clustering import run_constrained_ward
from .validation import compute_purity, compute_coherence
from .repair import repair_articulation_points, smooth_boundaries_topological

__all__ = [
    "generate_hex_grid",
    "join_signals_to_hexes",
    "build_adjacency_graph",
    "apply_barrier_cuts",
    "add_barrier_side_feature",
    "run_constrained_ward",
    "compute_purity",
    "compute_coherence",
    "repair_articulation_points",
    "smooth_boundaries_topological",
]
