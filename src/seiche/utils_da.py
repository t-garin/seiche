"""
Contains functions for handling xarray DataArrays.
"""

import json
import logging
from math import ceil
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio.transform
import rioxarray as rxr
import rioxarray.exceptions
import xarray as xr
from pyproj import CRS
from rioxarray.merge import merge_arrays

from seiche.utils_qol import asinstance

logger = logging.getLogger(__name__)


def reproj_clip(
    da: xr.DataArray,
    epsg: int,
    poly: gpd.GeoDataFrame,
    *,
    pad: bool = True,
) -> xr.DataArray | None:
    """
    Clip and reproject a DataArray to a polygon's bounding box and EPSG code.

    Parameters
    ----------
    da : xr.DataArray
        Input DataArray to be clipped and reprojected.

    epsg : int
        EPSG code for target projection.

    poly : gpd.GeoDataFrame
        Polygon(s) for clipping and reprojection.

    pad : bool
        Wether or not to pad the clipped data to the full extent of POLY.

    Returns
    -------
    xr.DataArray
        Clipped and reprojected DataArray.

    """
    clipper = poly.to_crs(epsg=da.rio.crs.to_epsg())
    # an integer raster without a declared nodata would otherwise produce NaN
    # out-of-extent cells that trigger an "invalid value encountered in cast"
    if da.rio.nodata is None and np.issubdtype(da.dtype, np.integer):
        da = asinstance(da.rio.write_nodata(0), xr.DataArray)
    try:
        newda = (
            da.rio.clip_box(*clipper.total_bounds)
            .rio.clip(clipper.geometry.values)
            .rio.reproject(f"EPSG:{epsg}")
        )
    except rxr.exceptions.NoDataInBounds:
        logger.debug("reproj_clip -> rxr.NoDataInBounds")
        return None
    else:
        if pad:
            newda = newda.rio.pad_xy(*poly.total_bounds)
        return asinstance(newda, xr.DataArray)


def merge_clipped_rasters(
    paths: list[str],
    epsg: int,
    poly: gpd.GeoDataFrame,
) -> xr.DataArray:
    """
    Reproject and clip multiple raster files, returning a single DataArray.

    Parameters
    ----------
    paths : list[str]
        List of file paths to raster files.

    epsg : int
        EPSG code for target projection.

    poly : gpd.GeoDataFrame
        Polygon(s) for clipping and reprojection.

    Returns
    -------
    xr.DataArray
        Merged, clipped, and reprojected DataArray.

    """
    arrays = [
        reproj_clip(
            asinstance(rxr.open_rasterio(path), xr.DataArray), epsg=epsg, poly=poly
        )
        for path in paths
    ]
    # reproj clip returns None if no data in range
    return merge_arrays([a for a in arrays if a is not None])


def read_netcdf(filepath: str | Path) -> xr.Dataset:
    """
    Load a precompiled netCDF, restoring the JSON-serialized units dict.

    Parameters
    ----------
    filepath : str
        Path to the netCDF file.

    Returns
    -------
    xr.Dataset
        The loaded dataset, with the units attr restored to a dict.

    """
    ds = xr.open_dataset(filepath)
    if "units" in ds.attrs:
        ds.attrs["units"] = json.loads(ds.attrs["units"])
    return ds


def da_from_array(
    array: np.ndarray | list[np.ndarray], other_da: xr.DataArray
) -> xr.DataArray:
    """
    Create a DataArray from a numpy array using another's coordinates/dimensions.

    Parameters
    ----------
    array : np.array
        Numpy array to convert.

    other_da : xr.DataArray
        DataArray to copy coordinates and dimensions from.

    Returns
    -------
    xr.DataArray
        New DataArray with same coords/dims as other_da.

    """
    return xr.DataArray(array, coords=other_da.coords, dims=other_da.dims)


def empty_copy_from_da(da: xr.DataArray) -> xr.DataArray:
    """
    Return a copy of the da with all values set to np.nan.
    """
    return da.copy(data=np.full_like(da.values, fill_value=np.nan))


def generate_empty_da_from_bounds(
    bounds: tuple[float, float, float, float],
    pixel_size: float,
    epsg: int,
    n_bands: int = 1,
) -> xr.DataArray:
    """
    Generate an empty regular xr.DataArray raster aligned to an extent.

    The grid is raster-aligned to the bounds using rasterio.transform.from_bounds.
    The x and y coords hold the cell centers (not the edges), so e.g. bounds
    (0, 0, 100, 100) with pixel_size 10 yield x from 5 to 95 and y from 95 to 5.

    Parameters
    ----------
    bounds : tuple
        (west, south, east, north).
    pixel_size : int | float
        Pixel size in meters.
    epsg : int
        EPSG code of the output CRS.
    n_bands : int, default: 1
        Number of bands in the output raster.

    Returns
    -------
    xr.DataArray
        Empty float32 raster with a band dim and proper rio transform/CRS.

    """
    crs = CRS.from_epsg(epsg)
    axis_unit = crs.axis_info[0].unit_name
    if axis_unit != "metre":
        msg = (
            f"EPSG:{epsg} uses '{axis_unit}' units, but only meters are supported. "
            f"Ensure pixel_size is in meters."
        )
        raise ValueError(
            msg,
        )

    w, s, e, n = bounds
    n_y_pixels = ceil((n - s) / pixel_size)
    n_x_pixels = ceil((e - w) / pixel_size)
    transform = rasterio.transform.from_bounds(
        w,
        s,
        e,
        n,
        width=n_x_pixels,
        height=n_y_pixels,
    )
    x, _ = rasterio.transform.xy(
        transform,
        np.arange(n_x_pixels),
        np.arange(n_x_pixels),
    )
    _, y = rasterio.transform.xy(
        transform,
        np.arange(n_y_pixels),
        np.arange(n_y_pixels),
    )
    da = xr.DataArray(
        np.zeros((n_bands, n_y_pixels, n_x_pixels), dtype="float32"),
        dims=("band", "y", "x"),
        coords={"x": x, "y": y, "band": np.arange(1, n_bands + 1)},
    )
    return asinstance(
        da.rio.write_transform(transform).rio.write_crs(epsg), xr.DataArray
    )
