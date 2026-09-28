"""
Functions to evaluate the number of affected people.

Based on the Filosofi (INSEE) data, and the
Global Human Settlement Layer (GHSL) population data.
"""

from collections.abc import Callable

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from rasterio.enums import Resampling

from seiche.utils_enum import HazardBand
from seiche.utils_gdf import concat_hazard
from seiche.utils_qol import asinstance


def parse_condition(expr: str) -> Callable[..., object]:
    """
    Return a condition callable from a boolean expression string.

    The condition has signature `(h, v, t) -> bool mask`. The expression is
    evaluated with `eval` against an empty `__builtins__` namespace, so no
    builtins or arbitrary names are reachable; only `h`, `v`, `t`, `True`
    and `False`.

    Parameters
    ----------
    expr : str
        Boolean expression on `h`, `v` and `t`, e.g. `"h > 0.3"`.

    Returns
    -------
    Callable
        Function of signature `(h, v, t)` returning a boolean mask matching the
        input type.

    Raises
    ------
    NameError
        If the expression references any name other than `h`, `v`, `t`, `True`
        or `False`.

    Examples
    --------
    See the `param.pop.conditions` documentation.

    """
    namespace: dict[str, object] = {
        "h": None,
        "v": None,
        "t": None,
        "True": True,
        "False": False,
    }

    def condition(h: object, v: object, t: object) -> object:
        namespace.update({"h": h, "v": v, "t": t})
        return eval(expr, {"__builtins__": {}}, namespace)  # noqa: S307

    return condition


# filosofi
def get_affected_people_vector(
    hazard: xr.DataArray,
    popvector: gpd.GeoDataFrame,
    conditions: list[Callable[..., object]] | None = None,
) -> list[gpd.GeoDataFrame]:
    """
    Calculate the number of affected people from Filosofi (INSEE) data.

    This function takes a hazard raster (with bands for water depth, velocity, and
    duration) and a population vector, applies a condition to the hazard data, and
    returns the number of affected people per row where the condition is met.

    Parameters
    ----------
    hazard : xr.DataArray
        Hazard raster of shape (band, y, x), with bands:
            - 0: H (max water depth)
            - 1: V (max water velocity)
            - 2: T (flood duration)

    popvector : gpd.GeoDataFrame
        Filosofi vector data, typically with a column 'ind' for population count.

    conditions : callable, default: parse_condition("True")
        Function that takes (H, V, T) and returns a boolean mask. Defaults to
        ``"True"``.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with additional columns for H, V, T and masked on the area
        when the condition matches.

    """
    popvector = popvector.to_crs(hazard.rio.crs)
    popvector = concat_hazard(popvector, hazard)
    if conditions is None:
        conditions = [parse_condition("True")]
    estimations_list = []
    # ---
    for condition in conditions:
        mask = condition(
            h=popvector[HazardBand.max_depth],
            v=popvector[HazardBand.max_speed],
            t=popvector[HazardBand.duration],
        )
        if np.isscalar(mask):
            mask = pd.Series(mask, index=popvector.index)
        estimations_list.append(asinstance(popvector.where(mask), gpd.GeoDataFrame))
    # ---
    return estimations_list


# ghslpop
def get_affected_people_raster(
    hazard: xr.DataArray,
    pop: xr.DataArray,
    condition: Callable[..., object] | None = None,
    resampling: Resampling = Resampling.nearest,
) -> xr.DataArray:
    """
    Calculate the number of affected people from GHSL population data.

    This function takes a hazard raster (with bands for water depth, velocity, and
    duration) and a population raster, applies a condition to the hazard data, and
    returns the number of affected people per pixel where the condition is met.

    Parameters
    ----------
    hazard : xr.DataArray
        Hazard raster of shape (band, y, x), with bands:
            - 0: H (max water depth)
            - 1: V (max water velocity)
            - 2: T (flood duration)

    pop : xr.DataArray
        GHSL population raster, typically opened with rioxarray, of shape (band, y, x).

    condition : callable, default: parse_condition("True")
        Function that takes (H, V, T) and returns a boolean mask. Defaults to
        ``"True"``.

    resampling : Resampling, default: Resampling.nearest
        Resampling method to use when reprojecting the hazard data to match the
        population data, based on rasterio.enums.Resampling.

    Returns
    -------
    xr.DataArray
        Number of affected people per pixel, masked by the condition.

    """
    if hazard.rio.crs != pop.rio.crs:
        if pop.size < hazard.size:
            pop = asinstance(pop.rio.reproject(hazard.rio.crs), xr.DataArray)
        else:
            hazard = asinstance(hazard.rio.reproject(pop.rio.crs), xr.DataArray)
    pop = asinstance(pop.rio.clip_box(*hazard.rio.bounds()), xr.DataArray)
    # downsample or upsample hazard to match pop
    # not the other way around, since it could change
    # the number of people per pixel
    hazard = asinstance(
        hazard.rio.reproject_match(pop, resampling=resampling), xr.DataArray
    )
    if condition is None:
        condition = parse_condition("True")
    pop = asinstance(pop.where(hazard.notnull()), xr.DataArray)  # noqa: PD004
    return asinstance(
        pop.where(
            condition(
                h=hazard.isel(band=HazardBand.max_depth.band_index),
                v=hazard.isel(band=HazardBand.max_speed.band_index),
                t=hazard.isel(band=HazardBand.duration.band_index),
            ),
        ),
        xr.DataArray,
    )
