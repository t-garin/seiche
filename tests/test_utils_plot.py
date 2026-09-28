"""
Tests for the plotting utilities.
"""

import matplotlib.colors as mcolors
import pytest

from generate_synthetic_data import load_test_data

from seiche.utils_plot import Colors

HEX_CMAPS = load_test_data("test_utils_plot_data.yml", "hex_colormaps")


@pytest.mark.parametrize("key", list(HEX_CMAPS))
def test_colormaps_exist(key: str) -> None:
    """Each color key produces a listed colormap."""
    assert isinstance(getattr(Colors, f"{key}_list"), mcolors.ListedColormap)


@pytest.mark.parametrize("key", list(HEX_CMAPS))
def test_listed_colormap_matches_hex(key: str) -> None:
    """Listed colormaps sample the pinned hex colors exactly."""
    listed = getattr(Colors, f"{key}_list")
    assert [mcolors.to_hex(color).lower() for color in listed.colors] == [
        color.lower() for color in HEX_CMAPS[key]
    ]
