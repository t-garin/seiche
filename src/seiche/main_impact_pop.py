"""
Compute affected population based on hazard rasters and population datasets.
"""

import logging
from pathlib import Path
from typing import Any

import geopandas as gpd
import rioxarray as rxr
import xarray as xr

from seiche.affected_population import (
    get_affected_people_raster,
    get_affected_people_vector,
    parse_condition,
)
from seiche.utils_da import reproj_clip
from seiche.utils_enum import OutputFiles, PopDataset
from seiche.utils_qol import asinstance, require
from seiche.utils_state import (
    read_epsg_from_state,
    read_poly_from_state,
    read_pop_conditions_from_state,
    read_pop_datasets_from_state,
)

logger = logging.getLogger(__name__)


def _process_ghslpop(
    state: dict[str, Any],
    nickname: str,
    hzd_filled: xr.DataArray,
    ghslpop: xr.DataArray,
) -> None:
    """
    Compute affected people from a raster population layer (GHSL).
    """
    # IMPORTANT THAT WE DONT REPROJECT THE POP HERE
    # IT COULD MESS WITH THE NUM OF PEOPLE PER PIXEL
    for condition, expr in read_pop_conditions_from_state(state).items():
        savepath = OutputFiles.ghslpop.savepath(
            state,
            nickname=nickname,
            condition=condition,
        )
        if not savepath.exists():
            affected = get_affected_people_raster(
                hazard=hzd_filled,
                pop=ghslpop,
                condition=parse_condition(expr),
            )
            affected.rio.to_raster(savepath)


def _process_filosofi(
    state: dict[str, Any],
    nickname: str,
    hzd_filled: xr.DataArray,
    filosofi: gpd.GeoDataFrame,
) -> None:
    """
    Compute affected people from a vector population layer (Filosofi).
    """
    pop_conditions = read_pop_conditions_from_state(state)
    affected_population_estimations = get_affected_people_vector(
        hazard=hzd_filled,
        popvector=filosofi,
        conditions=[parse_condition(expr) for _, expr in pop_conditions.items()],
    )
    for i, condition in enumerate(pop_conditions):
        savepath = OutputFiles.filosofi.savepath(
            state,
            nickname=nickname,
            condition=condition,
        )
        if not savepath.exists():
            affected_population_estimations[i].to_file(savepath, driver="GPKG")


def impact_pop(state: dict[str, Any]) -> dict[str, Any]:
    """
    See module docstring.
    """
    pop_datasets = read_pop_datasets_from_state(state)
    epsg = read_epsg_from_state(state)
    poly = read_poly_from_state(state)
    hazard = {
        name: asinstance(rxr.open_rasterio(path), xr.DataArray)
        for name, path in state["hazard"].items()
    }
    # load it before the loop in case it is used multiple times
    ghslpop: xr.DataArray | None = None
    filosofi: gpd.GeoDataFrame | None = None
    if PopDataset.ghslpop in pop_datasets:
        ghslpop = asinstance(
            rxr.open_rasterio(
                Path(state["config"]["path.inp"])
                / state["config"]["path.inp.pop.ghslpop"][0],
            ),
            xr.DataArray,
        )
    if PopDataset.filosofi in pop_datasets:
        filosofi = asinstance(
            gpd.read_file(
                Path(state["config"]["path.inp"])
                / state["config"]["path.inp.pop.filosofi"][0],
            )
            .to_crs(epsg=epsg)
            .clip(poly),
            gpd.GeoDataFrame,
        )
    logger.warning("for now only 1 file for pop rasters")

    for nickname, hzd in hazard.items():
        # =====================================================================
        # Fill hazard nan values with 0
        # > otherwise, issues when resampling a raster with a lot of holes
        # > fill everything with 0, doesnt change when Resampling.average
        # =====================================================================
        # maybe should be done directly in main_hazard.py ?
        hzd_filled = require(
            reproj_clip(
                hzd.fillna(0),
                epsg=hzd.rio.crs.to_epsg(),
                poly=poly,
            )
        )
        del hzd
        for pop in pop_datasets:
            logger.info("☠️ ~ %s x %s ~", nickname, pop)
            match pop:
                case PopDataset.ghslpop:
                    _process_ghslpop(state, nickname, hzd_filled, require(ghslpop))
                case PopDataset.filosofi:
                    _process_filosofi(state, nickname, hzd_filled, require(filosofi))
                case _:
                    logger.info("☠️ Undefined configuration, skipping")
        del hzd_filled
    del hazard
    return state
