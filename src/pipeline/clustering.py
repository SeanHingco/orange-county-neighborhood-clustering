"""
Spatially-constrained Ward agglomerative clustering.

Thin, documented wrapper around sklearn's AgglomerativeClustering —
the substance of the technique is in how the connectivity matrix and
feature matrix are constructed (see connectivity.py and hexgrid.py),
not in the clustering call itself.
"""

from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.cluster import AgglomerativeClustering
from sklearn.preprocessing import RobustScaler


def run_constrained_ward(
    features: np.ndarray,
    adjacency: csr_matrix,
    n_clusters: int,
    scale: bool = True,
) -> np.ndarray:
    """
    Run Ward agglomerative clustering constrained to the given adjacency graph.

    Parameters
    ----------
    features : (n_hexes, n_signals) array of signal values per hex.
        Should already include any engineered features (e.g. barrier-side
        signed distance) as additional columns.
    adjacency : output of build_adjacency_graph / apply_barrier_cuts.
        Hexes can only be merged directly if connected in this graph.
    n_clusters : target number of districts. See docs/WRITEUP.md for the
        purity/coherence tradeoff this choice creates.
    scale : if True, apply RobustScaler (median/IQR) before clustering.
        Recommended — Ward clustering is distance-based and sensitive to
        feature scale; RobustScaler is used over StandardScaler because
        demographic/economic signals are frequently long-tailed.

    Returns
    -------
    1D int array of cluster labels, length n_hexes.
    """
    X = RobustScaler().fit_transform(features) if scale else features

    model = AgglomerativeClustering(
        n_clusters=n_clusters,
        connectivity=adjacency,
        linkage="ward",
    )
    return model.fit_predict(X)
