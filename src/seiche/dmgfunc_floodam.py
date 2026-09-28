"""
Floodam Class.
"""

import logging
from pathlib import Path
from typing import TypedDict

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

from seiche.utils_da import read_netcdf
from seiche.utils_enum import FloodamAlea, FloodamSeason, HazardBand
from seiche.utils_gdf import concat_hazard, find_column, streamline
from seiche.utils_qol import asinstance, compute_file_sha256, require

logger = logging.getLogger(__name__)


class _FloodamPrecompiled(TypedDict):
    """
    Typed shape of the precompiled Floodam files.
    """

    a: xr.Dataset
    h: xr.Dataset
    p: xr.Dataset
    batisurf: xr.Dataset
    stockemp: xr.Dataset
    totalemp: xr.Dataset
    seuilemp: pd.DataFrame
    sirenemp: pd.DataFrame
    ct: pd.DataFrame
    wext: xr.DataArray
    wint: xr.DataArray


def _read_precompiled(
    precompiled_dir: str | Path = (
        Path(__file__).parent.parent.parent / "data" / "floodam" / "precompiled"
    ),
) -> _FloodamPrecompiled:
    """
    Read the precompiled Floodam files, checking their sha256 against the manifest.

    Parameters
    ----------
    precompiled_dir : str, default: None
        Directory holding the precompiled files and the sha256.txt manifest.

    Returns
    -------
    _FloodamPrecompiled
        Mapping of attribute name to the loaded object.

    """
    # precompiled file -> attribute name
    precompiled_files = {
        "a.nc": "a",
        "h.nc": "h",
        "p.nc": "p",
        "batisurf.nc": "batisurf",
        "stockemp.nc": "stockemp",
        "totalemp.nc": "totalemp",
        "seuilemp.csv": "seuilemp",
        "sirenemp.csv": "sirenemp",
        "ct.csv": "ct",
        "wext.nc": "wext",
        "wint.nc": "wint",
    }

    manifest_path = Path(precompiled_dir) / "sha256.txt"
    with Path(manifest_path).open() as f:
        manifest = {
            filename: digest
            for digest, filename in (line.split() for line in f if line.strip())
        }

    for filename in precompiled_files:
        digest = compute_file_sha256(Path(precompiled_dir) / filename)
        if digest != manifest[filename]:
            msg = (
                f"{filename} sha256 mismatch, "
                "rerun `uv run --script tools/format_floodam.py`"
            )
            raise RuntimeError(
                msg,
            )

    dirpath = Path(precompiled_dir)
    return {
        "a": read_netcdf(dirpath / "a.nc"),
        "h": read_netcdf(dirpath / "h.nc"),
        "p": read_netcdf(dirpath / "p.nc"),
        "batisurf": read_netcdf(dirpath / "batisurf.nc"),
        "stockemp": read_netcdf(dirpath / "stockemp.nc"),
        "totalemp": read_netcdf(dirpath / "totalemp.nc"),
        "seuilemp": pd.read_csv(dirpath / "seuilemp.csv", index_col=0),
        # sirenemp index holds strings like "00", "01" that pandas would
        # otherwise infer as ints (losing the leading zeros)
        "sirenemp": pd.read_csv(dirpath / "sirenemp.csv", index_col=0, dtype={0: str}),
        "ct": pd.read_csv(dirpath / "ct.csv", index_col=0),
        "wext": read_netcdf(dirpath / "wext.nc")["value"],
        "wint": read_netcdf(dirpath / "wint.nc")["value"],
    }


