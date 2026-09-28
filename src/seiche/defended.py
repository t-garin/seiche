"""
Depths Estimation from a Flood Extent aNd Digital Elevation Data.
"""

import tempfile
from pathlib import Path

import numpy as np
import xarray as xr
from pysheds.grid import Grid
from rasterio.enums import Resampling
from scipy import ndimage
from scipy.ndimage import binary_closing

from seiche.utils_da import da_from_array
from seiche.utils_enum import DefendedMethod, SimpleMethod
from seiche.utils_qol import asinstance

DEFAULT_HAND_THRESHOLD = 100  # pysheds example, see _compute_hand


def simple(
    dem: np.ndarray,
    wet_mask: np.ndarray,
    method: SimpleMethod,
) -> np.ndarray:
    """
    Estimate water depth using a simple method based on DEM and flood extent mask.

    Parameters
    ----------
    dem : np.ndarray
        Digital Elevation Model (DEM) as a 2D numpy array.

    wet_mask : np.ndarray
        Boolean or binary mask array where flooded pixels are True/1.

    method : SimpleMethod
        Method to use for estimation:
            - 'all': Use the global maximum water surface elevation.
            - 'each': Use the maximum per connected group of flooded pixels.

    Returns
    -------
    np.ndarray
        Estimated water depth per pixel (same shape as dem).

    """
    # Finding maximum water depth ...
    match method:
        # ... among ALL the groups (== on the global extent)
        case SimpleMethod.all:
            max_wet_dem = np.nanmax(wet_mask * dem)
            water_depth = max_wet_dem - dem

        # ... among EACH group
        case SimpleMethod.each:
            # Group the flood extent into groups of connected water (see ndimage.label)
            structure = np.ones((3, 3))
            groups, num_ids = ndimage.label(wet_mask, structure=structure)
            group_ids = np.arange(0, num_ids + 1)
            # get the maximum per group using ndimage.maximum
            groups_max = ndimage.maximum(dem, groups, group_ids)
            water_depth = groups_max[groups] - dem

    return water_depth


def fwdet(dem: xr.DataArray, wet_mask: xr.DataArray, method: str) -> np.ndarray:
    """
    Estimate water depth using the FwDET (Floodwater Depth Estimation Tool) algorithm.

    Main steps:
        1. Extract the grid cells on the outline of the inundation extent.
        2. Extract DEM values for these boundary cells.
        3. Interpolate the floodwater elevation from the boundary cells.
        4. Calculate floodwater depth by subtracting DEM from interpolated surface.

    Parameters
    ----------
    dem : xr.DataArray
        DEM as a xr.DataArray.

    wet_mask : xr.DataArray
        Boolean mask for flooded pixels.

    method : str
        Interpolation method ('nearest', 'linear', 'cubic').

    Returns
    -------
    np.ndarray
        Estimated water depth per pixel (same shape as dem).

    """

    def _extract_boundary(wet: np.ndarray) -> np.ndarray:
        """
        Extract the boundary of flooded area from wet mask.

        Substract the eroded wet mask from the original wet mask.
        """
        return wet - ndimage.binary_erosion(
            input=wet,
            structure=np.ones((3, 3)),
            mask=wet,
        )

    # 1. Extract boundary
    boundary = da_from_array(
        [_extract_boundary(wet_mask.isel(band=0).values)],
        wet_mask,
    )
    # 2. Extract DEM
    border_dem = dem.rio.reproject_match(wet_mask).where(boundary)
    # 3. Interpolate Free Surface
    freesurf = border_dem.rio.interpolate_na(method).where(wet_mask)
    # 4. Reproject freesurf to the dem resolution for subtraction.
    #    Here we up-sample, so beware of which Resampling is used.
    freesurf = freesurf.rio.reproject_match(dem, resampling=Resampling.average)
    # 5. Substract DEM to freesurf
    return (freesurf - dem).isel(band=0).values


