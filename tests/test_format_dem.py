"""
Tests for the DEM formatting utilities.
"""

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from generate_synthetic_data import (
    load_test_data,
    run_case,
    synthetic_raster,
    synthetic_state,
)

from seiche.format_dem import (
    generate_dem_from_ascs,
    generate_dem_from_tifs,
    generate_or_load_dem,
)
from seiche.utils_state import read_epsg_from_state, read_poly_from_state

DEM_FROM_TIFS = load_test_data("test_format_dem_data.yml", "dem_from_tifs")
DEM_FROM_ASCS = load_test_data("test_format_dem_data.yml", "dem_from_ascs")
OR_LOAD_DEM = load_test_data("test_format_dem_data.yml", "or_load_dem")


def _write_asc(path: Path, values: np.ndarray, xll: float, yll: float) -> None:
    """Write a simple ESRI ASCII grid at a given corner."""
    n_rows, n_cols = values.shape
    with path.open("w") as f:
        f.write(f"ncols {n_cols}\n")
        f.write(f"nrows {n_rows}\n")
        f.write(f"xllcorner {xll}\n")
        f.write(f"yllcorner {yll}\n")
        f.write("cellsize 100\n")
        f.write("NODATA_value -9999\n")
        for row in values:
            f.write(" ".join(f"{v:.1f}" for v in row) + "\n")


def _write_tiles(tmp_path: Path, tiles: list[dict]) -> list[Path]:
    """Write the tif/asc tiles described by a regression case."""
    paths = []
    for tile in tiles:
        path = tmp_path / tile["name"]
        if tile.get("kind") == "asc":
            _write_asc(
                path,
                np.full((tile["n"], tile["n"]), tile["value"]),
                tile["xll"],
                tile["yll"],
            )
        else:
            synthetic_raster(
                path,
                tile["value"],
                n=tile.get("n", 8),
                x=tile.get("x"),
                y=tile.get("y"),
            )
        paths.append(path)
    return paths


@pytest.mark.parametrize("case", DEM_FROM_TIFS, ids=[c["id"] for c in DEM_FROM_TIFS])
def test_generate_dem_from_tifs(tmp_path: Path, case: dict) -> None:
    """Tiles are merged into a single DEM with NaN nodata."""
    tiles = _write_tiles(tmp_path, case["tiles"])
    state = synthetic_state(tmp_path)
    dem = generate_dem_from_tifs(
        tiles, read_epsg_from_state(state), read_poly_from_state(state)
    )
    assert dem.shape == (1, 10, 10)
    assert np.isnan(dem.rio.nodata)
    run_case(case, lambda: dem.values)


@pytest.mark.parametrize("case", DEM_FROM_ASCS, ids=[c["id"] for c in DEM_FROM_ASCS])
def test_generate_dem_from_ascs(tmp_path: Path, case: dict) -> None:
    """ASCII grids are read with their declared EPSG and merged."""
    asc_paths = _write_tiles(tmp_path, case["asc"])
    state = synthetic_state(tmp_path)
    dem = generate_dem_from_ascs(
        asc_paths,
        dem_epsg=case["dem_epsg"],
        epsg=read_epsg_from_state(state),
        poly=read_poly_from_state(state),
    )
    if "expected_crs" in case:
        assert dem.rio.crs.to_epsg() == case["expected_crs"]
    if "expected" in case:
        run_case(case, lambda: dem.values)


@pytest.mark.parametrize("case", OR_LOAD_DEM, ids=[c["id"] for c in OR_LOAD_DEM])
def test_generate_or_load_dem(tmp_path: Path, case: dict) -> None:
    """A missing DEM is generated and saved, then loaded."""
    (tmp_path / "out").mkdir(exist_ok=True)
    _write_tiles(tmp_path, case["tiles"])
    state = synthetic_state(
        tmp_path,
        **{
            "path.inp.dem.root": ".",
            "path.inp.dem.filter_key": case["filter_key"],
            "path.inp.dem.EPSG": 2154,
        },
    )
    if "raises" in case:
        run_case(case, lambda: generate_or_load_dem(state))
        return
    if case.get("call_twice"):
        generate_or_load_dem(state)
    out = generate_or_load_dem(state)
    dem = xr.open_dataarray(out["dem"]["path"])
    run_case(case, lambda: dem.values)


def test_generate_or_load_dem_skips_hvt_only(tmp_path: Path) -> None:
    """No DEM is generated when only user-provided hvt hazards are configured."""
    state = synthetic_state(
        tmp_path,
        **{
            "path.inp.hvt": [{"nickname": "hvt", "filepath": "hvt.tif"}],
            "path.inp.slf": None,
            "path.inp.bfm.root": None,
        },
    )
    out = generate_or_load_dem(state)
    assert "dem" not in out
