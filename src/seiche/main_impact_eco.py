"""
Compute economic impacts based on hazard and landcover data.
"""

import itertools
import logging
from typing import Any

import geopandas as gpd
import rioxarray as rxr
import xarray as xr

from seiche.dmgfunc_floodam import Floodam
from seiche.dmgfunc_jrc import JRC
from seiche.format_lcv import generate_or_load_lcv
from seiche.maps import MAPS
from seiche.utils_da import reproj_clip
from seiche.utils_enum import (
    DamageFunc,
    FloodamAlea,
    FloodamSeason,
    HciMode,
    JrcRegion,
    Landcover,
    LandcoverType,
    OutputFiles,
)
from seiche.utils_qol import asinstance, require
from seiche.utils_state import (
    read_dmgfuncs_from_state,
    read_epsg_from_state,
    read_landcovers_from_state,
    read_poly_from_state,
)

logger = logging.getLogger(__name__)


def _compute_jrc_raster(  # noqa: PLR0913
    jrc: JRC,
    state: dict[str, Any],
    landcover_name: Landcover,
    nickname: str,
    hzd: xr.DataArray,
    landcover: xr.DataArray,
) -> None:
    """
    Compute JRC damage factor / std / maxdmg rasters for a raster landcover.
    """
    epsg = read_epsg_from_state(state)
    poly = read_poly_from_state(state)
    dmgfac_savepath = OutputFiles.dmgfac.savepath(
        state,
        nickname=nickname,
        landcover=landcover_name,
    )
    std_savepath = OutputFiles.std.savepath(
        state,
        nickname=nickname,
        landcover=landcover_name,
    )
    maxdmg_savepath = OutputFiles.maxdmg.savepath(
        state,
        nickname=nickname,
        landcover=landcover_name,
    )
    if not dmgfac_savepath.exists() or not std_savepath.exists():
        max_depth = hzd.isel(band=0).expand_dims("band")
        dmg_fac, std = jrc.get_dmg_fac_raster_lc(
            landcover=landcover,
            max_depth=max_depth,
            map_jrc=MAPS[landcover_name]["map_jrc"],
            region=JrcRegion(state["config"]["param.jrc.region"]),
        )
        require(reproj_clip(dmg_fac, epsg, poly)).rio.to_raster(dmgfac_savepath)
        require(reproj_clip(std, epsg, poly)).rio.to_raster(std_savepath)
    if not maxdmg_savepath.exists():
        max_dmg = jrc.get_max_dmg_raster_lc(
            landcover=landcover,
            map_jrc=MAPS[landcover_name]["map_jrc"],
            a3=state["config"]["param.jrc.a3"],
            hci_mode=HciMode.landuse,  # important for raster
        )
        require(reproj_clip(max_dmg, epsg, poly)).rio.to_raster(maxdmg_savepath)
    logger.critical("CONVERT TO € PER PIX & CHECK €/HA VS €/M2")


def _compute_jrc_vector(  # noqa: PLR0913
    jrc: JRC,
    state: dict[str, Any],
    landcover_name: Landcover,
    nickname: str,
    hzd: xr.DataArray,
    landcover: gpd.GeoDataFrame,
) -> None:
    """
    Compute JRC damage factors for a vector landcover.
    """
    savepath = OutputFiles.dmg.savepath(
        state,
        nickname=nickname,
        landcover=landcover_name,
    )
    if not savepath.exists():
        dmg_fac = jrc.get_dmg_fac_vector_lc(
            landcover=landcover,
            hazard=hzd,
            col2keep=MAPS[landcover_name]["column_for_jrc"],
            map_jrc=MAPS[landcover_name]["map_jrc"],
            region=JrcRegion(state["config"]["param.jrc.region"]),
        )
        dmg_fac.to_file(savepath, driver="GPKG")
    logger.critical("TODO: missing maxdmg for vector jrc")


