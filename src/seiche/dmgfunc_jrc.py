"""
JRC class.
"""

import logging
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import xarray as xr

from seiche.utils_da import da_from_array
from seiche.utils_enum import HazardBand, HciMode, JrcClass, JrcRegion
from seiche.utils_gdf import concat_hazard, streamline
from seiche.utils_qol import asinstance, check_sha256_manifest

logger = logging.getLogger(__name__)

A3_CODE_LEN = 3
N_UNIQUE_VALUES_SINGLE_CLASS = 2


def _read_precompiled(
    precompiled_dir: str | Path = (
        Path(__file__).parent.parent.parent / "data" / "jrc" / "precompiled"
    ),
) -> dict[str, pd.DataFrame]:
    """
    Read the precompiled JRC CSVs, checking their sha256 against the manifest.

    Parameters
    ----------
    precompiled_dir : str, default: None
        Directory holding the precompiled CSVs and the sha256.txt manifest.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping of attribute name to the loaded dataframe.

    """
    # precompiled csv -> attribute name
    precompiled_files = {
        "dmgfac.csv": "_dmgfac",
        "hmaxdmg.csv": "_hmaxdmg",
        "cmaxdmg.csv": "_cmaxdmg",
        "imaxdmg.csv": "_imaxdmg",
        "tmaxdmg.csv": "_tmaxdmg",
        "rmaxdmg.csv": "_rmaxdmg",
        "amaxdmg.csv": "_amaxdmg",
    }

    check_sha256_manifest(
        precompiled_dir,
        precompiled_files,
        rerun_hint="`uv run --script tools/format_jrc.py`",
    )

    return {
        attr: pd.read_csv(Path(precompiled_dir) / filename, index_col=0)
        for filename, attr in precompiled_files.items()
    }


