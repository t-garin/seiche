"""
Automattic plot of some generated data.
"""

import logging
from pathlib import Path
from typing import Any

import geopandas as gpd
import hvplot.pandas
import hvplot.xarray
import matplotlib.colors as mcolors
import rioxarray as rxr
import xarray as xr

from seiche.utils_enum import Landcover, OutputFiles, PopDataset
from seiche.utils_plot import Colors, HvOpts
from seiche.utils_qol import asinstance
from seiche.utils_state import (
    read_landcovers_from_state,
    read_pop_datasets_from_state,
)

logger = logging.getLogger(__name__)


def _plot_dem(state: dict[str, Any]) -> None:
    """
    Desc.
    """
    dem = asinstance(
        rxr.open_rasterio(OutputFiles.dem.savepath(state)),
        xr.DataArray,
    )
    _save_hvplot(
        state,
        filename=OutputFiles.dem.filename(state),
        fig=dem.isel(band=0).hvplot(cmap="terrain", bgcolor="grey", **HvOpts.basic_rxr),
    )


def _plot_esawc(state: dict[str, Any]) -> None:
    esawc = asinstance(
        rxr.open_rasterio(
            OutputFiles.lcv.savepath(state, ext="tif", landcover=Landcover.esawc),
        ),
        xr.DataArray,
    )
    bounds = [5, 15, 25, 35, 45, 55, 65, 75, 85, 92.5, 97.5, 105]
    norm = mcolors.BoundaryNorm(boundaries=bounds, ncolors=len(bounds) - 1)
    esawc_plot = (
        esawc.where(esawc)
        .isel(band=0)
        .hvplot(
            cmap=Colors.esawc_list,
            norm=norm,
            cticks=[
                (10, "Tree Cover"),
                (20, "Shrubland"),
                (30, "Grassland"),
                (40, "Cropland"),
                (50, "Built-up"),
                (60, "Bare/Sparse vegetation"),
                (70, "Snow and Ice"),
                (80, "Permanent Water Bodies"),
                (88.5, "Herbaceous Wetland"),
                (95, "Mangroves"),
                (100, "Moss and Lichen"),
            ],
            **HvOpts.basic_rxr_nogeo,
        )
    )
    _save_hvplot(
        state,
        esawc_plot,
        OutputFiles.lcv.filename(state, ext="tif", landcover=Landcover.esawc),
    )


def _plot_oso23(state: dict[str, Any]) -> None:
    oso23 = asinstance(
        rxr.open_rasterio(
            OutputFiles.lcv.savepath(state, ext="tif", landcover=Landcover.oso23),
        ),
        xr.DataArray,
    )
    bounds = [i + 0.5 for i in range(24)]
    norm = mcolors.BoundaryNorm(boundaries=bounds, ncolors=len(bounds) - 1)
    oso23_plot = (
        oso23.where(oso23)
        .isel(band=0)
        .hvplot(
            cmap=Colors.oso23_list,
            norm=norm,
            cticks=[
                (1, "Urbain dense"),
                (2, "Urbain diffus"),
                (3, "Zone industrielle et commerciale"),
                (4, "Routes"),
                (5, "Oléagineux d'hiver"),
                (6, "Céréales à paille"),
                (7, "Protéagineux de printemps"),
                (8, "Soja"),
                (9, "Tournesol"),
                (10, "Mais"),
                (11, "Riz"),
                (12, "Tubercules/racines"),
                (13, "Prairies"),
                (14, "Vergers"),
                (15, "Vignes"),
                (16, "Forêts de feuillus"),
                (17, "Fôrets de conifères"),
                (18, "Pelouses"),
                (19, "Landes"),
                (20, "Surfaces minérales"),
                (21, "Plages et dunes"),
                (22, "Glaciers et neiges éternelles"),
                (23, "Eau"),
            ],
            **HvOpts.basic_rxr_nogeo,
        )
    )
    _save_hvplot(
        state,
        oso23_plot,
        OutputFiles.lcv.filename(state, ext="tif", landcover=Landcover.oso23),
    )


