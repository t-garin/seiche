"""
Contains utility functions for working with GeoDataFrames.
"""

import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import xarray as xr
from exactextract import exact_extract

from seiche.utils_enum import HazardBand
from seiche.utils_qol import asinstance


def streamline(
    landcover: gpd.GeoDataFrame,
    col2keep: str,
    newcol: str = "class",
) -> gpd.GeoDataFrame:
    """
    Streamline a GeoDataFrame to one column (renamed 'class') plus geometry.

    Parameters
    ----------
    landcover : gpd.GeoDataFrame
        Input GeoDataFrame with multiple columns.

    col2keep : str
        Name of the column to keep (besides geometry).

    newcol : str, default: "class"
        New name for the kept column.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with only 'geometry' and 'class' columns.

    """
    landcover = asinstance(landcover[["geometry", col2keep]].copy(), gpd.GeoDataFrame)
    landcover.columns = ["geometry", newcol]
    try:
        # if landcover class are stored as int
        landcover[newcol] = [int(elem) for elem in landcover[newcol]]
    except ValueError:
        # otherwise convert to string (should work on np.nan / pd.NA too)
        landcover[newcol] = [str(elem) for elem in landcover[newcol]]
    return landcover


def concat_hazard(
    landcover: gpd.GeoDataFrame,
    hazard: xr.DataArray,
    *,
    use_max_depth: bool = True,
    use_max_speed: bool = True,
    use_duration: bool = True,
) -> gpd.GeoDataFrame:
    """
    Concatenate hazard values from a raster DataArray to a GeoDataFrame as a new column.

    Parameters
    ----------
    landcover : gpd.GeoDataFrame
        Input GeoDataFrame to which hazard values will be added.

    hazard : xr.DataArray
        3-band raster (e.g., max_depth, max_speed, duration) to extract hazard
        values from.

    use_max_depth : bool, default: True
        Whether to include max_depth in the hazard values. Default is True.

    use_max_speed : bool, default: True
        Whether to include max_speed in the hazard values. Default is True.

    use_duration : bool, default: True
        Whether to include duration in the hazard values. Default is True.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with an added hazard column.

    """
    if hazard.rio.crs.to_epsg() != landcover.crs.to_epsg():
        msg = "hazard and landcover CRS must match"
        raise ValueError(msg)

    to_concat = {
        HazardBand.max_depth: use_max_depth,
        HazardBand.max_speed: use_max_speed,
        HazardBand.duration: use_duration,
    }

    bands_to_concat = [band.band_index for band, use in to_concat.items() if use]
    names_to_concat = [band for band, use in to_concat.items() if use]

    rasters = (
        hazard.isel(band=bands_to_concat)
        .assign_coords(band=names_to_concat)
        .to_dataset(dim="band")
    )

    # exact_extract is much faster reading a raster file than an in-memory xarray
    # (GDAL block cache + no per-feature array re-materialization), so write it to
    # a temporary GeoTIFF first.
    with tempfile.NamedTemporaryFile(suffix=".tif") as f:
        rasters.rio.to_raster(f.name)
        extracted = exact_extract(f.name, landcover, ops="mean", output="pandas")

    extracted.columns = names_to_concat
    extracted.index = landcover.index
    return gpd.GeoDataFrame(pd.concat([landcover, extracted], axis=1))


def read_sirene(sirene_path: str | Path, epsg: int = 2154) -> gpd.GeoDataFrame:
    """
    Read Sirène file and format it as a GeoDataFrame.
    """
    sirene = pd.read_csv(sirene_path, low_memory=False)
    sirene = gpd.GeoDataFrame(
        sirene,
        geometry=gpd.points_from_xy(sirene.longitude, sirene.latitude),
        crs="EPSG:4326",
    )
    return sirene.to_crs(epsg=epsg)


def find_column(dataframe: pd.DataFrame | gpd.GeoDataFrame, *candidates: str) -> str:
    """
    Find the first matching column from candidates, or raise a ValueError.

    Useful for some databases where the formating is not always consistent between
    versions.
    For example, BDTopo sometimes has a "USAGE_1" col that is written "usage_1".
    """
    col = next((c for c in candidates if c in dataframe.columns), None)
    if col is None:
        msg = f"None of {candidates} found in columns"
        raise ValueError(msg)
    return col
