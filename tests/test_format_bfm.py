"""
Tests for the BFM formatting utilities.
"""

from pathlib import Path

import dask
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from generate_synthetic_data import (
    REAL_XY,
    load_test_data,
    run_case,
    synthetic_dem,
    synthetic_raster,
    synthetic_state,
)

from seiche.format_bfm import (
    filter_bfms,
    generate_bfms_netcdfs,
    get_bfm_at_date,
    get_bfms_paths_n_dates,
    get_duration,
    get_duration_from_bfms,
    get_max_depth_from_duration,
    get_max_speed_from_dem,
    is_bfm_valid,
    load_bfms_from_nc_files,
)
from seiche.utils_enum import DefendedMethod
from seiche.utils_state import read_epsg_from_state, read_poly_from_state

STATES = load_test_data("test_format_bfm_data.yml", "states")
PATHS_N_DATES_CASES = load_test_data(
    "test_format_bfm_data.yml", "get_bfms_paths_n_dates"
)
BFM_AT_DATE_CASES = load_test_data("test_format_bfm_data.yml", "get_bfm_at_date")
NETCDFS_CASES = load_test_data("test_format_bfm_data.yml", "generate_bfms_netcdfs")
MAX_DEPTH_CASES = load_test_data(
    "test_format_bfm_data.yml", "get_max_depth_from_duration"
)
MAX_SPEED_CASES = load_test_data("test_format_bfm_data.yml", "get_max_speed_from_dem")
DUR_FROM_BFMS_CASES = load_test_data(
    "test_format_bfm_data.yml", "get_duration_from_bfms"
)
DUR_FROM_BFMS_REJECTS = load_test_data(
    "test_format_bfm_data.yml", "get_duration_from_bfms_rejects"
)
IS_VALID_CASES = load_test_data("test_format_bfm_data.yml", "is_bfm_valid")
FILTER_CASES = load_test_data("test_format_bfm_data.yml", "filter_bfms")
GET_DURATION_CASES = load_test_data("test_format_bfm_data.yml", "get_duration")
LOAD_BFMS_CASES = load_test_data("test_format_bfm_data.yml", "load_bfms_from_nc_files")


def _scenario_state(tmp_path: Path, name: str) -> dict[str, object]:
    """Return a state whose input dir holds the tifs of a named scenario."""
    scenario = STATES[name]
    root = tmp_path / "floodml"
    root.mkdir()
    for tif in scenario["tifs"]:
        synthetic_raster(
            root / tif["name"],
            tif["value"],
            n=tif.get("n", 8),
            x=tif.get("x"),
            y=tif.get("y"),
        )
    if scenario.get("notes"):
        (root / "notes.txt").write_text("x", encoding="utf-8")
    ignore = None
    if scenario.get("files2ignore"):
        ignore = tmp_path / "ignore.txt"
        ignore.write_text(scenario["files2ignore"], encoding="utf-8")
    return synthetic_state(
        tmp_path,
        **{
            "path.inp.bfm.root": "floodml",
            "path.inp.bfm.regex": scenario["regex"],
            "path.inp.bfm.filter_key": scenario["filter_key"],
            "path.inp.bfm.files2ignore": str(ignore) if ignore else None,
        },
    )


def _nc_paths(savedir: Path) -> list[Path]:
    """Return the sorted .nc files of a BFM savedir."""
    return sorted(savedir.glob("*.nc"))


@pytest.mark.parametrize("case", PATHS_N_DATES_CASES)
def test_get_bfms_paths_n_dates(tmp_path, case: dict) -> None:
    """Matching tifs are found, grouped by their regex-parsed date."""
    state = _scenario_state(tmp_path, case["state"])
    paths_dates = get_bfms_paths_n_dates(state)
    if "expected_len" in case:
        assert len(paths_dates) == case["expected_len"]
    if "expected_dates" in case:
        assert sorted(str(dt) for _, dt in paths_dates) == sorted(
            case["expected_dates"]
        )
    if "skip_names" in case:
        names = {Path(p).name for p, _ in paths_dates}
        assert not names.intersection(case["skip_names"])
    if case.get("sorted"):
        paths = [p for p, _ in paths_dates]
        assert paths == sorted(paths)


@pytest.mark.parametrize("case", BFM_AT_DATE_CASES)
def test_get_bfm_at_date(tmp_path, case: dict) -> None:
    """BFMs of the same date are merged, invalid values set to NaN."""
    state = _scenario_state(tmp_path, case["state"])
    paths_dates = get_bfms_paths_n_dates(state)
    same_date = [p for p, dt in paths_dates if str(dt) == case["date"]]
    bfm = get_bfm_at_date(
        pd.Timestamp(case["date"]),
        same_date,
        read_epsg_from_state(state),
        read_poly_from_state(state),
    )
    if "expected" in case and case["expected"] is None:
        assert bfm is None
        return
    assert bfm is not None
    if "expected_unique" in case:
        assert set(np.unique(bfm.values[~np.isnan(bfm.values)])) == set(
            case["expected_unique"]
        )
    if case.get("has_nan"):
        assert np.isnan(bfm.values).any()
    if case.get("expected_all_nan"):
        assert np.isnan(bfm.values).all()


@pytest.mark.parametrize("case", NETCDFS_CASES)
def test_generate_bfms_netcdfs(tmp_path, case: dict) -> None:
    """NetCDFs are written per date; existing ones are not rewritten."""
    state = _scenario_state(tmp_path, case["state"])
    savedir = Path(generate_bfms_netcdfs(state))
    assert sorted(p.name for p in savedir.glob("*.nc")) == case["expected_names"]
    if case.get("idempotent"):
        first = savedir / case["expected_names"][0]
        mtime = first.stat().st_mtime
        generate_bfms_netcdfs(state)
        assert first.stat().st_mtime == mtime


