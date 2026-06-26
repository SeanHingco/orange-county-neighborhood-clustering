"""
Post-clustering shape repair:

1. Articulation-point neck repair — splits "dumbbell" districts (two blobs
   joined by a thin neck) using graph connectivity, not signal data.
2. Topological boundary smoothing — simplifies hex-tooth edges once, on a
   shared edge network, so adjacent districts stay seam-free.

See docs/WRITEUP.md ("Cleaning up the shapes") for the reasoning.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import geopandas as gpd
from shapely.ops import unary_union, polygonize, linemerge


def repair_articulation_points(hexes: gpd.GeoDataFrame, labels: np.ndarray, hex_adjacency: dict) -> np.ndarray:
    """
    Detect and split "dumbbell"-shaped districts: districts whose internal
    hex-adjacency graph has an articulation point (a hex whose removal
    would disconnect the district into two pieces).

    Parameters
    ----------
    hexes : hex GeoDataFrame, same row order as `labels`
    labels : cluster labels from run_constrained_ward
    hex_adjacency : {hex_id: [neighbor_hex_id, ...]} — full grid adjacency
        (not cut by district membership), used to build each district's
        internal subgraph.

    Returns
    -------
    A new label array, same length as `labels`, with dumbbell districts
    split into two new label values where a repair was made.
    """
    labels = labels.copy()
    hex_ids = hexes["hex_id"].tolist()
    next_label = labels.max() + 1

    for district_id in np.unique(labels):
        member_mask = labels == district_id
        member_hexes = [h for h, m in zip(hex_ids, member_mask) if m]
        if len(member_hexes) < 3:
            continue

        g = nx.Graph()
        g.add_nodes_from(member_hexes)
        member_set = set(member_hexes)
        for h in member_hexes:
            for neighbor in hex_adjacency.get(h, []):
                if neighbor in member_set:
                    g.add_edge(h, neighbor)

        if not nx.is_connected(g):
            continue  # a different problem; not what this repair targets

        cuts = list(nx.articulation_points(g))
        if not cuts:
            continue

        # cut at the first articulation point, take the resulting components
        cut_node = cuts[0]
        g_minus = g.copy()
        g_minus.remove_node(cut_node)
        components = list(nx.connected_components(g_minus))
        if len(components) < 2:
            continue

        # reassign the smaller component(s) to a new label; the articulation
        # hex itself stays with the largest component
        components.sort(key=len, reverse=True)
        new_member_set = set()
        for comp in components[1:]:
            new_member_set |= comp

        for idx, h in enumerate(hex_ids):
            if h in new_member_set:
                labels[idx] = next_label
        next_label += 1

    return labels


def smooth_boundaries_topological(district_polygons: gpd.GeoDataFrame, tolerance: float) -> gpd.GeoDataFrame:
    """
    Simplify district boundaries via a shared-edge network, so that two
    adjacent districts simplify identically along their shared edge
    instead of independently (which leaves gaps/slivers).

    Parameters
    ----------
    district_polygons : GeoDataFrame[district_id, geometry], one polygon
        per district, in a *projected* (planar) CRS — not lat/lon — so
        that `tolerance` is in real distance units.
    tolerance : shapely simplify tolerance, same units as the CRS.

    Returns
    -------
    GeoDataFrame[district_id, geometry] with simplified, seam-free polygons.
    """
    # union all district boundaries into one shared line network
    all_boundaries = unary_union([geom.boundary for geom in district_polygons.geometry])
    merged = linemerge(all_boundaries)
    simplified = merged.simplify(tolerance, preserve_topology=True)

    # repolygonize the simplified shared-edge network
    rebuilt_polys = list(polygonize(simplified))

    # match rebuilt polygons back to district_ids by maximum overlap area
    records = []
    for district_id, original_geom in zip(district_polygons["district_id"], district_polygons.geometry):
        best_poly, best_overlap = None, 0.0
        for candidate in rebuilt_polys:
            overlap = candidate.intersection(original_geom).area
            if overlap > best_overlap:
                best_poly, best_overlap = candidate, overlap
        records.append({"district_id": district_id, "geometry": best_poly})

    return gpd.GeoDataFrame(records, crs=district_polygons.crs)