def _plot_rpg(state: dict[str, Any]) -> None:
    rpg = gpd.read_file(
        OutputFiles.lcv.savepath(state, ext="gpkg", landcover=Landcover.rpg),
    )
    rpg["CODE_GROUP"] = rpg["CODE_GROUP"].astype(int)

    rpg_plot = rpg.hvplot(
        kind="polygons",
        color="CODE_GROUP",
        cmap=Colors.rpg_code_group_list,
        # pin the norm to the fixed 1-28 CODE_GROUP range, otherwise the default
        # continuous normalization rescales to the data min/max and shifts colors
        clim=(1, 28),
        cticks=[
            (1, "Blé tendre"),
            (2, "Maïs grain et ensilage"),
            (3, "Orge"),
            (4, "Autres céréales"),
            (5, "Colza"),
            (6, "Tournesol"),
            (7, "Autres oléagineux"),
            (8, "Protéagineux"),
            (9, "Plantes à fibre"),
            (10, ""),
            (11, "Gel"),
            (12, ""),
            (13, ""),
            (14, "Riz"),
            (15, "Légumineuses à grain"),
            (16, "Fourrage"),
            (17, "Estives et landes"),
            (18, "Prairies permanentes"),
            (19, "Prairies temporaires"),
            (20, "Vergers"),
            (21, "Vignes"),
            (22, "Fruits à coques"),
            (23, "Oliviers"),
            (24, "Autres cultures industrielles"),
            (25, "Légumes ou fleurs"),
            (26, "Canne à sucre"),
            (27, ""),
            (28, "Divers"),
        ],
        clabel="",
        data_aspect=1,
        height=1000,
        width=1000,
        fontscale=2,
        xaxis=None,
        yaxis=None,
        linewidth=0,
    )
    _save_hvplot(
        state,
        rpg_plot,
        OutputFiles.lcv.filename(state, ext="gpkg", landcover=Landcover.rpg),
    )


def _plot_hzds(state: dict[str, Any]) -> None:
    """
    Be careful, "hzd_" is hardcoded here.
    """
    for hzdpath in Path(state["config"]["path.out"]).glob("hzd_*.tif"):
        hzd = asinstance(rxr.open_rasterio(hzdpath), xr.DataArray)
        for band, suffix, cmap in (
            (0, "H", "Reds"),
            (1, "V", "Greens"),
            (2, "T", "Blues"),
        ):
            band_data = hzd.where(hzd).isel(band=band)
            # some hazards have no speed/duration (e.g. fwdet): skip empty bands
            if band_data.notnull().any():
                _save_hvplot(
                    state,
                    filename=f"{Path(hzdpath).name}_{suffix}",
                    fig=band_data.hvplot(
                        cmap=cmap,
                        bgcolor="grey",
                        robust=True,
                        **HvOpts.basic_rxr,
                    ),
                )


def _plot_pops(state: dict[str, Any]) -> None:
    poppaths = [
        path
        for path in Path(state["config"]["path.out"]).glob("*.tif")
        if "ghslpop" in path.name or "filosofi" in path.name
    ]
    for poppath in poppaths:
        pop = asinstance(rxr.open_rasterio(poppath), xr.DataArray)

        pop_plot = (
            (pop.isel(band=0) + 1e-10)
            # add epsilon to keep "zeros" when plotting with log cnorm
            .hvplot(
                cmap="Purples",
                bgcolor="grey",
                cnorm="log",
                clim=(1, None),
                **HvOpts.basic_rxr_nogeo,
            )
        )
        _save_hvplot(state, pop_plot, Path(poppath).name + "_map")

        pop.name = "_"
        # mask non-positive values (nodata artifacts like -200) that would
        # otherwise break the log-scale histogram bins
        pop_hist = pop.where(pop > 0).hvplot.hist(
            logx=True,
            bins=99,
            xlim=(1, None),
            legend=False,
            grid=True,
            title="",
            xlabel="N# of people per pixel",
            ylabel="Number of pixels",
        )
        _save_hvplot(state, pop_hist, Path(poppath).name + "_hist")


def _save_hvplot(state: dict[str, Any], fig: object, filename: str) -> None:
    """
    Dave hvplot.
    """
    if not isinstance(filename, str):
        msg = f"filename must be a str, got {filename}"
        raise TypeError(msg)
    savepath = f"{state['config']['path.out']}/{filename}.png"
    hvplot.save(fig, savepath, backend="matplotlib")
    logger.info("🎨 %s.png", filename)


def plot(state: dict[str, Any]) -> dict[str, Any]:
    """
    Plot all SEICHE outputs.
    """
    if not state["config"]["param.autoplot"]:
        logger.info("Skipping automatic plotting")
        return state
    hvplot.extension("matplotlib")  # ty: ignore[too-many-positional-arguments]
    landcovers = read_landcovers_from_state(state)
    if Landcover.esawc in landcovers:
        _plot_esawc(state)
    if Landcover.oso23 in landcovers:
        _plot_oso23(state)
    if Landcover.rpg in landcovers:
        _plot_rpg(state)
    pop_datasets = read_pop_datasets_from_state(state)
    if PopDataset.ghslpop in pop_datasets or PopDataset.filosofi in pop_datasets:
        _plot_pops(state)
    _plot_dem(state)
    _plot_hzds(state)
    return state  # pragma: no cover - tracer lost after the geo hvplot above