class JRC:
    """
    Global damage functions from the JRC.

    Source: Joint Research Centre of the European Commission.
    """

    def __init__(self) -> None:
        """
        Initialize the JRC class.
        """
        self.CLASSES = list(JrcClass)
        self.REGIONS = list(JrcRegion)

        data = _read_precompiled()
        self._dmgfac = data["_dmgfac"]
        self._hmaxdmg = data["_hmaxdmg"]
        self._cmaxdmg = data["_cmaxdmg"]
        self._imaxdmg = data["_imaxdmg"]
        self._tmaxdmg = data["_tmaxdmg"]
        self._rmaxdmg = data["_rmaxdmg"]
        self._amaxdmg = data["_amaxdmg"]

    #
    # =========================================================================
    # Public methods
    # =========================================================================
    #
    def get_dmg_fac_vector_lc(
        self,
        landcover: gpd.GeoDataFrame,
        # max_depth: xr.DataArray,
        hazard: xr.DataArray,
        col2keep: str,
        map_jrc: dict[int, list[float]],
        region: JrcRegion,
    ) -> gpd.GeoDataFrame:
        """
        Get Damage Factor for Vector Land Cover.

        Parameters
        ----------
        landcover : gpd.GeoDataFrame
            desc

        hazard : xr.DataArray
            desc

        col2keep : str
            Name of the column in the landcover GeoDataFrame to consider as the
            landcover class. (see maps.py)

        map_jrc : dict
            Maps landcover codes to their damage distribution across the JRC damage
            function classes (see maps.py).

        region : JrcRegion
            desc

        Returns
        -------
        gpd.GeoDataFrame
            desc

        """
        # match data
        # do this elsewhere and call a function
        landcover = asinstance(landcover.copy(), gpd.GeoDataFrame)
        landcover.to_crs(epsg=hazard.rio.crs.to_epsg(), inplace=True)
        bbox_poly = shapely.box(*landcover.total_bounds).intersection(
            shapely.box(*hazard.rio.bounds())
        )
        if bbox_poly.is_empty:
            msg = "landcover and hazard bounding boxes do not intersect"
            raise ValueError(msg)
        bbox = bbox_poly.bounds
        landcover = asinstance(landcover.clip(bbox), gpd.GeoDataFrame)
        hazard = asinstance(hazard.rio.clip_box(*bbox), xr.DataArray)
        # only keep the columns we need: index, geometry, class
        landcover = streamline(landcover, col2keep)
        # add 4th/5th/6th column: max_depth, max_speed, duration
        landcover = concat_hazard(landcover, hazard)
        # add 7th column: classVector
        landcover["classVector"] = landcover["class"].map(map_jrc)
        # computing damages by iterating on classes
        for classe, class_vector in map_jrc.items():
            mask = landcover["class"] == classe
            if not mask.any():
                continue
            get_dmg, get_std = self._get_dmgfac_vector_interpolators(
                class_vector=class_vector,
                region=region,
            )
            landcover.loc[mask, "dmg"] = get_dmg(
                landcover.loc[mask, HazardBand.max_depth]
            )
            landcover.loc[mask, "std"] = get_std(
                landcover.loc[mask, HazardBand.max_depth]
            )
        return landcover

    def get_dmg_fac_raster_lc(
        self,
        landcover: xr.DataArray,
        max_depth: xr.DataArray,
        map_jrc: dict[int, list[float]],
        region: JrcRegion,
    ) -> tuple[xr.DataArray, xr.DataArray]:
        """
        Get Damage Factor for Raster Land Cover.

        Parameters
        ----------
        landcover : xr.DataArray
            desc

        max_depth: xr.DataArray
            desc

        map_jrc : dict
            Maps landcover codes to their damage distribution across the JRC damage
            function classes (see maps.py).

        region : JrcRegion
            desc

        Returns
        -------
        dmgs : xr.DataArray
            desc

        stds : xr.DataArray
            desc

        """
        landcover = landcover.copy()
        # ---
        hmax = max_depth.rio.reproject_match(landcover).to_numpy()
        dmgs = np.full_like(hmax, np.nan)
        stds = np.full_like(hmax, np.nan)
        # ---
        for code, class_vector in map_jrc.items():
            mask = landcover.to_numpy() == code
            if not mask.any():
                continue
            get_dmg, get_std = self._get_dmgfac_vector_interpolators(
                class_vector=class_vector,
                region=region,
            )
            dmgs[mask] = get_dmg(hmax[mask])
            stds[mask] = get_std(hmax[mask])
        # ---
        dmgs = da_from_array(dmgs, other_da=landcover)
        stds = da_from_array(stds, other_da=landcover)
        return dmgs, stds

    def get_max_dmg_raster_lc(
        self,
        landcover: xr.DataArray,
        map_jrc: dict[int, list[float]],
        a3: str,
        hci_mode: HciMode = HciMode.landuse,
    ) -> xr.DataArray:
        """
        Get maximum damages for raster land cover.

        Parameters
        ----------
        landcover : xr.DataArray
            desc

        map_jrc : dict
            Maps landcover codes to their damage distribution across the JRC damage
            function classes (see maps.py).

        a3 : str
            desc

        hci_mode : HciMode
            desc

        """
        landcover = landcover.copy()
        maxdmgs = np.full(landcover.shape, np.nan, dtype=float)
        # ---
        # CONVERT TO € PER PIXEL AND BE CAREFUL
        # WITH €/HA VS €/M2
        # ---
        for code, class_vector in map_jrc.items():
            mask = landcover.to_numpy() == code
            if not mask.any():
                continue

            maxdmgs[mask] = self._get_maxdmg_vector(
                a3=a3,
                class_vector=class_vector,
                hci_mode=hci_mode,
            )
        # ---
        return da_from_array(maxdmgs, other_da=landcover)

    #
    # =========================================================================
    # Private methods
    # =========================================================================
    #
    def _get_dmgfac_classe_interpolators(
        self, classe: JrcClass | str, region: JrcRegion
    ) -> list[Callable[..., float]]:
        """
        Return interpolators for the damage factor and std deviation for a classe.
        """
        if classe not in self.CLASSES:
            msg = "CLASSE INVALID"
            raise ValueError(msg)
        # Gathering reference depth
        refdepth = (
            self._dmgfac[self._dmgfac.index == classe]["depth"].to_numpy().tolist()
        )

        def getvals(col: str) -> list[float]:
            return list(
                self._dmgfac[self._dmgfac.index == classe][col].to_numpy().astype(float)
            )

        try:
            dmg = getvals(f"dmg{region.upper()}")
        except (KeyError, ValueError):
            # if no regional damage factor, use global one
            dmg = getvals("dmgGL")

        try:
            std = getvals(f"std{region.upper()}")
        except (KeyError, ValueError):
            # there is no global standard deviation, so if no data, no data :(
            std = [np.nan] * len(self._dmgfac[self._dmgfac.index == classe])
        # return two lambda interpolator functions
        return [
            lambda depth: np.interp(depth, refdepth, dmg),
            lambda depth: np.interp(depth, refdepth, std),
        ]

    def _get_dmgfac_vector_interpolators(
        self,
        class_vector: np.ndarray | list[float],
        region: JrcRegion,
    ) -> list[Callable[..., float]]:
        """
        Return interpolators for damage factor and std deviation from class_vector.

        Given a class vector (a1, a2, a3, a4, a5, a6) and a region,
        return two lambda functions that will return the damage factor
        and the standard deviation for a given depth (in m).

        The class vector should be of shape (6,) and contain the
        coefficients for each class (h, c, i, t, r, a) IN THIS ORDER.
        The coefficients should be >= 0, since it does not make sense
        to have a negative damage factor.

        Check JRC.CLASSES and JRC.REGIONS for authorized values.

        Returns a linear combination of the estimated damage factors
        of each corresponding class scaled by the coefficients a1 to a6.

        Same is true for the standard deviation. But it is not a linear
        operator, so this will have to change in the future !!!
        """
        if type(class_vector) is list:
            class_vector = np.array(class_vector)
        class_vector = asinstance(class_vector, np.ndarray)

        if class_vector.shape != (len(self.CLASSES),):
            msg = (
                f"class vector should be of shape "
                f"({len(self.CLASSES)},) = {self.CLASSES}"
            )
            raise ValueError(msg)

        if not all(class_vector >= 0):
            msg = f"class vector values should be >= 0but got {class_vector}"
            raise ValueError(msg)

        # if all classes are 0, return 0
        if np.array_equal(class_vector, np.zeros((6,))):
            return [lambda _: 0, lambda _: 0]
        # if one damage func correspond to one landcover type
        # np.unique(np.array([0,0,x,0,0,0])) = (0, x) if x > 0
        if len(np.unique(class_vector)) == N_UNIQUE_VALUES_SINGLE_CLASS:
            _, index = np.unique(
                class_vector,
                return_index=True,
            )  # index[1] gives the position of the non 0 coef if x>0
            return self._get_dmgfac_classe_interpolators(
                classe=self.CLASSES[index[1]],
                region=region,
            )
        # if class_vector has a random shape
        interpolators = [
            self._get_dmgfac_classe_interpolators(classe, region)
            for classe in self.CLASSES
        ]
        dmg_interp = [i[0] for i in interpolators]
        std_interp = [i[1] for i in interpolators]
        # TO DO CHECK : std(linear combination) = linear combination(std)
        # UPDATE: i think not .. TODO: change this
        # if class_vector[i]!=0 else 0 : not interpolate if going to be
        # set to 0 afterwards
        # the linear combination must stay array-safe: sum() broadcasts over
        # scalar and array depths alike (np.array([...]).dot() is ragged
        # and fails when the interpolators return arrays)
        return [
            lambda depth: sum(
                dmg_interp[i](depth) * class_vector[i]
                for i in range(6)
                if class_vector[i] != 0
            ),
            lambda depth: sum(
                std_interp[i](depth) * class_vector[i]
                for i in range(6)
                if class_vector[i] != 0
            ),
        ]

    def _get_maxdmg_classe(  # noqa: C901, PLR0911, PLR0912
        self,
        a3: str,
        classe: JrcClass | str,
        hci_mode: HciMode = HciMode.landuse,
    ) -> float:
        if len(a3) != A3_CODE_LEN:
            msg = "for now only a3 country codes"
            raise ValueError(msg)
        a3 = a3.upper()  # capitalize every letters

        if classe not in self.CLASSES:
            msg = f"invalid classe {classe}"
            raise ValueError(msg)

        def getval(df: pd.DataFrame, a3: str, col: str) -> float:
            """
            Return the value of columns 'col' for the row matching a3.

            Given a dataframe df that has "a3" as col but not index,
            also, it should only return one row.
            """
            return float(df[df["a3"] == a3][col].to_numpy().tolist()[0])

        match (classe, hci_mode):
            case (JrcClass.h, HciMode.building):
                return getval(self._hmaxdmg, a3, "building-total")
            case (JrcClass.h, HciMode.landuse):
                return getval(self._hmaxdmg, a3, "landuse-total")
            case (JrcClass.h, HciMode.object):
                return getval(self._hmaxdmg, a3, "object-total")

            case (JrcClass.c, HciMode.building):
                return getval(self._cmaxdmg, a3, "building-total")
            case (JrcClass.c, HciMode.landuse):
                return getval(self._cmaxdmg, a3, "landuse-total")
            case (JrcClass.c, HciMode.object):
                return getval(self._cmaxdmg, a3, "object-total")

            case (JrcClass.i, HciMode.building):
                return getval(self._imaxdmg, a3, "building-total")
            case (JrcClass.i, HciMode.landuse):
                return getval(self._imaxdmg, a3, "landuse-total")
            case (JrcClass.i, HciMode.object):
                return getval(self._imaxdmg, a3, "object-total")

            case (JrcClass.t, _):
                return getval(self._tmaxdmg, a3, "maxdmg")
            case (JrcClass.r, _):
                return getval(self._rmaxdmg, a3, "maxdmg")
            case (JrcClass.a, _):
                return getval(self._amaxdmg, a3, "maxdmg")
            case _:  # pragma: no cover - unreachable, inputs are validated above
                msg = "shouldnt be possible to have this error"
                raise ValueError(msg)

    def _get_maxdmg_vector(
        self,
        a3: str,
        class_vector: np.ndarray | list[float],
        hci_mode: HciMode = HciMode.landuse,
    ) -> float:
        # if all classes are 0, return 0
        if np.array_equal(class_vector, np.zeros((6,))):
            return 0
        # if one damage func correspond to one landcover type
        # np.unique(np.array([0,0,x,0,0,0])) = (0, x) if x > 0
        if len(np.unique(class_vector)) == N_UNIQUE_VALUES_SINGLE_CLASS:
            _, index = np.unique(
                class_vector,
                return_index=True,
            )  # index[1] gives the position of the non 0 coef if x>0
            return self._get_maxdmg_classe(a3, self.CLASSES[index[1]], hci_mode)
        # if class_vector has a random shape
        # get maxdmg per each class
        maxdmgs = [
            self._get_maxdmg_classe(a3, classe, hci_mode) for classe in self.CLASSES
        ]
        # multiply by vector coef
        maxdmgs *= np.array(class_vector)
        # return the mean
        return float(np.mean(maxdmgs))
