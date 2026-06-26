"""
Purity / coherence validation against a published ground-truth
neighborhood boundary set.

See docs/WRITEUP.md ("Picking the number of clusters, and the tradeoff
that creates") for what these metrics mean and why they trade off
against each other.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd


def _area_overlap_table(predicted: gpd.GeoDataFrame, ground_truth: gpd.GeoDataFrame) -> pd.DataFrame:
    """Intersection area between every predicted district and every ground-truth neighborhood."""
    overlay = gpd.overlay(
        predicted[["district_id", "geometry"]],
        ground_truth[["neighborhood_id", "geometry"]],
        how="intersection",
    )
    overlay["overlap_area"] = overlay.geometry.area
    return overlay


def compute_purity(predicted: gpd.GeoDataFrame, ground_truth: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    For each ground-truth neighborhood, what fraction of its area falls
    inside a single predicted district (its best-matching one)?

    Low purity = that neighborhood got fragmented across multiple
    predicted districts.

    Returns
    -------
    DataFrame[neighborhood_id, purity, best_matching_district_id]
    """
    overlay = _area_overlap_table(predicted, ground_truth)
    truth_total = ground_truth.assign(_total_area=ground_truth.geometry.area)[["neighborhood_id", "_total_area"]]

    best = overlay.loc[overlay.groupby("neighborhood_id")["overlap_area"].idxmax()]
    result = best.merge(truth_total, on="neighborhood_id")
    result["purity"] = result["overlap_area"] / result["_total_area"]
    return result[["neighborhood_id", "purity", "district_id"]].rename(
        columns={"district_id": "best_matching_district_id"}
    )


def compute_coherence(predicted: gpd.GeoDataFrame, ground_truth: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    For each predicted district, what fraction of its area belongs to a
    single ground-truth neighborhood (its best-matching one)?

    Low coherence = that district absorbed multiple distinct real
    neighborhoods into one blob.

    Returns
    -------
    DataFrame[district_id, coherence, best_matching_neighborhood_id,
              n_neighborhoods_touched]
    """
    overlay = _area_overlap_table(predicted, ground_truth)
    pred_total = predicted.assign(_total_area=predicted.geometry.area)[["district_id", "_total_area"]]

    best = overlay.loc[overlay.groupby("district_id")["overlap_area"].idxmax()]
    touched_counts = overlay.groupby("district_id")["neighborhood_id"].nunique().rename("n_neighborhoods_touched")

    result = best.merge(pred_total, on="district_id").merge(touched_counts, on="district_id")
    result["coherence"] = result["overlap_area"] / result["_total_area"]
    return result[["district_id", "coherence", "neighborhood_id", "n_neighborhoods_touched"]].rename(
        columns={"neighborhood_id": "best_matching_neighborhood_id"}
    )
