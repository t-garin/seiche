"""
Tests for AFFECTED_POPULATION raster processing.
"""

import numpy as np
import pandas as pd
import pytest
import yaml
from pyproj import Transformer

from generate_synthetic_data import (
    run_case,
    synthetic_hazard,
    synthetic_population_raster,
    synthetic_population_vector,
)

from seiche.affected_population import (
    get_affected_people_raster,
    get_affected_people_vector,
    parse_condition,
)
from seiche.utils_da import generate_empty_da_from_bounds

with open("tests/test_affected_population_data.yml") as f:
    AP = yaml.safe_load(f)

SHAPE = (10, 10)
SEEDS = AP["seeds"]
CONDITIONS = AP["conditions"]
CRS_CASES = AP["crs_mismatch"]
PARSE_REJECTS = AP["parse_condition_rejects"]
HAZARDS = {f"H{i}": synthetic_hazard(seed=s) for i, s in enumerate(SEEDS, 1)}
RASTERPOPS = {
    f"P{i}": synthetic_population_raster(seed=s) for i, s in enumerate(SEEDS, 1)
}
VECTORPOPS = {
    f"P{i}": synthetic_population_vector(seed=s) for i, s in enumerate(SEEDS, 1)
}
_REAL_XY = (500000, 6300000)  # central France, EPSG:2154
_XY_TO_UTM = Transformer.from_crs(2154, 32631, always_xy=True)


def _decode(flat: str) -> np.ndarray:
    """Parse a space-joined snapshot string into a 2D (y, x) array."""
    return np.fromstring(flat, sep=" ").reshape(SHAPE)


def _da_at(bounds, crs, pixel_size, n_bands, seed):
    """Build a raster at a real location so reprojection keeps it overlapping."""
    da = generate_empty_da_from_bounds(bounds, pixel_size, crs, n_bands=n_bands)
    return da.copy(data=np.random.default_rng(seed).random((n_bands, *da.shape[1:])))


def _params_vector():
    """Yield (id, (pop, hazard, condition, expected)) for every combination."""
    for pk, pop in VECTORPOPS.items():
        for hk, hazard in HAZARDS.items():
            for ck, expr in CONDITIONS.items():
                key = f"{pk}_{hk}_{ck}"
                expected = np.fromstring(AP["result_vector"][key], sep=" ")
                case_id = f"{pk}-{hk}-{ck}"
                yield case_id, (pop, hazard, parse_condition(expr), expected)


def _params_raster():
    """Yield (id, (pop, hazard, condition, expected)) for every combination."""
    for pk, pop in RASTERPOPS.items():
        for hk, hazard in HAZARDS.items():
            for ck, expr in CONDITIONS.items():
                key = f"{pk}_{hk}_{ck}"
                expected = _decode(AP["result_raster"][key])
                case_id = f"{pk}-{hk}-{ck}"
                yield case_id, (pop, hazard, parse_condition(expr), expected)


@pytest.mark.parametrize(
    "pop,hazard,condition,expected",
    [p[1] for p in _params_raster()],
    ids=[p[0] for p in _params_raster()],
)
def test_affected_population_raster(pop, hazard, condition, expected):
    """Computed affected population must match the pinned snapshot."""
    computed = get_affected_people_raster(hazard, pop, condition).isel(band=0).values
    np.testing.assert_allclose(computed, expected, equal_nan=True)


def test_affected_population_raster_default_condition():
    """A None condition keeps all people where the hazard is not null."""
    pop = RASTERPOPS["P1"]
    hazard = HAZARDS["H1"]
    computed = get_affected_people_raster(hazard, pop).isel(band=0).values
    np.testing.assert_allclose(computed, pop.isel(band=0).values, equal_nan=True)


@pytest.mark.parametrize(
    "pop,hazard,condition,expected",
    [p[1] for p in _params_vector()],
    ids=[p[0] for p in _params_vector()],
)
def test_affected_population_vector(pop, hazard, condition, expected):
    """Computed vector affected population must match the pinned snapshot."""
    [computed] = get_affected_people_vector(hazard, pop, [condition])
    np.testing.assert_allclose(computed["ind"].values, expected, equal_nan=True)


def test_affected_population_vector_default_conditions():
    """A None condition keeps every row of the population vector."""
    pop = VECTORPOPS["P1"]
    hazard = HAZARDS["H1"]
    [computed] = get_affected_people_vector(hazard, pop)
    np.testing.assert_allclose(
        computed["ind"].values, pop["ind"].values, equal_nan=True
    )


@pytest.mark.parametrize("case", CRS_CASES)
def test_affected_population_raster_crs_mismatch(case: dict) -> None:
    """A hazard in a different CRS is reprojected, whichever raster is smaller."""
    x, y = _REAL_XY
    extent, pop_pixel, haz_pixel = (
        case["extent"],
        case["pop_pixel"],
        case["haz_pixel"],
    )
    pop = _da_at(
        (x - extent / 2, y - extent / 2, x + extent / 2, y + extent / 2),
        2154,
        pop_pixel,
        1,
        1312,
    )
    uw, us = _XY_TO_UTM.transform(x - extent / 2, y - extent / 2)
    ue, un = _XY_TO_UTM.transform(x + extent / 2, y + extent / 2)
    hazard = _da_at((uw, us, ue, un), 32631, haz_pixel, 3, 1312)
    computed = get_affected_people_raster(hazard, pop, parse_condition("True")).isel(
        band=0
    )
    assert computed.shape == tuple(case["expected_shape"])
    assert np.isfinite(computed.values).any()


@pytest.mark.parametrize("case", PARSE_REJECTS)
def test_parse_condition_rejects(case: dict) -> None:
    """Expressions referencing names other than h, v, t are rejected."""
    run_case(
        case,
        lambda: parse_condition(case["expr"])(h=pd.Series([1.0]), v=None, t=None),
    )
