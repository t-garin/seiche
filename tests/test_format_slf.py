"""
Tests for the .slf formatting utilities.
"""

from pathlib import Path

import numpy as np
import pytest

from generate_synthetic_data import _empty_raster, load_test_data, run_case

from seiche.format_slf import RASTER_NDIMS, Slf

SLF_PATH = Path("tests/marmande_light/lf_fr1_2019_light.slf")
DEPTH = "HAUTEUR D'EAU"
X_SPEED = "VITESSE U"
Y_SPEED = "VITESSE V"
FREESURF = "SURFACE LIBRE"

INIT_CASES = load_test_data("test_format_slf_data.yml", "init")
INIT_REJECTS = load_test_data("test_format_slf_data.yml", "init_rejects")
DELINEATION_CASES = load_test_data("test_format_slf_data.yml", "delineation")
GRID_CASES = load_test_data("test_format_slf_data.yml", "generate_grid")
INTERP_VALUES_CASES = load_test_data("test_format_slf_data.yml", "interp_values")
INTERP_REJECTS = load_test_data("test_format_slf_data.yml", "interp_values_rejects")
INTERP_CASES = load_test_data("test_format_slf_data.yml", "interp")
RASTER_NDIMS_CASES = load_test_data("test_format_slf_data.yml", "raster_ndims")


@pytest.fixture(scope="module")
def slf():
    """A Slf instance built on the real test file."""
    return Slf(
        epsg=2154,
        depth_varname=DEPTH,
        x_speed_varname=X_SPEED,
        y_speed_varname=Y_SPEED,
        freesurf_varname=FREESURF,
        file_name=str(SLF_PATH),
    )


@pytest.mark.parametrize("case", INIT_CASES)
def test_slf_init_attributes(slf, case: dict) -> None:
    """The epsg and variable names are stored on the instance."""
    assert getattr(slf, case["key"]) == case["expected"]


def test_slf_init_rejects_non_int_epsg() -> None:
    """The epsg must be an integer."""
    run_case(
        INIT_REJECTS[0],
        lambda: Slf(
            epsg="2154",
            depth_varname=DEPTH,
            x_speed_varname=X_SPEED,
            y_speed_varname=Y_SPEED,
            freesurf_varname=FREESURF,
            file_name=str(SLF_PATH),
        ),
    )


@pytest.mark.parametrize("case", DELINEATION_CASES)
def test_get_delineation(slf, case: dict) -> None:
    """The delineation is a polygon matching the mesh extent."""
    poly = slf.get_delineation()
    assert poly.is_valid and not poly.is_empty
    assert poly.geom_type == "Polygon"
    assert list(poly.bounds) == case["expected_bounds"]


@pytest.mark.parametrize("case", GRID_CASES)
def test_generate_grid_on_extent(slf, case: dict) -> None:
    """A grid is generated on the mesh extent at the requested pixel size."""
    grid = slf.generate_grid_on_extent(case["pixel_size"])
    assert grid.shape == tuple(case["expected_shape"])
    assert grid.rio.crs.to_epsg() == case["expected_crs"]


@pytest.mark.parametrize("case", INTERP_VALUES_CASES)
def test_interp_values_on_grid(slf, case: dict) -> None:
    """Node values are interpolated on the target grid."""
    grid = slf.generate_grid_on_extent(500)
    out = slf.interp_values_on_grid(np.full(slf.npoin2, case["fill"]), grid)
    assert out.shape == tuple(case["expected_shape"])
    if "expected_max" in case:
        assert np.nanmax(out.values) == pytest.approx(case["expected_max"])
    if case.get("has_nan"):
        assert np.isnan(out.values).any()
        assert np.isfinite(out.values).any()


@pytest.mark.parametrize("case", INTERP_REJECTS)
def test_interp_values_on_grid_rejects(slf, case: dict) -> None:
    """Invalid grids and node counts are rejected."""
    grid = slf.generate_grid_on_extent(500)
    if case.get("n_bands"):
        grid = _empty_raster((5, 5), 500, 2154, n_bands=case["n_bands"])
        run_case(
            case, lambda: slf.interp_values_on_grid(np.full(slf.npoin2, 1.0), grid)
        )
    else:
        run_case(
            case, lambda: slf.interp_values_on_grid(np.full(case["n_nodes"], 1.0), grid)
        )


@pytest.mark.parametrize("case", INTERP_CASES)
def test_interp_on_grid(slf, case: dict) -> None:
    """Hazard variables are interpolated on the grid."""
    grid = slf.generate_grid_on_extent(500)
    out = getattr(slf, case["method"])(grid, **case["kwargs"])
    assert out.shape == grid.shape
    assert np.nanmax(out.values) == pytest.approx(case["expected_max"])


@pytest.mark.parametrize("case", RASTER_NDIMS_CASES)
def test_raster_ndims_constant(case: dict) -> None:
    """Rasters are expected to be 3D (band, y, x)."""
    assert RASTER_NDIMS == case["expected"]