@pytest.mark.parametrize("case", MAX_DEPTH_CASES)
def test_get_max_depth_from_duration(tmp_path, case: dict) -> None:
    """max depth is the defended depth where duration exceeds the threshold."""
    state = _scenario_state(tmp_path, case["state"])
    savedir = Path(generate_bfms_netcdfs(state))
    bfms = load_bfms_from_nc_files(_nc_paths(savedir), target_resolution=100)
    duration = get_duration_from_bfms(
        bfms,
        np.datetime64(case["mindate"], "ns"),
        np.datetime64(case["maxdate"], "ns"),
    )
    dem = synthetic_dem(shape=case["dem_shape"], pixel_size=100)
    dem = dem.assign_coords(x=REAL_XY[0] + dem.x, y=REAL_XY[1] + dem.y)
    max_depth = get_max_depth_from_duration(
        duration, DefendedMethod(case["method"]), dem
    )
    assert max_depth.shape == duration.shape
    assert np.nanmin(max_depth.values) >= case["expected_min_ge"]


@pytest.mark.parametrize("case", MAX_SPEED_CASES)
def test_get_max_speed_from_dem(case: dict) -> None:
    """max speed is an empty (all-NaN) copy of the DEM."""
    dem = synthetic_dem(shape=case["shape"])
    max_speed = get_max_speed_from_dem(dem)
    assert max_speed.shape == dem.shape
    assert np.isnan(max_speed.values).all()


@pytest.mark.parametrize("case", DUR_FROM_BFMS_CASES)
def test_get_duration_from_bfms(tmp_path, case: dict) -> None:
    """Duration is computed per pixel from the BFM time series."""
    state = _scenario_state(tmp_path, case["state"])
    savedir = Path(generate_bfms_netcdfs(state))
    bfms = load_bfms_from_nc_files(_nc_paths(savedir), target_resolution=100)
    with dask.config.set(scheduler="synchronous"):
        duration = get_duration_from_bfms(
            bfms,
            np.datetime64(case["mindate"], "ns"),
            np.datetime64(case["maxdate"], "ns"),
        )
    assert duration.shape == (1, *bfms.shape[2:])
    assert float(np.nanmin(duration.values)) == case["expected_min"]
    assert float(np.nanmax(duration.values)) > case["expected_max_gt"]


@pytest.mark.parametrize("case", DUR_FROM_BFMS_REJECTS)
def test_get_duration_from_bfms_wrong_date_types(case: dict) -> None:
    """mindate and maxdate must be numpy datetime64."""
    bad = case["bad"]
    mindate = "2019-12-01" if bad == "mindate" else np.datetime64("2019-12-01", "ns")
    maxdate = "2019-12-31" if bad == "maxdate" else np.datetime64("2019-12-31", "ns")
    run_case(case, lambda: get_duration_from_bfms(None, mindate, maxdate))


@pytest.mark.parametrize("case", IS_VALID_CASES)
def test_is_bfm_valid(tmp_path, case: dict) -> None:
    """A valid nc file yields True, an invalid one yields False."""
    state = _scenario_state(tmp_path, case["state"])
    savedir = Path(generate_bfms_netcdfs(state))
    valid = _nc_paths(savedir)[0]
    invalid = tmp_path / "invalid.nc"
    xr.DataArray(
        np.array([[[2, 2], [2, 2]]]),
        dims=("band", "y", "x"),
    ).to_netcdf(invalid)
    assert list(is_bfm_valid([valid, invalid])) == case["expected"]


@pytest.mark.parametrize("case", FILTER_CASES)
def test_filter_bfms(tmp_path, case: dict) -> None:
    """Only the valid nc files are kept."""
    state = _scenario_state(tmp_path, case["state"])
    savedir = Path(generate_bfms_netcdfs(state))
    valid = _nc_paths(savedir)[0]
    invalid = tmp_path / "invalid.nc"
    xr.DataArray(
        np.array([[[2, 2], [2, 2]]]),
        dims=("band", "y", "x"),
    ).to_netcdf(invalid)
    assert filter_bfms([valid, invalid]) == [valid]


@pytest.mark.parametrize("case", GET_DURATION_CASES)
def test_get_duration(case: dict) -> None:
    """Flood duration sums the intervals around flooded observations."""
    dates = pd.to_datetime(case["dates"]).to_numpy().astype("datetime64[ns]")
    mindate = np.datetime64(case["mindate"], "ns")
    maxdate = np.datetime64(case["maxdate"], "ns")
    run_case(
        case,
        lambda: get_duration(dates, np.array(case["values"]), mindate, maxdate),
    )


@pytest.mark.parametrize("case", LOAD_BFMS_CASES)
def test_load_bfms_from_nc_files(tmp_path, case: dict) -> None:
    """nc files are concatenated along time and sorted."""
    state = _scenario_state(tmp_path, case["state"])
    savedir = Path(generate_bfms_netcdfs(state))
    paths = _nc_paths(savedir)
    if case.get("crs_mismatch"):
        other = tmp_path / "other.nc"
        xr.open_dataarray(paths[0]).rio.write_crs("EPSG:32631").to_netcdf(other)
        paths = [paths[0], other]
    if "raises" in case:
        run_case(case, lambda: load_bfms_from_nc_files(paths, target_resolution=100))
        return
    bfms = load_bfms_from_nc_files(paths, target_resolution=100)
    assert bfms.shape[0] == case["expected_time_n"]
    assert list(bfms.time.values) == sorted(bfms.time.values)
