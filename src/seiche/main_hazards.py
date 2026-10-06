"""
Generate hazard rasters from Telemac2D Selafin files or BFMs NetCDF files.
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rioxarray as rxr
import xarray as xr

from seiche.format_bfm import (
    filter_bfms,
    generate_bfms_netcdfs,
    get_duration_from_bfms,
    get_max_depth_from_duration,
    load_bfms_from_nc_files,
)
from seiche.format_slf import Slf
from seiche.utils_da import empty_copy_from_da, reproj_clip
from seiche.utils_enum import HazardBand, HazardSource, OutputFiles
from seiche.utils_qol import asinstance, require
from seiche.utils_state import (
    read_defended_methods_from_state,
    read_epsg_from_state,
    read_hazards_from_state,
    read_poly_from_state,
    read_use_variables_from_state,
)

logger = logging.getLogger(__name__)


def generate_hazard(state: dict[str, Any]) -> dict[str, Any]:
    """
    Generate the hazard rasters and store their paths in the state.
    """
    methods = read_hazards_from_state(state)
    dem = None
    if HazardSource.slf in methods or HazardSource.bfm in methods:
        dem = asinstance(rxr.open_rasterio(state["dem"]["path"]), xr.DataArray)
    hazard = {}
    for method in methods:
        match method:
            case HazardSource.bfm:
                hazard.update(generate_bfm_hazard(require(dem), state))
            case HazardSource.slf:
                hazard.update(generate_slf_hazard(require(dem), state))
            case HazardSource.hvt:
                hazard.update(generate_hvt_hazard(state))
            case _:
                msg = "Hazard method should be 'bfm', 'slf' or 'hvt', not {method}"
                raise ValueError(msg)
    del dem
    hazard_paths = {
        name: OutputFiles.hzd.savepath(state, nickname=name) for name in hazard
    }
    del hazard
    return {**state, "hazard": hazard_paths}


def generate_hazard_from_bands(
    max_depth: xr.DataArray,
    max_speed: xr.DataArray,
    duration: xr.DataArray,
    state: dict[str, Any],
    *,
    fillna0: bool = True,
) -> xr.DataArray:
    """
    Take max_depth, max_speed, duration and combine them into a 3-band hazard.

    N.B.: Fill NaN with 0 to avoid issues when computing damages because
    if there is NaN depth, damage funcs take the average for non-NaN depth
    values. In the case where the duration is 0 but the depth is NaN (e.g.),
    the dmg func would compute a non-zero damage, which is wrong.
    """
    # To make sur they are aligned,
    # we take max_depth as reference and reproject everything on it.
    max_speed = asinstance(max_speed.rio.reproject_match(max_depth), xr.DataArray)
    duration = asinstance(duration.rio.reproject_match(max_depth), xr.DataArray)

    if fillna0:
        max_depth = asinstance(max_depth.fillna(0), xr.DataArray)
        max_speed = asinstance(max_speed.fillna(0), xr.DataArray)
        duration = asinstance(duration.fillna(0), xr.DataArray)

    hzd = xr.concat([max_depth, max_speed, duration], dim="band", join="exact")

    return require(
        reproj_clip(
            hzd,
            epsg=read_epsg_from_state(state),
            poly=read_poly_from_state(state),
        )
    )


def generate_slf_hazard(
    dem: xr.DataArray,
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate hazard rasters from Telemac2D Selafin files.
    """
    hazard = {}
    use_max_depth, use_max_speed, use_duration = read_use_variables_from_state(state)

    for slf_config in state["config"]["path.inp.slf"]:
        nickname = slf_config["nickname"]
        logger.info("Processing slf: %s", nickname)

        slf_savepath = OutputFiles.hzd.savepath(state, nickname=nickname)

        slf_from_freesurf_savepath = OutputFiles.hzd.savepath(
            state,
            nickname=f"{nickname}_from_freesurf",
        )

        if slf_savepath.exists() and slf_from_freesurf_savepath.exists():
            hazard[nickname] = asinstance(rxr.open_rasterio(slf_savepath), xr.DataArray)
            hazard[f"{nickname}_from_freesurf"] = asinstance(
                rxr.open_rasterio(
                    slf_from_freesurf_savepath,
                ),
                xr.DataArray,
            )
            continue

        slf = Slf(
            file_name=Path(state["config"]["path.inp"]) / slf_config["filepath"],
            epsg=slf_config["epsg"],
            depth_varname=slf_config["depthVarname"],
            x_speed_varname=slf_config["xspeedVarname"],
            y_speed_varname=slf_config["yspeedVarname"],
            freesurf_varname=slf_config["freesurfVarname"],
        )

        grid = slf.generate_grid_on_extent(
            pixel_size=state["config"]["param.slf.pixel_size"]
        )

        logger.debug("Interpolation grid generated ✅")

        if use_max_depth:
            max_depth = slf.interp_max_depth_on_grid(grid)
            max_freesurf = slf.interp_max_freesurf_on_grid(grid)
            max_depth_from_freesurf = max_freesurf - dem.rio.reproject_match(
                max_freesurf,
            )
            logger.debug("Maximum water depth interpolated ✅")
        else:
            max_depth = grid.copy(data=np.full_like(grid.values, fill_value=np.nan))
            max_depth_from_freesurf = grid.copy(
                data=np.full_like(grid.values, fill_value=np.nan),
            )

        if use_max_speed:
            max_speed = slf.interp_max_speed_on_grid(grid)
            logger.debug("Maximum water speed interpolated ✅")
        else:
            max_speed = grid.copy(data=np.full_like(grid.values, fill_value=np.nan))

        if use_duration:
            duration = slf.interp_duration_on_grid(
                grid,
                threshold=slf_config["depthThreshold"],
            )
            logger.debug("Flood duration interpolated ✅")
        else:
            duration = grid.copy(data=np.full_like(grid.values, fill_value=np.nan))

        del slf
        del grid

        for name, max_depth_band, savepath in zip(
            [nickname, f"{nickname}_from_freesurf"],
            [max_depth, max_depth_from_freesurf],
            [slf_savepath, slf_from_freesurf_savepath],
            strict=True,
        ):
            hazard[name] = generate_hazard_from_bands(
                max_depth=max_depth_band,
                max_speed=max_speed,
                duration=duration,
                state=state,
            )
            hazard[name].rio.to_raster(savepath)
            # deletes it from memory to free memory
            # otherwise can crash out the computation
            # for large spatial extents
            del hazard[name]
            # lazy load the file back
            hazard[name] = asinstance(rxr.open_rasterio(savepath), xr.DataArray)

    return hazard


