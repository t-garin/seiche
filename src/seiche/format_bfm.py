"""
Extracts data from BFMs, uses DEFENDED, formats everyting in xr.DataArray.
"""

import logging
import re
from collections.abc import Iterator
from functools import reduce
from itertools import compress
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import numpy.typing as npt
import pandas as pd
import rioxarray as rxr
import xarray as xr
from rioxarray.merge import merge_arrays

from seiche.defended import defended
from seiche.utils_da import (
    empty_copy_from_da,
    generate_empty_da_from_bounds,
    reproj_clip,
)
from seiche.utils_enum import DefendedMethod
from seiche.utils_geom import bbox_union
from seiche.utils_qol import asinstance
from seiche.utils_state import (
    read_epsg_from_state,
    read_expname_from_state,
    read_poly_from_state,
)

logger = logging.getLogger(__name__)

BFM_NO_DATA_6 = 6
BFM_NO_DATA_7 = 7


def get_bfms_paths_n_dates(
    state: dict[str, Any],
) -> list[tuple[str, pd.Timestamp]]:
    """
    Get all BFM paths and dates from config file.
    """
    root = Path(state["config"]["path.inp"]) / state["config"]["path.inp.bfm.root"]
    regex = state["config"]["path.inp.bfm.regex"]
    filter_key = state["config"]["path.inp.bfm.filter_key"]
    files2ignore_path = state["config"]["path.inp.bfm.files2ignore"]

    # read txt file containing files2ignore
    files2ignore = []
    if (files2ignore_path is not None) and (files2ignore_path != ""):
        with Path(files2ignore_path).open() as f:
            files2ignore = [line.strip() for line in f if line.strip()]

    # recursively find filepaths, only keep .tif and those that match filterKey
    all_files_in_dir = [
        file
        for file in root.rglob("*")
        if file.is_file()
        # if it is a .tif file
        and (file.suffix == ".tif")
        # if it contains filter key
        and (filter_key in file.name)
        # if it is not to be ignored
        and (file.name not in files2ignore)
    ]
    # sort so the merge order (and therefore the outputs) is deterministic
    all_files_in_dir = sorted(all_files_in_dir, key=str)
    return [
        (
            str(filepath),
            pd.to_datetime(re.search(regex, filepath.name).group()),
        )
        for filepath in all_files_in_dir
    ]


def generate_bfms_netcdfs(state: dict[str, Any]) -> str:
    """
    Convert FloodML outputs (geotiff) to individual .nc, return savedir.
    """
    expname = read_expname_from_state(state)
    savedir = Path(state["config"]["path.out"]) / "bfm"
    savedir.mkdir(parents=True, exist_ok=True)

    # Group BFMs by date
    grouped_bfms = {}
    for path, datetime in get_bfms_paths_n_dates(state):
        grouped_bfms.setdefault(datetime, []).append(path)

    # Process each group of BFMs
    for date, paths in grouped_bfms.items():
        # Check if the file for this date already exists
        tmp_bfm_file = savedir / f"bfms_{expname}_{date}.nc"

        if tmp_bfm_file.exists():
            logger.debug("🛰️ BFM file for date %s already exists", date)
            continue

        # get combined BFM for the date
        bfm = get_bfm_at_date(
            date,
            paths,
            read_epsg_from_state(state),
            read_poly_from_state(state),
        )
        if (bfm is None) or (bfm.size == 0):
            # if no data in bound for any bfm
            # or if .where gave an empty dataarray
            continue

        # if everything is fine, save the combined BFM for the date
        bfm.to_netcdf(tmp_bfm_file, engine="netcdf4", format="NETCDF4")
        logger.debug("🛰️ Wrote %s", tmp_bfm_file.name)

    return str(savedir)


