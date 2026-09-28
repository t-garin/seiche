"""
Dead code moved out of ``src/seiche/utils_plot.py``.

- ``extract_hex_from_mpl_cmap`` was only exercised by unit tests.
- The gradient machinery (``_get_gradient`` / ``_get_listed_colormap`` with
  ``nelem``) and the ``*_grad`` colormaps were never used by the pipeline.
- The ``GarinBlue``, ``pan``, ``bi`` and ``rainbow`` palettes were unused.

Kept here as reference, can be re-integrated if needed.
"""

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

HEX_COLORS = {
    # Someone from our lab hated this blue from one of my posters
    # So it became a joke with my coworker Camille, now it's mine
    "GarinBlue": "#2171b5",
}

HEX_COLORMAPS = {
    "pan": ["#FF218C", "#FFD800", "#21B1FF"],
    "bi": ["#D60270", "#9B4F96", "#0038A8"],
    "rainbow": [
        "#FF0000",
        "#FFA500",
        "#FFFF00",
        "#008000",
        "#0000FF",
        "#4B0082",
        "#EE82EE",
    ],
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


def extract_hex_from_mpl_cmap(cmap_name: str, n_colors: int) -> list[str]:
    """
    Extract hex color codes from a given matplotlib colormap.

    Parameters
    ----------
    cmap_name : str
        The name of the colormap.

    n_colors : int
        The number of colors to extract.

    Returns
    -------
    list[str]
        A list of hex color codes.

    """
    # Get the colormap
    cmap = plt.get_cmap(cmap_name, n_colors)

    # Extract the colors and convert to hex
    return [mcolors.to_hex(color) for color in (cmap(i) for i in range(n_colors))]


def get_gradient(
    hex_colormaps: dict[str, list[str]], key: str
) -> mcolors.LinearSegmentedColormap:
    """
    Former ``_Colors._get_gradient``.
    """
    return mcolors.LinearSegmentedColormap.from_list(
        colors=[mcolors.to_rgb(color) for color in hex_colormaps[key]],
        name=key,
    )


def get_listed_colormap(
    hex_colormaps: dict[str, list[str]],
    key: str,
    nelem: int | None = None,
) -> mcolors.ListedColormap:
    """
    Former ``_Colors._get_listed_colormap``.

    If ``nelem`` is None, return the original hex_colormaps elements.
    Otherwise, create a gradient from hex_colormaps, and then sample nelem
    evenly spaced points.
    """
    if nelem is None:
        colors = [mcolors.to_rgb(color) for color in hex_colormaps[key]]
    else:
        colors = get_gradient(hex_colormaps, key)(np.linspace(0, 1, nelem))

    return mcolors.ListedColormap(colors=colors, name=key)
