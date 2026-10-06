"""
Generate or load land cover data (raster or vector).

Stored as GeoDataFrame for vector data, and rioxarray DataArray for raster data.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import geopandas as gpd
import rioxarray as rxr
import xarray as xr

from seiche.utils_da import merge_clipped_rasters
from seiche.utils_enum import Landcover, LandcoverType, OutputFiles
from seiche.utils_gdf import read_sirene
from seiche.utils_qol import asinstance
from seiche.utils_state import (
    read_epsg_from_state,
    read_poly_from_state,
)


def _load_vector_lcv(  # noqa: PLR0913
    paths: list[Path],
    savepath: Path,
    epsg: int,
    poly: gpd.GeoDataFrame,
    layer: str | None = None,
    reader: Callable[[Path], gpd.GeoDataFrame] | None = None,
) -> gpd.GeoDataFrame:
    """
    Load or build a vector landcover GeoDataFrame from .shp/.gpkg files.

    Parameters
    ----------
    paths : list[Path]
        Paths to the input vector files.
    savepath : Path
        Where the clipped landcover gpkg is cached.
    epsg : int
        Output EPSG code.
    poly : gpd.GeoDataFrame
        Polygon used to clip the landcover.
    layer : str | None, optional
        Layer to read from the gpkg files, by default None.
    reader : Callable[[Path], gpd.GeoDataFrame] | None, optional
        Custom reader for non-gpkg/shp formats (e.g. Sirene csv), by default None.

    Returns
    -------
    gpd.GeoDataFrame
        The clipped landcover.

    """
    if savepath.exists():
        return asinstance(gpd.read_file(savepath), gpd.GeoDataFrame)
    if len(paths) != 1:
        msg = "FOR NOW ONLY ONE SHP PER LANDCOVER SORRY :("
        raise ValueError(msg)
    if reader is not None:
        landcover = reader(paths[0])
    elif (layer is not None) and (all(f.suffix == ".gpkg" for f in paths)):
        landcover = gpd.read_file(paths[0], layer=layer)
    else:
        landcover = gpd.read_file(paths[0])
    landcover = asinstance(landcover.to_crs(epsg=epsg).clip(poly), gpd.GeoDataFrame)
    landcover.to_file(savepath, driver="GPKG")
    return landcover


def generate_or_load_lcv(
    state: dict[str, Any],
    landcover_name: Landcover,
) -> tuple[xr.DataArray | gpd.GeoDataFrame, LandcoverType]:
    """
    See module docstring.
    """
    landcover_paths = [
        Path(state["config"]["path.inp"]) / filepath
        for filepath in state["config"][f"path.inp.lcv.{landcover_name}"]
    ]
    lcv_tif_path = OutputFiles.lcv.savepath(state, ext="tif", landcover=landcover_name)
    lcv_gpkg_path = OutputFiles.lcv.savepath(
        state,
        ext="gpkg",
        landcover=landcover_name,
    )
    epsg = read_epsg_from_state(state)
    poly = read_poly_from_state(state)

    layer = "batiment" if landcover_name is Landcover.bdtopo else None

    if all(f.suffix == ".tif" for f in landcover_paths):
        landcover_type = LandcoverType.raster
        if lcv_tif_path.exists():
            landcover = asinstance(rxr.open_rasterio(lcv_tif_path), xr.DataArray)
        else:
            landcover = merge_clipped_rasters(landcover_paths, epsg, poly)
            landcover.astype(float).rio.to_raster(lcv_tif_path)
    elif all(f.suffix == ".shp" for f in landcover_paths) or all(
        f.suffix == ".gpkg" for f in landcover_paths
    ):
        landcover_type = LandcoverType.vector
        landcover = _load_vector_lcv(
            landcover_paths,
            lcv_gpkg_path,
            epsg,
            poly,
            layer,
        )
    elif landcover_name is Landcover.sirene:
        landcover_type = LandcoverType.vector
        landcover = _load_vector_lcv(
            landcover_paths,
            lcv_gpkg_path,
            epsg,
            poly,
            reader=lambda p: read_sirene(p, epsg=epsg),
        )
    else:
        msg = (
            "Wrong landcover file type (only .shp, .gpkg or .tif for now) "
            "or non consistent file types in list"
        )
        raise ValueError(
            msg,
        )
    return landcover, landcover_type
