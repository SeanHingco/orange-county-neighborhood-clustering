"""
Spatial adjacency graph construction, with support for cutting connectivity
across physical barriers (highways, rivers, rail) and injecting a
signed barrier-side feature into the signal space.
"""

from __future__ import annotations

import h3
import numpy as np
import geopandas as gpd
from scipy.sparse import lil_matrix, csr_matrix
from shapely.geometry import LineString
from shapely.strtree import STRtree


def build_adjacency_graph(hexes: gpd.GeoDataFrame) -> csr_matrix:
    """
    Build a sparse adjacency matrix from H3 hex-grid adjacency.

    Two hexes are connected iff they are H3 grid-neighbors. This is the
    connectivity matrix passed to sklearn's AgglomerativeClustering to
    constrain merges to geographically adjacent units.

    Returns
    -------
    scipy.sparse.csr_matrix, shape (n_hexes, n_hexes)
    """
    hex_ids = hexes["hex_id"].tolist()
    index_of = {h: i for i, h in enumerate(hex_ids)}
    n = len(hex_ids)
    adj = lil_matrix((n, n), dtype=np.int8)

    for i, hex_id in enumerate(hex_ids):
        for neighbor in h3.grid_disk(hex_id, 1):
            if neighbor == hex_id:
                continue
            j = index_of.get(neighbor)
            if j is not None:
                adj[i, j] = 1
                adj[j, i] = 1

    return adj.tocsr()


def apply_barrier_cuts(
    adjacency: csr_matrix,
    hexes: gpd.GeoDataFrame,
    barriers: gpd.GeoDataFrame,
) -> csr_matrix:
    """
    Remove adjacency edges between hexes whose connecting line crosses
    a physical barrier (e.g. a freeway or river centerline).

    Parameters
    ----------
    adjacency : output of build_adjacency_graph
    hexes : the same hex GeoDataFrame used to build `adjacency`, same row order
    barriers : LineString geometries representing barrier features

    Returns
    -------
    A new csr_matrix with barrier-crossing edges removed.
    """
    barrier_lines = list(barriers.geometry)
    tree = STRtree(barrier_lines)

    centroids = hexes.geometry.centroid.values
    adj = adjacency.tolil()
    rows, cols = adjacency.nonzero()

    for i, j in zip(rows, cols):
        if i >= j:
            continue  # symmetric matrix, only need to check each pair once
        edge = LineString([centroids[i], centroids[j]])
        # query returns candidate barrier indices whose bounding box intersects `edge`
        candidate_idxs = tree.query(edge)
        crosses = any(edge.crosses(barrier_lines[k]) for k in candidate_idxs)
        if crosses:
            adj[i, j] = 0
            adj[j, i] = 0

    return adj.tocsr()


def add_barrier_side_feature(
    hexes: gpd.GeoDataFrame,
    barriers: gpd.GeoDataFrame,
) -> np.ndarray:
    """
    Compute, for each hex centroid, a signed perpendicular distance to the
    nearest barrier line. This gives clustering a real numeric reason to
    separate hexes that sit on opposite sides of a barrier even when their
    other signals are identical.

    Returns
    -------
    1D array, one signed distance value per hex (same row order as `hexes`),
    suitable for appending as an extra column to the clustering feature matrix.
    """
    barrier_lines = list(barriers.geometry)
    tree = STRtree(barrier_lines)
    centroids = hexes.geometry.centroid.values

    signed_distances = np.zeros(len(centroids))
    for idx, pt in enumerate(centroids):
        nearest_idx = tree.nearest(pt)
        nearest_line = barrier_lines[nearest_idx]
        # project point onto line, use cross-product sign of the tangent
        # direction at the nearest point to determine which side pt is on
        nearest_pt_on_line = nearest_line.interpolate(nearest_line.project(pt))
        dist = pt.distance(nearest_line)

        # local tangent direction via a small step along the line
        proj_dist = nearest_line.project(pt)
        eps = 1e-6
        p1 = nearest_line.interpolate(max(proj_dist - eps, 0))
        p2 = nearest_line.interpolate(min(proj_dist + eps, nearest_line.length))
        tangent = np.array([p2.x - p1.x, p2.y - p1.y])
        to_point = np.array([pt.x - nearest_pt_on_line.x, pt.y - nearest_pt_on_line.y])
        cross = tangent[0] * to_point[1] - tangent[1] * to_point[0]
        sign = 1.0 if cross >= 0 else -1.0

        signed_distances[idx] = sign * dist

    return signed_distances
