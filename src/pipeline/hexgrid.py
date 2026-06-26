"""
H3 hex grid generation and spatial signal joining.

Tiles a region of interest into H3 hexagons at a given resolution,
and joins external signal data (e.g. Census block groups, point-based
amenity counts) onto that grid by spatial overlap.
"""

from __future__ import annotations

import geopandas as gpd
import h3
import pandas as pd
from shapely.geometry import Polygon


def generate_hex_grid(boundary: gpd.GeoSeries | Polygon, resolution: int = 9) -> gpd.GeoDataFrame:
    """
    Tile a region boundary into H3 hexagons at the given resolution.

    Parameters
    ----------
    boundary : a single (multi)polygon, or a GeoSeries that will be unioned,
        in EPSG:4326.
    resolution : H3 resolution. 8-9 is a reasonable range for
        neighborhood-scale clustering; higher resolutions produce more,
        smaller hexes and increase sparse-data coverage problems.

    Returns
    -------
    GeoDataFrame with columns [hex_id, geometry], one row per hex,
    geometry as hexagon polygons in EPSG:4326.
    """
    if isinstance(boundary, gpd.GeoSeries):
        geom = boundary.union_all()
    else:
        geom = boundary

    # h3.polygon_to_cells expects (lat, lng) ordered LatLngPoly input
    geo_json_like = {
        "type": "Polygon",
        "coordinates": [[(y, x) for x, y in geom.exterior.coords]],
    }
    hex_ids = h3.geo_to_cells(geo_json_like, resolution) if hasattr(h3, "geo_to_cells") else h3.polygon_to_cells(
        h3.LatLngPoly([(y, x) for x, y in geom.exterior.coords]), resolution
    )

    records = []
    for hex_id in hex_ids:
        boundary_coords = h3.cell_to_boundary(hex_id)
        # h3 returns (lat, lng); shapely wants (lng, lat)
        poly = Polygon([(lng, lat) for lat, lng in boundary_coords])
        records.append({"hex_id": hex_id, "geometry": poly})

    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def join_signals_to_hexes(
    hexes: gpd.GeoDataFrame,
    signal_source: gpd.GeoDataFrame,
    signal_columns: list[str],
    method: str = "area_weighted",
) -> gpd.GeoDataFrame:
    """
    Join polygon-based signal data (e.g. Census block groups) onto a hex grid.

    Parameters
    ----------
    hexes : output of generate_hex_grid
    signal_source : polygons carrying the signal columns (e.g. ACS block groups)
    signal_columns : which columns from signal_source to bring over
    method : "area_weighted" apportions each signal value across overlapping
        hexes by intersection area share; "centroid" assigns each hex the
        value of whichever source polygon contains its centroid (faster,
        less precise for hexes straddling a source boundary).

    Returns
    -------
    hexes GeoDataFrame with signal_columns appended.
    """
    hexes = hexes.copy()

    if method == "centroid":
        centroids = hexes.copy()
        centroids["geometry"] = centroids.geometry.centroid
        joined = gpd.sjoin(centroids, signal_source[signal_columns + ["geometry"]], how="left", predicate="within")
        for col in signal_columns:
            hexes[col] = joined[col].values
        return hexes

    if method == "area_weighted":
        overlay = gpd.overlay(hexes, signal_source[signal_columns + ["geometry"]], how="intersection")
        overlay["_area"] = overlay.geometry.area
        # area-weighted mean per hex_id across all intersecting source polygons
        agg = (
            overlay.groupby("hex_id")
            .apply(lambda g: pd.Series({col: (g[col] * g["_area"]).sum() / g["_area"].sum() for col in signal_columns}))
            .reset_index()
        )
        hexes = hexes.merge(agg, on="hex_id", how="left")
        return hexes

    raise ValueError(f"Unknown join method: {method}")
