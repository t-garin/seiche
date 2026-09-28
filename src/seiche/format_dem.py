"""
Generate or load a DEM as a rioxarray DataArray.
"""

from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import rioxarray as rxr
import xarray as xr
from rioxarray.merge import merge_arrays

from seiche.utils_da import reproj_clip
from seiche.utils_enum import OutputFiles
from seiche.utils_qol import asinstance
from seiche.utils_state import (
    read_epsg_from_state,
    read_poly_from_state,
)


def generate_dem_from_tifs(
    filepaths: list[Path],
    epsg: int,
    poly: gpd.GeoDataFrame,
) -> xr.DataArray:
    """
    Generate a DEM from a list of GeoTIFF filepaths.
    """
    arrays = [
        reproj_clip(asinstance(rxr.open_rasterio(path), xr.DataArray), epsg, poly)
        for path in filepaths
    ]
    return asinstance(
        merge_arrays([a for a in arrays if a is not None])
        .astype(float)
        .rio.write_nodata(np.nan),
        xr.DataArray,
    )


def generate_dem_from_ascs(
    filepaths: list[Path],
    dem_epsg: int,
    epsg: int,
    poly: gpd.GeoDataFrame,
) -> xr.DataArray:
    """
    Generate a DEM from a list of ASCII grid filepaths.
    """
    arrays = []
    for path in filepaths:
        array = asinstance(rxr.open_rasterio(path, masked=True), xr.DataArray)
        # dem_epsg is the EPSG code of the input ASCII grids
        # since it is not stored in the file itself
        array = array.rio.write_crs(f"EPSG:{dem_epsg}")
        array = reproj_clip(array, epsg, poly, pad=False)
        if array is not None:
            arrays.append(array)
    return asinstance(
        merge_arrays(arrays).astype(float).rio.write_nodata(np.nan), xr.DataArray
    )


def generate_or_load_dem(state: dict[str, Any]) -> dict[str, Any]:
    """
    Generate or load the DEM and store its path in the state.
    """
    dem_savepath = OutputFiles.dem.savepath(state)
    if not dem_savepath.exists():
        epsg = read_epsg_from_state(state)
        poly = read_poly_from_state(state)
        root = Path(state["config"]["path.inp"]) / state["config"]["path.inp.dem.root"]
        filter_key = state["config"]["path.inp.dem.filter_key"]
        paths = [
            path
            for path in root.rglob("*")
            if path.is_file()
            and (path.suffix in (".tif", ".asc"))
            and (filter_key in path.name)
        ]
        if all(f.suffix == ".tif" for f in paths):
            dem = generate_dem_from_tifs(
                filepaths=paths,
                epsg=epsg,
                poly=poly,
            )
        elif all(f.suffix == ".asc" for f in paths):
            dem = generate_dem_from_ascs(
                filepaths=paths,
                dem_epsg=state["config"]["path.inp.dem.EPSG"],
                epsg=epsg,
                poly=poly,
            )
        else:
            msg = "DEM files must all end with .tif or .asc"
            raise ValueError(msg)
        dem.rio.to_raster(dem_savepath)
    else:
        dem = asinstance(rxr.open_rasterio(dem_savepath), xr.DataArray)
    del dem
    dem_path = OutputFiles.dem.savepath(state)
    return {**state, "dem": {"path": dem_path}}