class Floodam:
    """
    Damage functions for flood damages in France.
    """

    def __init__(self) -> None:
        """
        Initialize the Floodam class.
        """
        # like "../data/floodam/"
        self.DATADIR = Path(__file__).parent.parent.parent / "data" / "floodam"

        data = _read_precompiled()
        self.a = data["a"]
        self.h = data["h"]
        self.p = data["p"]
        self.batisurf = data["batisurf"]
        self.stockemp = data["stockemp"]
        self.totalemp = data["totalemp"]
        self.seuilemp = data["seuilemp"]
        self.sirenemp = data["sirenemp"]
        self.ct = data["ct"]
        self.wext = data["wext"]
        self.wint = data["wint"]

        # > classes for a, h, p, c
        self.CLASSES = {
            "a": self._get_classes(self.a),
            "h": self._get_classes(self.h),
            "p": self._get_classes(self.p),
            "batisurf": self._get_classes(self.batisurf),
        }

    # PUBLIC FUNCS
    def get_dmg_agri_rpg(
        self,
        landcover: gpd.GeoDataFrame,
        hazard: xr.DataArray,
        season: FloodamSeason,
        classe_col: str,
    ) -> gpd.GeoDataFrame:
        """
        Get agriculture damages based on RPG data.
        """
        landcover = concat_hazard(landcover, hazard)

        # in case some nans
        landcover = asinstance(
            landcover.dropna(
                subset=list(HazardBand),
                how="any",
            ),
            gpd.GeoDataFrame,
        )

        landcover["dmg_per_m2"] = [
            self._get_dmg_agri(
                classe=row[classe_col],
                max_depth=row[HazardBand.max_depth],
                max_speed=row[HazardBand.max_speed],
                duration=row[HazardBand.duration],
                season=season,
            )
            for _, row in landcover.iterrows()
        ]

        # SURF_PARC is in ha = 10 000 m2, self.a.attrs["units"] gives meters
        landcover["dmg"] = landcover["dmg_per_m2"] * landcover["SURF_PARC"] * 10_000

        return asinstance(landcover, gpd.GeoDataFrame)

    def get_dmg_housing_bdtopo(
        self,
        lcv: gpd.GeoDataFrame,
        hzd: xr.DataArray,
        alea: FloodamAlea,
    ) -> gpd.GeoDataFrame:
        """
        Get housing damages based on BdTopo data.
        """
        usage1_col = find_column(lcv, "USAGE1", "usage_1")
        usage2_col = find_column(lcv, "USAGE2", "usage_2")
        etat_col = find_column(lcv, "ETAT", "etat_de_l_objet")
        nbfloors_col = find_column(lcv, "NB_ETAGES", "nombre_d_etages")
        nbhouses_col = find_column(lcv, "NB_LOGTS", "nombre_de_logements")
        # keep only houses
        lcv = asinstance(
            lcv[
                (lcv[usage1_col] == "Résidentiel") | (lcv[usage2_col] == "Résidentiel")
            ],
            gpd.GeoDataFrame,
        )
        # only keep buildings in service or under construction
        lcv = asinstance(
            lcv[(lcv[etat_col] == "En service") | (lcv[etat_col] == "En construction")],
            gpd.GeoDataFrame,
        )
        # for now not taking into account zmin/zmax

        def _get_classe(row: pd.Series) -> str | float:
            """
            Get the class of the building based on its usage.
            """
            nbfloors = row[nbfloors_col]
            nbhouses = row[nbhouses_col]

            if nbhouses == 1 and nbfloors == 1:
                return "ise"  # individuel sans étage
            if nbhouses == 1 and nbfloors > 1:
                return "iae"  # individuel avec étage
            if nbhouses > 1:
                return "col"  # collectif
            # some rows have 0 houses but > 0 floors, they are set to NaN
            return np.nan

        lcv = asinstance(
            lcv.dropna(subset=[nbfloors_col, nbhouses_col]), gpd.GeoDataFrame
        )
        lcv.loc[:, "classe"] = lcv.apply(_get_classe, axis=1)

        # drop NaN classes
        lcv = asinstance(lcv.dropna(subset=["classe"]), gpd.GeoDataFrame)

        # remove useless columns
        lcv = streamline(lcv, col2keep="classe", newcol="classe")

        # concat hazard without speed
        lcv = concat_hazard(lcv, hzd, use_max_speed=False)

        # add area of the building
        logger.info(
            "get_dmg_housing_bdtopo: be sure EPSG is projected, so area is in m2",
        )
        lcv["area"] = lcv["geometry"].area  # in m2

        # apply damage function
        lcv["dmg_per_m2"] = [
            self._get_dmg_housing(
                classe=row["classe"],
                max_depth=row[HazardBand.max_depth],
                duration=row[HazardBand.duration],
                alea=alea,
            )
            for _, row in lcv.iterrows()
        ]

        # finally, calculate the damage
        lcv["dmg"] = lcv["dmg_per_m2"] * lcv["area"]
        return lcv

    def get_dmg_commercial_standalone_sirene(
        self,
        lcv: gpd.GeoDataFrame,
        hzd: xr.DataArray,
        alea: FloodamAlea,
        *,
        return_minimum_price_if_above_thresh: bool,
    ) -> gpd.GeoDataFrame:
        """
        Get commercial damages based on Sirene data.

        Sirène data should be obtained after using
        misctools.geoDataFrames.read_sirene(sirene_path, epsg)

        We use here Sirene without any additional data, so the damage
        estimation is solely based on the NAF code and the TEFET
        (Tranche d'effectif), not on the surface or number of employees.
        This is a less robust approach and may not be as accurate.
        """
        lcv = asinstance(
            lcv[
                [
                    # https://www.sirene.fr/static-resources/documentation/v_sommaire_311.htm#27
                    "siret",
                    # """ La nomenclature en vigueur à la date de la mise en place de
                    # l API-Sirene utilise la Naf Rev.2 depuis le 01 Janvier 2008.
                    # Tous les etablissements actifs au 01/01/2008 ont eu leur code APE
                    # recode dans la nouvelle nomenclature [...] """
                    "activitePrincipaleEtablissement",  # naf
                    "nomenclatureActivitePrincipaleEtablissement",  # naf_type
                    "trancheEffectifsEtablissement",  # tefet au 31/12 à N-2
                    "etatAdministratifEtablissement",  # A = actif, F = fermé
                    "geometry",
                ]
            ],
            gpd.GeoDataFrame,
        )
        # renaming columns
        lcv.columns = [
            "siret",
            "naf",
            "naf_type",
            "tefet",
            "is_active",
            "geometry",
        ]
        lcv = asinstance(lcv, gpd.GeoDataFrame)
        # only keep active companies
        lcv["is_active"] = lcv["is_active"].map({"A": True, "F": False})
        lcv = asinstance(lcv.loc[lcv["is_active"]], gpd.GeoDataFrame)
        lcv = asinstance(lcv.drop("is_active", axis=1), gpd.GeoDataFrame)
        # check only NAFRef2 is available
        if not np.array_equal(np.unique(lcv["naf_type"]), np.array(["NAFRev2"])):
            msg = "Only NAFRev2 naf_type is supported"
            raise ValueError(msg)
        lcv = asinstance(lcv.drop("naf_type", axis=1), gpd.GeoDataFrame)
        # remove the dot in naf to match the floodam classes
        lcv["naf"] = lcv["naf"].astype(str).apply(lambda x: x.replace(".", ""))
        # concat_hazard
        lcv = concat_hazard(lcv, hzd, use_max_speed=False)
        # compute damages
        lcv["dmg"] = [
            self._get_dmg_commercial(
                naf=row["naf"],
                max_depth=row[HazardBand.max_depth],
                duration=row[HazardBand.duration],
                alea=alea,
                tefet=row["tefet"],
                return_minimum_price_if_above_thresh=return_minimum_price_if_above_thresh,
            )
            for _, row in lcv.iterrows()
        ]
        # remove NaNs
        return asinstance(lcv[~np.isnan(lcv["dmg"])], gpd.GeoDataFrame)

    def _check_if_str(self, var: object) -> None:
        if not isinstance(var, str):
            msg = "var is not a string"
            raise TypeError(msg)

    def _check_if_int_or_float(self, var: object) -> None:
        if not isinstance(var, (int, float)):
            msg = "var is not int or float"
            raise TypeError(msg)

    def _get_classes(self, ds: xr.Dataset) -> list[str]:
        # returns land cover classes
        return [str(k) for k in ds]

    def _get_dmg_agri(
        self,
        classe: str,
        max_depth: float,
        max_speed: float,
        duration: float,
        season: FloodamSeason,
    ) -> float:
        for var in [classe, season]:
            self._check_if_str(var)
        for var in [max_depth, max_speed, duration]:
            self._check_if_int_or_float(var)
        return float(
            self.a[classe]
            .sel(season=season)
            .sel(
                maxDepth=max_depth,
                maxSpeed=max_speed,
                duration=duration,
                method="nearest",
            )
            .to_numpy()
            .item()
        )

    def _get_dmg_housing(
        self,
        classe: str,
        max_depth: float,
        duration: float,
        alea: FloodamAlea,
    ) -> float:
        for var in [classe, alea]:
            self._check_if_str(var)
        for var in [max_depth, duration]:
            self._check_if_int_or_float(var)
        return float(
            self.h[classe]
            .sel(alea=alea)
            .sel(maxDepth=max_depth, duration=duration, method="nearest")
            .to_numpy()
            .item()
        )

    def _get_dmg_public(
        self,
        classe: str,
        max_depth: float,
        duration: float,
        alea: FloodamAlea,
    ) -> float:
        for var in [classe, alea]:
            self._check_if_str(var)
        for var in [max_depth, duration]:
            self._check_if_int_or_float(var)
        return float(
            self.p[classe]
            .sel(alea=alea)
            .sel(maxDepth=max_depth, duration=duration, method="nearest")
            .to_numpy()
            .item()
        )

    def _get_dmg_commercial(  # noqa: C901, PLR0911, PLR0912, PLR0913
        self,
        naf: str | None = None,
        max_depth: float | None = None,
        duration: float | None = None,
        alea: FloodamAlea | None = None,
        surface: float | None = None,
        n_emp: float | None = None,
        tefet: str | None = None,
        siret: str | None = None,
        *,
        return_minimum_price_if_above_thresh: bool = False,
    ) -> float:
        for var in [naf, alea]:
            self._check_if_str(var)
        for var in [max_depth, duration]:
            self._check_if_int_or_float(var)
        naf = require(naf)
        alea = require(alea)
        max_depth = require(max_depth)
        duration = require(duration)

        if n_emp is not None:
            self._check_if_int_or_float(n_emp)
        if surface is not None:
            self._check_if_int_or_float(surface)

        # check if naf is available
        # check only one since _get_classes(batisurf)
        # == _get_classes(stockemp) == _get_classes(totalemp)
        if naf in self._get_classes(self.batisurf):

            def __getdmg(ds: xr.Dataset) -> float:
                return float(
                    ds[naf]
                    .sel(alea=alea)
                    .sel(maxDepth=max_depth, duration=duration, method="nearest")
                    .to_numpy()
                    .item()
                )

            # if no number of employees provided,
            # then use sirenemp given a tefet
            # (tefet = "tranche effective etablissement")
            def __get_n_emp_from_tefet(tefet: str) -> float:
                try:
                    return float(self.sirenemp.loc[tefet, "valeur.employe"])
                except KeyError:
                    # usually if np.nan or 'NN', see notice
                    # "il est considéré" que tout établissement correspond
                    # au moins à un emploi."
                    return 1

            if n_emp is None:
                n_emp = __get_n_emp_from_tefet(require(tefet))

            # pour description des méthodes, voir feuille 'notice' de fc.xlsx/mc.xlsx
            if surface is not None:
                # methode 1 : recommandée
                dmgbuild = __getdmg(self.batisurf) * surface
                dmgstock = __getdmg(self.stockemp) * n_emp
                return dmgbuild + dmgstock

            # méthode 2: unknown building surface
            # dmg directly using totalemp
            # if we use this method, have to check
            # that it is not above or equal an employee threshold
            tefet_threshold = str(self.seuilemp.loc[naf, "seuil.001.5"])
            n_emp_threshold = __get_n_emp_from_tefet(tefet_threshold)
            if n_emp >= n_emp_threshold:
                logger.debug(
                    "Alternative method for siret %s showed 'n_emp >= n_emp_threshold'",
                    siret,
                )
                # """S il est atteint, les dommages attendus par l enjeu
                # sont potentiellement supérieurs à 1,5 millions €.
                # Il est nécessaire alors de mobiliser la méthode recommandée, en
                # passant par une analyse plus détaillée de l enjeu permettant
                # de préciser la surface du ou des bâtiments."""
                if return_minimum_price_if_above_thresh:
                    logger.debug(
                        "More in depth analyses are needed, "
                        "setting a minimal value of 1.5M€",
                    )
                    return 1_500_000
                logger.debug(
                    "More in depth analyses are needed, setting value to nan",
                )
                return np.nan
            return __getdmg(self.totalemp) * n_emp

        # if naf not available, try correspondance table
        if naf in self.ct.index:
            functype, classe = (
                self.ct.loc[naf, "functype"],
                self.ct.loc[naf, "classe"],
            )
            match functype:
                case "p":
                    return self._get_dmg_public(
                        classe=classe,
                        max_depth=max_depth,  # in m for both c and p
                        duration=duration,  # in seconds for both c and p
                        alea=alea,
                    )
                case "c":
                    return self._get_dmg_commercial(
                        naf=classe,
                        max_depth=max_depth,
                        duration=duration,
                        alea=alea,
                        surface=surface,
                        n_emp=n_emp,
                        tefet=tefet,
                    )
                case "WIP":
                    logger.info("skipping naf %s, still need to process fw.xls", naf)
                    return np.nan
                case _:
                    msg = "neither c nor p"
                    raise ValueError(msg)
        # if no damage at all
        else:
            logger.debug(
                "Skipping unknown naf %s or unavailable dammage for this naf",
                naf,
            )
            return np.nan
