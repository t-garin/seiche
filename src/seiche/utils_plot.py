"""
Docstring for utils_plot.
"""

from typing import Any

import matplotlib.colors as mcolors


class _Colors:
    """
    Useful API for color stuff.

    Should be accessed through the Colors object, not the _Colors class,
    since it needs to be instanciated to automatically generate the attributes.

    There is maybe a prettier way of doing this, but it works just fine!

    """

    esawc_list: mcolors.ListedColormap
    oso23_list: mcolors.ListedColormap
    rpg_code_group_list: mcolors.ListedColormap

    def __init__(self) -> None:
        """
        Automatically generate a listed colormap for each color key.

        ```
        Colors.*_list -> mcolors.ListedColormap
        ```
        """
        self.hex_colormaps = {
            "esawc": [
                "#00A000",  # 10 Tree cover
                "#966400",  # 20 Shrubland
                "#FFB400",  # 30 Grassland
                "#FFFF64",  # 40 Cropland
                "#C31400",  # 50 Built-up
                "#FFF5D7",  # 60 Bare / sparse vegetation
                "#FFFFFF",  # 70 Snow and ice
                "#0046C8",  # 80 Permanent water bodies
                "#00DC82",  # 90 Herbaceous wetland
                "#009678",  # 95 Mangroves
                "#FFEBAF",  # 100 Moss and lichen
            ],
            "oso23": [
                "#ff00ff",  # 1 Urbain dense
                "#ff55ff",  # 2 Urbain diffus
                "#ffaaff",  # 3 Zones industrielles et commerciales
                "#00ffff",  # 4 Routes
                "#ffff00",  # 5 Colza
                "#d0ff00",  # 6 Céréales à paille
                "#a1d600",  # 7 Protéagineux
                "#ffaa44",  # 8 Soja
                "#d6d600",  # 9 Tournesol
                "#ff5500",  # 10 Maïs
                "#c5ffff",  # 11 Riz
                "#aaaa61",  # 12 Tubercules / Racines
                "#aaaa00",  # 13 Prairies
                "#aaaaff",  # 14 Vergers
                "#550000",  # 15 Vignes
                "#009c00",  # 16 Forêts de feuillus
                "#003200",  # 17 Forêts de conifères
                "#aaff00",  # 18 Pelouse
                "#55aa7f",  # 19 Landes
                "#ff0000",  # 20 Surfaces minérales
                "#ffb802",  # 21 Plages et Dunes
                "#bebebe",  # 22 Glaciers et neiges éternelles
                "#0000ff",  # 23 Eau
                # for now i only considered 23 classes,
                # and there seems to be a new 24th now ???
                # need to check further
                # "#4479c8", #24 Serres
            ],
            "rpg_code_group": [
                # no official color, made using extract_hex_from_mpl_cmap
                "#ffffe5",  # 1. Blé tendre
                "#fff7bc",  # 2. Maïs grain et ensilage
                "#fee391",  # 3. Orge
                "#fec44f",  # 4. Autres céréales
                "#fe9929",  # 5. Colza
                "#ec7014",  # 6. Tournesol
                "#cc4c02",  # 7. Autres oléagineux
                "#993404",  # 8. Protéagineux
                "#662506",  # 9. Plantes à fibre
                "#000000",  # 10. ???
                "#6baed6",  # 11. Gel
                "#000000",  # 12. ???
                "#000000",  # 13. ???
                "#dbf1d5",  # 14. Riz
                "#aedea7",  # 15. Légumineuses à grain
                "#74c476",  # 16. Fourrage
                "#37a055",  # 17. Estives et landes
                "#0c7734",  # 18. Prairies permanentes
                "#00441b",  # 19. Prairies temporaires
                "#dadaeb",  # 20. Vergers
                "#9e9ac8",  # 21. Vignes
                "#6a51a3",  # 22. Fruits à coques
                "#3f007d",  # 23. Oliviers
                "#bfbfbf",  # 24. Autres cultures industrielles
                "#808080",  # 25. Légumes ou fleurs
                "#404040",  # 26. Canne à sucre
                "#000000",  # 27. ???
                "#FF00FF",  # 28. Divers
            ],
        }

        for key in self.hex_colormaps:
            setattr(self, f"{key}_list", self._get_listed_colormap(key))

    def _get_listed_colormap(self, key: str) -> mcolors.ListedColormap:
        """
        Return the listed colormap for the given hex color key.
        """
        colors = [mcolors.to_rgb(color) for color in self.hex_colormaps[key]]
        return mcolors.ListedColormap(colors=colors, name=key)


class _HvOpts:
    """
    Options for when plotting with hvplot.

    https://hvplot.holoviz.org/en/docs/latest/ref/plotting_options/index.html
    """

    @property
    def basic_rxr_nogeo(self) -> dict[str, Any]:
        """
        Desc.
        """
        return {
            "x": "x",
            "y": "y",
            "data_aspect": 1,
            "xaxis": None,
            "yaxis": None,
            "height": 1000,
            "width": 1000,
            "fontscale": 2,
            "use_dask": True,
            "title": "",
            "clabel": "",
        }

    @property
    def basic_rxr(self) -> dict[str, Any]:
        """
        Basic plot kwargs for a 2D slice of a rxr-born xr.DataArray.
        """
        return {"geo": True, "project": True, **self.basic_rxr_nogeo}


Colors = _Colors()
HvOpts = _HvOpts()
