"""
Tests for DEFENDED.

For every (DEM, WET) pair and every DEFENDED method, compare the
computed water depth to an expected snapshot stored in
tests/test_defended_data.yml with np.testing.assert_allclose. Snapshots are
compiled once from the reference implementation and pinned there so any
behaviour change is caught.
"""


import numpy as np
import pytest
import yaml

from generate_synthetic_data import synthetic_dem, synthetic_wet_mask

from seiche.defended import defended
from seiche.utils_enum import DefendedMethod

with open("tests/test_defended_data.yml") as f:
    EXPECTED = yaml.safe_load(f)

DEM_1 = synthetic_dem(seed=1312)
DEM_2 = synthetic_dem(seed=6769)
DEM_3 = synthetic_dem(seed=5040)

WET_1S = synthetic_wet_mask(DEM_1, "threshold", "small", water_level=25)
WET_1L = synthetic_wet_mask(DEM_1, "threshold", "large", water_level=60)
WET_1B_S = synthetic_wet_mask(DEM_1, "blob", "small", fraction=0.3, seed=1312)
WET_1B_L = synthetic_wet_mask(DEM_1, "blob", "large", fraction=0.6, seed=1312)
WET_1R = synthetic_wet_mask(DEM_1, "random", "small", fraction=0.3, seed=1312)

WET_2S = synthetic_wet_mask(DEM_2, "threshold", "small", water_level=25)
WET_2L = synthetic_wet_mask(DEM_2, "threshold", "large", water_level=60)
WET_2B_S = synthetic_wet_mask(DEM_2, "blob", "small", fraction=0.3, seed=6769)
WET_2B_L = synthetic_wet_mask(DEM_2, "blob", "large", fraction=0.6, seed=6769)
WET_2R = synthetic_wet_mask(DEM_2, "random", "small", fraction=0.3, seed=6769)

WET_3S = synthetic_wet_mask(DEM_3, "threshold", "small", water_level=25)
WET_3L = synthetic_wet_mask(DEM_3, "threshold", "large", water_level=60)
WET_3B_S = synthetic_wet_mask(DEM_3, "blob", "small", fraction=0.3, seed=5040)
WET_3B_L = synthetic_wet_mask(DEM_3, "blob", "large", fraction=0.6, seed=5040)
WET_3R = synthetic_wet_mask(DEM_3, "random", "small", fraction=0.3, seed=5040)

METHODS = tuple(DefendedMethod)

HAND_THRESHOLD = 10  # meaningful for the synthetic 10x10 DEMs (max accumulation ~50)

CASES = (
    ("DEM_1", DEM_1, "WET_1S", WET_1S),
    ("DEM_1", DEM_1, "WET_1L", WET_1L),
    ("DEM_1", DEM_1, "WET_1B_S", WET_1B_S),
    ("DEM_1", DEM_1, "WET_1B_L", WET_1B_L),
    ("DEM_1", DEM_1, "WET_1R", WET_1R),
    ("DEM_2", DEM_2, "WET_2S", WET_2S),
    ("DEM_2", DEM_2, "WET_2L", WET_2L),
    ("DEM_2", DEM_2, "WET_2B_S", WET_2B_S),
    ("DEM_2", DEM_2, "WET_2B_L", WET_2B_L),
    ("DEM_2", DEM_2, "WET_2R", WET_2R),
    ("DEM_3", DEM_3, "WET_3S", WET_3S),
    ("DEM_3", DEM_3, "WET_3L", WET_3L),
    ("DEM_3", DEM_3, "WET_3B_S", WET_3B_S),
    ("DEM_3", DEM_3, "WET_3B_L", WET_3B_L),
    ("DEM_3", DEM_3, "WET_3R", WET_3R),
)


def _params():
    """Yield (id, (dem, wet_mask, method, expected)) for every combination."""
    for dem_name, dem, mask_name, mask in CASES:
        for method in METHODS:
            key = f"{mask_name}_{method}"
            case_id = f"{dem_name}-{mask_name}-{method}"
            yield case_id, (dem, mask, method, _decode(EXPECTED[key]))


def _decode(s):
    """Parse a flat space-joined snapshot string into a 2D float array."""
    arr = np.fromstring(s, sep=" ")
    return arr.reshape(10, 10)


@pytest.mark.parametrize(
    "dem,wet_mask,method,expected",
    [p[1] for p in _params()],
    ids=[p[0] for p in _params()],
)
def test_defended(dem, wet_mask, method, expected):
    """Computed depth must match the pinned snapshot."""
    computed = (
        defended(method=method, bfm=wet_mask, dem=dem, hand_threshold=HAND_THRESHOLD)
        .isel(band=0)
        .values
    )
    np.testing.assert_allclose(computed, expected)