def get_bfm_at_date(
    date: pd.Timestamp,
    paths: list[str],
    epsg: int,
    poly: gpd.GeoDataFrame,
) -> xr.DataArray | None:
    """
    Get combined BFM for a specific date from multiple paths.

    All BFMs are reprojected to match the DEM.
    Invalid values (nodata, 6, 7) are set to np.nan.
    0 = dry, 1 = flooded, np.nan = no data.
    6 = clouds, 7 = cloud shadows (only for optical)

    drop = True, allows for more efficient storing on disk for tmp files,
    while other = np.nan, allows for easier concatenation since there is
    no need for reindexing arrays (in .where).

    other = np.nan is prefered here for performance, because disk space
    for 10m raster satellite images is not a real bottleneck compared to
    having to concatenate a bunch of non aligned netcdfs
    """

    def bfms_yielder() -> Iterator[xr.DataArray]:
        for path in paths:
            bfm = reproj_clip(
                asinstance(rxr.open_rasterio(path, chunks="auto"), xr.DataArray),  # ty: ignore[invalid-argument-type]
                epsg=epsg,
                poly=poly,
            )
            # utils_da.reproj_clip returns None if no data in bound
            if bfm is not None:
                yield bfm

    if next(bfms_yielder(), None) is None:
        return None
    bfm = merge_arrays(list(bfms_yielder()))
    return (
        bfm.where(
            (bfm != bfm.rio.nodata) & (bfm != BFM_NO_DATA_6) & (bfm != BFM_NO_DATA_7),
            other=np.nan,  # drop=True,
        )
        .assign_coords(time=date)
        .expand_dims(dim="time")
    )


def get_max_depth_from_duration(
    duration: xr.DataArray,
    defended_method: DefendedMethod,
    dem: xr.DataArray,
    flooded_threshold: int = 0,
    hand_threshold: float | None = None,
) -> xr.DataArray:
    """
    Get maxDepth based on computed duration + a defended method + a DEM.

    Parameters
    ----------
    duration : xr.DataArray
        Flood duration in seconds.

    defended_method : DefendedMethod
        Defended depth estimation method.

    dem : xr.DataArray
        Digital Elevation Model (DEM).

    flooded_threshold : int, default: 0
        Duration threshold above which pixels are considered flooded.

    hand_threshold : float | None, default: None
        Accumulation threshold for the HAND method.

    Returns
    -------
    xr.DataArray
        Max water depth.

    """
    # duration values are in seconds, so should be the threshold
    max_flooded_extent = (duration > flooded_threshold).astype(np.uint8)

    max_depth = defended(
        method=defended_method,
        bfm=max_flooded_extent,
        dem=dem,
        hand_threshold=hand_threshold,
    )

    # remove negative values that make no physical sense
    return max_depth.where(max_depth >= 0, other=0)


def get_max_speed_from_dem(dem: xr.DataArray) -> xr.DataArray:
    """
    Compute the max speed from the bfms.

    No way of knowing the speed from the bfms: it is always nan.
    """
    return empty_copy_from_da(dem)


def get_duration_from_bfms(
    bfms: xr.DataArray,
    mindate: np.datetime64,
    maxdate: np.datetime64,
) -> xr.DataArray:
    """
    Docstring for get_duration_from_bfms.
    """
    if not isinstance(mindate, np.datetime64):
        msg = "mindate must be a numpy datetime64"
        raise TypeError(msg)
    if not isinstance(maxdate, np.datetime64):
        msg = "maxdate must be a numpy datetime64"
        raise TypeError(msg)
    return asinstance(
        xr.apply_ufunc(
            lambda values: get_duration(
                bfms["time"].to_numpy(),
                values,
                mindate,
                maxdate,
            ),
            bfms,
            input_core_dims=[["time"]],
            dask="parallelized",
            vectorize=True,
            output_dtypes=[np.float64],
            dask_gufunc_kwargs={"allow_rechunk": True},
        ).compute(),
        xr.DataArray,
    )


def are_unique_values_expected(bfm: xr.DataArray) -> bool:
    """
    Check that BFM values are valid (0, 1, np.nan).

    Return 0 if error, 1 if all NaN, 2 if valid.
    """
    unique_values = np.unique(bfm)

    valid_combinations = [
        # don't allow for all NaNs,
        # no data is taken care of
        # by get_bfm_at_date
        np.array([0]),
        np.array([1]),
        np.array([0, 1]),
        np.array([0, np.nan]),
        np.array([1, np.nan]),
        np.array([0, 1, np.nan]),
    ]

    return any(
        np.array_equal(unique_values, combo, equal_nan=True)
        for combo in valid_combinations
    )


def is_bfm_valid(paths: list[str | Path]) -> Iterator[bool]:
    """
    Hierarchical sequence of checks to see if BFM is valid or not.
    """
    for path in paths:
        da = xr.open_dataarray(path)
        if not are_unique_values_expected(da):
            logger.debug(
                "🛰️ Vals: %s, reject %s",
                np.unique(da),
                Path(path).name,
            )
            yield False
        else:
            yield True