def _compute_floodam(  # noqa: PLR0913
    floodam: Floodam,
    state: dict[str, Any],
    landcover_name: Landcover,
    nickname: str,
    hzd: xr.DataArray,
    landcover: gpd.GeoDataFrame,
) -> None:
    """
    Compute Floodam damages for a vector landcover.
    """
    savepath = OutputFiles.dmg.savepath(
        state,
        nickname=nickname,
        landcover=landcover_name,
    )
    if savepath.exists():
        return
    if landcover_name is Landcover.rpg:
        landcover["classe"] = (
            landcover["CODE_GROUP"].astype(int).map(MAPS[Landcover.rpg]["map_floodam"])
        )
        dmg = floodam.get_dmg_agri_rpg(
            landcover=asinstance(landcover.dropna(subset="classe"), gpd.GeoDataFrame),
            hazard=hzd,
            season=FloodamSeason(state["config"]["param.floodam.season"]),
            classe_col="classe",
        )
    elif landcover_name is Landcover.bdtopo:
        dmg = floodam.get_dmg_housing_bdtopo(
            lcv=landcover,
            hzd=hzd,
            alea=FloodamAlea(state["config"]["param.floodam.alea"]),
        )
    else:
        dmg = floodam.get_dmg_commercial_standalone_sirene(
            lcv=landcover,
            hzd=hzd,
            alea=FloodamAlea(state["config"]["param.floodam.alea"]),
            return_minimum_price_if_above_thresh=True,
        )
    dmg.to_file(savepath, driver="GPKG")


def impact_eco(state: dict[str, Any]) -> dict[str, Any]:
    """
    See module docstring.
    """
    hazard = {
        name: asinstance(rxr.open_rasterio(path), xr.DataArray)
        for name, path in state["hazard"].items()
    }
    logger.info("💲 Starting damage computation")

    landcovers = read_landcovers_from_state(state)
    dmgfuncs = read_dmgfuncs_from_state(state)

    # load before the loop in case it is used multiple times
    floodam: Floodam | None = Floodam() if DamageFunc.floodam in dmgfuncs else None
    jrc: JRC | None = JRC() if DamageFunc.jrc in dmgfuncs else None
    logger.info("💲 Dmgfuncs and Population databases initialized")

    for landcover_name, dmgfunc, (nickname, hzd) in itertools.product(
        landcovers,
        dmgfuncs,
        hazard.items(),
    ):
        # =====================================================================
        # Computation to skip match-case
        # Split in 2 match cases to be sure it skips correctly
        # =====================================================================
        match (landcover_name, dmgfunc):
            case (
                Landcover.rpg | Landcover.bdtopo | Landcover.sirene,
                DamageFunc.jrc,
            ):
                logger.info("💲 Skipping %s x %s", landcover_name, dmgfunc)
                continue  # get out of the loop early
        logger.info("💲 ~ %s x %s x %s ~", landcover_name, dmgfunc, nickname)
        landcover, landcover_type = generate_or_load_lcv(state, landcover_name)

        match (landcover_name, landcover_type, dmgfunc):
            case (_, LandcoverType.raster, DamageFunc.jrc):
                _compute_jrc_raster(
                    require(jrc),
                    state,
                    landcover_name,
                    nickname,
                    hzd,
                    asinstance(landcover, xr.DataArray),
                )
            case (_, LandcoverType.vector, DamageFunc.jrc):
                _compute_jrc_vector(
                    require(jrc),
                    state,
                    landcover_name,
                    nickname,
                    hzd,
                    asinstance(landcover, gpd.GeoDataFrame),
                )
            case (_, LandcoverType.vector, DamageFunc.floodam):
                _compute_floodam(
                    require(floodam),
                    state,
                    landcover_name,
                    nickname,
                    hzd,
                    asinstance(landcover, gpd.GeoDataFrame),
                )
            case _:
                logger.info("💲 Undefined configuration, skipping")
    del hazard
    return state
