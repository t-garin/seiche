"""
Shared string enums for the SEICHE pipeline.
"""

from enum import StrEnum, auto
from pathlib import Path
from typing import Any

from seiche.utils_qol import asinstance

Landcover = StrEnum("Landcover", "bdtopo, esawc, oso23, rpg, sirene")
Landcover.__doc__ = "Land cover input datasets."

LandcoverType = StrEnum("LandcoverType", "raster, vector")
LandcoverType.__doc__ = "Raster or vector land cover representation."

DamageFunc = StrEnum("DamageFunc", "jrc, floodam")
DamageFunc.__doc__ = "Damage functions applied to the hazards."

HazardSource = StrEnum("HazardSource", "slf, bfm")
HazardSource.__doc__ = "Hazard sources."

PopDataset = StrEnum("PopDataset", "filosofi, ghslpop")
PopDataset.__doc__ = "Population datasets."


class OutputFiles(StrEnum):
    """
    Output files produced by the pipeline.

    Members carry ``filename`` and ``savepath`` methods resolving their file
    name (and full path) from the SEICHE state and their variable parts.
    """

    dem = auto()
    hzd = auto()
    duration = auto()
    lcv = auto()
    dmgfac = auto()
    maxdmg = auto()
    dmg = auto()
    std = auto()
    ghslpop = auto()
    filosofi = auto()
    report = auto()

    def filename(self, state: dict[str, Any], **parts: object) -> str:
        """
        Return the file name of this output, given the state and variable parts.

        Parameters
        ----------
        state : dict
            The whole SEICHE state.
        **parts : object
            The variable parts of the name as keyword arguments: ``nickname``
            for ``hzd``, ``ext``/``landcover`` for ``lcv``, ``nickname`` and
            ``landcover`` for the dmg outputs, ``nickname`` and ``condition``
            for the pop outputs, ``ext`` for ``report``.

        Returns
        -------
        str
            The file name, e.g. ``dmg_slf1_esawc_marmande_2019.gpkg``.

        """
        from seiche.utils_state import read_expname_from_state  # noqa: PLC0415

        return _TEMPLATES[self].format(expname=read_expname_from_state(state), **parts)

    def savepath(self, state: dict[str, Any], **parts: object) -> Path:
        """
        Return the full output path, i.e. ``path.out`` joined to ``filename``.
        """
        out = asinstance(state["config"]["path.out"], str)
        return Path(out) / self.filename(state, **parts)


HciMode = StrEnum("HciMode", "building, landuse, object")
HciMode.__doc__ = "JRC max damage aggregation mode (h, c, i classes)."

JrcClass = StrEnum("JrcClass", "h, c, i, t, r, a")
JrcClass.__doc__ = "JRC damage classes (h, c, i, t, r, a)."

SimpleMethod = StrEnum("SimpleMethod", "all, each")
SimpleMethod.__doc__ = "Water depth estimation mode for simple methods."

DefendedMethod = StrEnum(
    "DefendedMethod",
    "simple_a, simple_e, fwdet_n, fwdet_l, fwdet_c, hand_a, hand_e",
)
DefendedMethod.__doc__ = "Available defended depth estimation methods."

JrcRegion = StrEnum("JrcRegion", "eu, na, sa, as, af, oc, gl")
JrcRegion.__doc__ = "JRC damage function regions."

FloodamAlea = StrEnum("FloodamAlea", "fluvial, maritime")
FloodamAlea.__doc__ = "Floodam hazard types."

FloodamSeason = StrEnum("FloodamSeason", "automne, hiver, printemps, été")
FloodamSeason.__doc__ = "Floodam agricultural seasons."


class HazardBand(StrEnum):
    """
    Bands of a hazard raster.

    Values double as column names, ``band_index`` is the band position
    (0: max_depth, 1: max_speed, 2: duration).
    """

    max_depth = auto()
    max_speed = auto()
    duration = auto()

    @property
    def band_index(self) -> int:
        """
        Return the band position in the hazard raster.
        """
        return list(HazardBand).index(self)


_TEMPLATES: dict[OutputFiles, str] = {
    OutputFiles.dem: "dem_{expname}.tif",
    OutputFiles.duration: "duration_{expname}.tif",
    OutputFiles.hzd: "hzd_{nickname}_{expname}.tif",
    OutputFiles.lcv: "lcv_{landcover}_{expname}.{ext}",
    OutputFiles.dmgfac: "dmgfac_{nickname}_{landcover}_{expname}.tif",
    OutputFiles.maxdmg: "maxdmg_{nickname}_{landcover}_{expname}.tif",
    OutputFiles.std: "std_{nickname}_{landcover}_{expname}.tif",
    OutputFiles.dmg: "dmg_{nickname}_{landcover}_{expname}.gpkg",
    OutputFiles.ghslpop: "ghslpop_{nickname}_{condition}_{expname}.tif",
    OutputFiles.filosofi: "filosofi_{nickname}_{condition}_{expname}.gpkg",
    OutputFiles.report: "report_{expname}.{ext}",
}