def get_duration(
    dates: npt.NDArray[np.datetime64],
    values: npt.NDArray[np.int_],
    mindate: np.datetime64,
    maxdate: np.datetime64,
) -> float:
    """
    Get flood duration from Binary Flood Masks timeseries.

    Given a random timeseries of 0 and 1 at random dates,
    represented by `dates` and `values`:

    ```
    ^
    |
    |   0       1       1           0   1   0           1               1
    |
    L-----------------------------------------------------------------------> t

    `dates` and `values` indices:
    -----------------------------
        0       1       2           3   4   5           6               7

    `bounds` indices:
    -----------------
    |       |       |          |      |   |        |            |             |
    0       1       2          3      4   5        6            7             8
    |       |xxxxxxx|xxxxxxxxxx|      |xxx|        |xxxxxxxxxxxx|xxxxxxxxxxxxx|

    xs represent the timedeltas were we consider it to be flooded.

    We:
        1. Compute the mean date between two observations
            (to which we add `mindate` and `maxdate`,
            at positions 0 and -1 respectively)
            => `bounds` of size len(obs) + 1

        2. Iterate over `bounds`
            - Get the value in bounds from `values`
            - If the value is 1, add the value of timedelta to `total`
            => Some kind of nearest neighbours interpolation
            without the heavy resampling
    ```

    ---
    This could be improved further with Numba!
        - https://tutorial.xarray.dev/advanced/apply_ufunc/numba-vectorization.html
        - https://numba.pydata.org/numba-doc/dev/user/vectorize.html

    But this is good enough for now :)
    """
    # 0. Precomputation cleaning
    dates = np.sort(dates)
    if mindate >= dates[0]:
        msg = "mindate must be before the first available date"
        raise ValueError(msg)
    if maxdate <= dates[-1]:
        msg = "maxdate must be after the last available date"
        raise ValueError(msg)
    # 1. Compute bounds
    timedeltas = dates[1:] - dates[:-1]
    bounds = np.concatenate(
        (
            [mindate],
            [dates[:-1] + (timedeltas / 2)],
            [maxdate],
        ),
        axis=None,
    )
    # 2.  Iterate over bounds
    # > if everything is 0, return 0 early
    if np.all(values == 0):
        return 0.0
    # > if everything is nan, return 0 early
    if np.all(np.isnan(values)):
        return 0.0  # should be put to np.nan,
        # kept to 0 for compatibility
    # > else, compute duration
    return float(
        np.sum(
            np.where(
                # if value == 1
                values == 1,
                # then add the timedelta
                # between the bounds
                bounds[1:] - bounds[:-1],
                # else add 0
                0,
            ),
        ).item()  # get scalar from np.timedelta64
        / 1e9  # convert nanoseconds to seconds
    )


def load_bfms_from_nc_files(
    paths: list[str | Path],
    target_resolution: float,
) -> xr.DataArray:
    """
    Load a bunch of .nc files and concatenate them along a "time" dim.

    The way the .nc files are generated using get_bfm_at_date can lead to
    misalignments. To make sure all files are aligned, we generate an empty
    grid on the union of all files bbox, at target_resolution, and as a
    preprocess in xr.open_mfdataset() we .rio.reproject_match every file
    to this grid. In the future, maybe figure an efficient way to generate
    aligned individual netcdfs directly in get_bfm_at_date ?
    """
    # some preambulatory checks
    epsgs = [xr.open_dataarray(path).rio.crs.to_epsg() for path in paths]
    epsg = epsgs[0]
    if not all(x == epsg for x in epsgs):
        msg = "At least one EPSG mismatch"
        raise ValueError(msg)

    # template bbox at the union of all bboxes
    bboxes = [xr.open_dataarray(path).rio.bounds() for path in paths]
    w, s, e, n = reduce(bbox_union, bboxes)

    # finally create the template
    template = generate_empty_da_from_bounds((w, s, e, n), target_resolution, epsg)

    def _preprocess(da: xr.Dataset) -> xr.Dataset:
        # isel time = 0 because get_bfm_at_date generates a "time" dim
        # maybe change this behaviour later ?
        out = da.isel(time=0).rio.reproject_match(template)
        return asinstance(out, xr.Dataset)

    return asinstance(
        xr.open_mfdataset(
            paths,
            concat_dim="time",
            combine="nested",
            join="outer",
            preprocess=_preprocess,
        )
        .to_dataarray()
        .isel(variable=0)
        .drop_vars("variable")
        .sortby("time"),
        xr.DataArray,
    )


def filter_bfms(paths: list[str | Path]) -> list[str | Path]:
    """
    Map is_bfm_valid. on paths, return paths that are valid.
    """
    return list(compress(paths, is_bfm_valid(paths)))
