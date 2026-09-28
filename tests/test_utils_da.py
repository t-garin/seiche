"""
Tests for the dataarray utilities.
"""

import json
import warnings
from pathlib import Path

import pytest
import rioxarray  # noqa: F401  (registers the .rio accessor)
import xarray as xr
from generate_synthetic_data import (
    load_test_data,
    run_case,
    synthetic_empty_vector,
    synthetic_hazard,
)

from seiche.utils_da import (
    generate_empty_da_from_bounds,
    merge_clipped_rasters,
    read_netcdf,
    reproj_clip,
)

GRID_CASES = load_test_data("test_utils_da_data.yml", "grid")
REPROJ_CASES = load_test_data("test_utils_da_data.yml", "reproj_clip")
MERGE_CASES = load_test_data("test_utils_da_data.yml", "merge")
NETCDF_CASES = load_test_data("test_utils_da_data.yml", "read_netcdf")


@pytest.mark.parametrize("case", GRID_CASES)
def test_generate_empty_da_from_bounds(case: dict) -> None:
    """The grid shape, coords and CRS match the pinned values."""
    kwargs = {"n_bands": case.get("n_bands", 1)}
    call = lambda: generate_empty_da_from_bounds(  # noqa: E731
        case["bounds"], case["pixel_size"], case["epsg"], **kwargs
    )
    if "raises" in case:
        run_case(case, call)
        return
    da = call()
    assert list(da.shape) == case["shape"]
    assert da.rio.crs.to_epsg() == case["crs"]
    run_case({"expected": case["x"]}, lambda: da.x.values)
    run_case({"expected": case["y"]}, lambda: da.y.values)


@pytest.mark.parametrize("case", REPROJ_CASES)
def test_reproj_clip(case: dict) -> None:
    """reproj_clip returns the pinned clipped raster or None out of bounds."""
    da = synthetic_hazard(seed=case["seed"])
    poly = synthetic_empty_vector(
        n_cells=case["n_cells"], pixel_size=case["pixel_size"]
    )
    if case.get("translate"):
        poly = poly.translate(*case["translate"])
    out = reproj_clip(da, case["epsg"], poly, pad=case.get("pad", True))
    run_case(case, lambda: out.values if out is not None else None)


def test_reproj_clip_declares_nodata_on_integer_raster() -> None:
    """An integer raster without nodata gets a 0 nodata, not an invalid cast."""
    da = synthetic_hazard(seed=3)
    da = da.isel(band=0).astype("uint8").rio.write_nodata(None)
    poly = synthetic_empty_vector(n_cells=4, pixel_size=100)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = reproj_clip(da, 2154, poly)
    assert out.rio.nodata == 0
    assert out.dtype == "uint8"
    assert not any("invalid value" in str(w.message) for w in caught)


@pytest.mark.parametrize("case", MERGE_CASES)
def test_merge_clipped_rasters(tmp_path: Path, case: dict) -> None:
    """merge_clipped_rasters merges the clipped tiles into one raster."""
    da = synthetic_hazard(seed=case["seed"]).isel(band=0)
    paths = []
    for offset in case["offsets"]:
        part = da.assign_coords(x=da.x + offset, y=da.y)
        path = tmp_path / f"part_{offset}.tif"
        part.rio.to_raster(path)
        paths.append(str(path))
    merged = merge_clipped_rasters(
        paths, case["epsg"], synthetic_empty_vector(n_cells=100, pixel_size=10)
    )
    run_case(case, lambda: merged.values)


@pytest.mark.parametrize("case", NETCDF_CASES)
def test_read_netcdf_restores_units(tmp_path: Path, case: dict) -> None:
    """read_netcdf restores the JSON-serialized units dict."""
    ds = xr.Dataset(
        {"temp": (("x",), case["data"])},
        attrs={"units": json.dumps(case["units"])},
    )
    path = tmp_path / "data.nc"
    ds.to_netcdf(path)
    loaded = read_netcdf(str(path))
    assert loaded.attrs["units"] == case["units"]
    assert list(loaded["temp"].values) == case["data"]