def generate_hvt_hazard(state: dict[str, Any]) -> dict[str, Any]:
    """
    Generate hazard rasters from user-provided 3-band H/V/T rasters.

    The input raster bands must be, in order: H (max water depth), V (max
    water velocity) and T (flood duration). The bands are combined with
    :func:`generate_hazard_from_bands`, which reprojects and clips them to the
    study area, so no DEM or hydrodynamic model output is needed.
    """
    hazard = {}
    for hvt_config in state["config"]["path.inp.hvt"]:
        nickname = hvt_config["nickname"]
        logger.info("Processing hvt: %s", nickname)

        savepath = OutputFiles.hzd.savepath(state, nickname=nickname)

        if savepath.exists():
            hazard[nickname] = asinstance(rxr.open_rasterio(savepath), xr.DataArray)
            continue

        hvt = asinstance(
            rxr.open_rasterio(
                Path(state["config"]["path.inp"]) / hvt_config["filepath"],
            ),
            xr.DataArray,
        )
        n_bands = len(list(HazardBand))
        if hvt.shape[0] != n_bands:
            msg = (
                f"hvt raster '{hvt_config['filepath']}' must have {n_bands} bands "
                f"(H, V, T), got {hvt.shape[0]}"
            )
            raise ValueError(msg)

        hazard[nickname] = generate_hazard_from_bands(
            max_depth=hvt.isel(band=0),
            max_speed=hvt.isel(band=1),
            duration=hvt.isel(band=2),
            state=state,
        )
        hazard[nickname].rio.to_raster(savepath)
        # deletes it from memory to free memory, then lazy loads the file back
        del hazard[nickname]
        hazard[nickname] = asinstance(rxr.open_rasterio(savepath), xr.DataArray)

    return hazard


def generate_bfm_hazard(
    dem: xr.DataArray,
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate hazard rasters from BFMs NetCDF files.
    """
    # 1. convert geoTiffs in individual netCDFs
    savedir = generate_bfms_netcdfs(state)

    # 2. compute duration
    duration_savepath = OutputFiles.duration.savepath(state)

    if not duration_savepath.exists():
        logger.info("Duration file not found, generating it...")
        paths2keep = filter_bfms(list(Path(savedir).glob("*.nc")))
        bfms = load_bfms_from_nc_files(
            paths2keep,
            state["config"]["param.bfm.target_resolution"],
        )
        duration = get_duration_from_bfms(
            bfms,
            pd.Timestamp(state["config"]["param.bfm.start_date"]).to_datetime64(),
            pd.Timestamp(state["config"]["param.bfm.end_date"]).to_datetime64(),
        )
        duration.rio.to_raster(duration_savepath)

    duration = asinstance(rxr.open_rasterio(duration_savepath), xr.DataArray)

    # -------------------------------------------------------------------------

    # 3. Compute speed (not really)
    max_speed = empty_copy_from_da(dem)

    # -------------------------------------------------------------------------

    hazard = {}

    # 4. Iterate over defended methods to compute max_depth
    for defended_method in read_defended_methods_from_state(state):
        hazard_savepath = OutputFiles.hzd.savepath(state, nickname=defended_method)
        if not hazard_savepath.exists():
            logger.info(
                "Couldn't find, generating: %s",
                hazard_savepath.name,
            )
            max_depth = get_max_depth_from_duration(
                duration=duration,
                defended_method=defended_method,
                dem=dem,
                flooded_threshold=state["config"]["param.bfm.flooded_threshold"],
            )
            generate_hazard_from_bands(
                max_depth=max_depth,
                max_speed=max_speed,
                duration=duration,
                state=state,
            ).rio.to_raster(hazard_savepath)
            logger.info("Saved %s", hazard_savepath.name)
            del max_depth

        hazard[defended_method] = asinstance(
            rxr.open_rasterio(hazard_savepath), xr.DataArray
        )
    return hazard