def hand(
    dem: xr.DataArray,
    wet_mask: np.ndarray,
    method: SimpleMethod,
    thresh: float | None = None,
) -> np.ndarray:
    """
    Estimate water depth using the HAND (Height Above Nearest Drainage) approach.

    Parameters
    ----------
    dem : xr.DataArray
        Digital Elevation Model (DEM).

    wet_mask : np.ndarray
        Boolean or binary mask for flooded pixels.

    method : SimpleMethod
        Method for water depth estimation ('all' or 'each').

    thresh : float | int | None, default: None
        Accumulation threshold for HAND computation.
        If None, DEFAULT_HAND_THRESHOLD is used.

    Returns
    -------
    np.ndarray
        Estimated water depth per pixel (same shape as DEM).

    """

    def _compute_hand(dem_path: str, thresh: float) -> np.ndarray:
        # https://mattbartos.com/pysheds/hand.html
        # Instantiate grid from raster
        grid = Grid.from_raster(dem_path)
        dem = grid.read_raster(dem_path)
        # Clean dem
        dem = grid.fill_pits(dem)
        dem = grid.fill_depressions(dem)
        dem = grid.resolve_flats(dem)
        # Compute flow directions, accumulation and height above nearest drainage
        fdir = grid.flowdir(dem)
        acc = grid.accumulation(fdir)
        hand = grid.compute_hand(fdir, dem, acc > thresh)
        # return np.array instead of pysheds.Raster
        return np.array(hand.tolist())

    thresh = DEFAULT_HAND_THRESHOLD if thresh is None else thresh
    # pysheds reads a raster file, so write the DEM to a temporary file
    with tempfile.TemporaryDirectory() as tmpdir:
        dem_path = Path(tmpdir) / "dem.tif"
        # pysheds warns when no nodata is declared and defaults to 0
        nodata = 0 if dem.rio.nodata is None else dem.rio.nodata
        dem = asinstance(dem.rio.write_nodata(nodata), xr.DataArray)
        dem.rio.to_raster(dem_path)
        hand = _compute_hand(str(dem_path), thresh)
    hand[np.isnan(hand)] = 0
    return simple(dem=hand, wet_mask=wet_mask, method=method)


def defended(
    method: DefendedMethod,
    bfm: xr.DataArray,  # | str
    dem: xr.DataArray,  # | str
    hand_threshold: float | None = None,
) -> xr.DataArray:
    """
    Return a water depth estimation from a BFM and DEM.

    Parameters
    ----------
    method : DefendedMethod
        Estimation method: 'simple_a', 'simple_e', 'fwdet_n', 'fwdet_l',
        'fwdet_c', 'hand_a' or 'hand_e'.
    bfm : str | xr.DataArray
        Flood extent map (file path or DataArray).

    dem : str | xr.DataArray
        DEM (file path or DataArray).

    hand_threshold : float | int | None, default: None
        Accumulation threshold for HAND method.
        If None, DEFAULT_HAND_THRESHOLD is used.

    Returns
    -------
    xr.DataArray
        Estimated water depth per pixel (3D array, same shape as DEM).

    """
    # since 0 where added before, we remove them here
    # see function main_hazards.generate_hazard_from_bands
    # i don't like this, i don't have time, i have a phd to finish
    bfm = bfm.where(dem.rio.reproject_match(bfm).notnull(), other=np.nan)
    wet_mask = (bfm == 1).astype(int)

    # Do 1 iteration of binary_closing to the mask (dilation then erosion)
    # to remove small holes that lead to interpolation nasties
    wet_mask = wet_mask.copy(
        data=[
            binary_closing(wet_mask.values[0], structure=np.ones((3, 3)), iterations=1),
        ],
    ).astype(int)

    def to_array(x: xr.DataArray) -> np.ndarray:
        return x.isel(band=0).values

    match method:
        case DefendedMethod.simple_a | DefendedMethod.simple_e:
            wde = simple(
                dem=to_array(dem),
                wet_mask=to_array(wet_mask.rio.reproject_match(dem)),
                method=(
                    SimpleMethod.all
                    if method is DefendedMethod.simple_a
                    else SimpleMethod.each
                ),
            )
        case DefendedMethod.fwdet_n:
            wde = fwdet(
                dem=dem,
                wet_mask=wet_mask,
                method="nearest",
            )
        case DefendedMethod.fwdet_l:
            wde = fwdet(
                dem=dem,
                wet_mask=wet_mask,
                method="linear",
            )
        case DefendedMethod.fwdet_c:
            wde = fwdet(
                dem=dem,
                wet_mask=wet_mask,
                method="cubic",
            )
        case DefendedMethod.hand_a | DefendedMethod.hand_e:
            wde = hand(
                dem=dem,
                wet_mask=to_array(wet_mask.rio.reproject_match(dem)),
                method=(
                    SimpleMethod.all
                    if method is DefendedMethod.hand_a
                    else SimpleMethod.each
                ),
                thresh=hand_threshold,
            )

    wde[wde < 0] = 0  # clip the values to be >= 0
    wde[~to_array(wet_mask.rio.reproject_match(dem).astype(bool))] = (
        np.nan
    )  # put to nan if not wet
    return da_from_array([wde], dem)
