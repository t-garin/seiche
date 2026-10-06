"""
Tests for the hazard generation pipeline.
"""

import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from generate_synthetic_data import (
    REAL_XY,
    load_test_data,
    run_case,
    synthetic_dem,
    synthetic_hazard_at,
    synthetic_raster,
    synthetic_state,
)

from seiche.main_hazards import (
    generate_bfm_hazard,
    generate_hazard,
    generate_hazard_from_bands,
    generate_hvt_hazard,
    generate_slf_hazard,
)

SLF_PATH = Path("tests/marmande_light/lf_fr1_2019_light.slf")
# where the slf mesh lands after reprojection to EPSG:2154
SLF_X, SLF_Y = 472300, 6379228

GENERATE_HAZARD_CASES = load_test_data("test_main_hazards_data.yml", "generate_hazard")
FROM_BANDS_CASES = load_test_data(
    "test_main_hazards_data.yml", "generate_hazard_from_bands"
)
SLF_HAZARD_CASES = load_test_data("test_main_hazards_data.yml", "generate_slf_hazard")
BFM_HAZARD_CASES = load_test_data("test_main_hazards_data.yml", "generate_bfm_hazard")
HVT_HAZARD_CASES = load_test_data(
    "test_main_hazards_data.yml", "generate_hvt_hazard"
)


def _slf_state(tmp_path: Path, **overrides: object) -> dict[str, object]:
    """Return a state configured to process one slf file."""
    shutil.copy(SLF_PATH, tmp_path / "lf_fr1_2019_light.slf")
    state = synthetic_state(
        tmp_path,
        **{
            "path.inp.slf": [
                {
                    "filepath": "lf_fr1_2019_light.slf",
                    "epsg": 27563,
                    "nickname": "lf",
                    "xspeedVarname": "VITESSE U",
                    "yspeedVarname": "VITESSE V",
                    "depthVarname": "HAUTEUR D'EAU",
                    "freesurfVarname": "SURFACE LIBRE",
                    "depthThreshold": 0.05,
                }
            ],
            "path.inp.bfm.root": None,
            "param.slf.pixel_size": 500,
            "use.dmg.floodam": True,
            "use.dmg.jrc": False,
        },
    )
    # overwrite the default polygon with one around the slf location
    poly = gpd.GeoDataFrame(
        geometry=[box(465000, 6369000, 480000, 6390000)],
        crs="EPSG:2154",
    )
    poly.to_file(tmp_path / "poly.geojson", driver="GeoJSON")
    (tmp_path / "out").mkdir(exist_ok=True)
    state["config"].update(overrides)
    return state


def _slf_dem() -> object:
    """A DEM covering the slf location in EPSG:2154."""
    dem = synthetic_dem(shape=(40, 40), pixel_size=500)
    return dem.assign_coords(x=SLF_X - 7500 + dem.x, y=SLF_Y - 10500 + dem.y)


def _bfm_state(tmp_path: Path, **overrides: object) -> dict[str, object]:
    """Return a state configured to process the synthetic BFM tifs."""
    root = tmp_path / "floodml"
    root.mkdir()
    synthetic_raster(root / "Inf_20191210T175503_a.tif", 1, n=2, y=6300200)
    synthetic_raster(root / "Inf_20191210T175503_b.tif", 0, n=2, y=6299600)
    synthetic_raster(root / "Inf_20191217T174655_c.tif", 0)
    defended = {
        "use.defended.simple_a": True,
        "use.defended.simple_e": False,
        "use.defended.fwdet_c": False,
        "use.defended.fwdet_l": False,
        "use.defended.fwdet_n": False,
        "use.defended.hand_a": False,
        "use.defended.hand_e": False,
    }
    defended.update(overrides)
    return synthetic_state(
        tmp_path,
        **{
            "path.inp.bfm.root": "floodml",
            "path.inp.bfm.regex": r"(\d{8})T(\d{6})",
            "path.inp.bfm.filter_key": ".tif",
            "path.inp.bfm.files2ignore": None,
            "param.bfm.flooded_threshold": 0,
            "param.bfm.target_resolution": 100,
            "param.bfm.start_date": "2019-12-01",
            "param.bfm.end_date": "2019-12-31",
            "path.inp.slf": None,
            **defended,
        },
    )


def _hvt_state(tmp_path: Path, **overrides: object) -> dict[str, object]:
    """Return a state configured to process one user-provided hvt raster."""
    state = synthetic_state(
        tmp_path,
        **{
            "path.inp.hvt": [{"nickname": "hvt", "filepath": "hvt.tif"}],
            "path.inp.slf": None,
            "path.inp.bfm.root": None,
            "use.dmg.floodam": True,
            "use.dmg.jrc": False,
        },
    )
    (tmp_path / "out").mkdir(exist_ok=True)
    state["config"].update(overrides)
    return state


def _bfm_dem() -> object:
    """A DEM covering the synthetic BFM location."""
    dem = synthetic_dem(shape=(10, 10), pixel_size=100)
    return dem.assign_coords(x=REAL_XY[0] + dem.x, y=REAL_XY[1] + dem.y)


@pytest.mark.parametrize("case", GENERATE_HAZARD_CASES)
def test_generate_hazard(tmp_path, monkeypatch, case: dict) -> None:
    """generate_hazard dispatches to the configured hazard source."""
    if case["source"] == "slf":
        state = _slf_state(tmp_path)
        dem = _slf_dem()
    elif case["source"] == "bfm":
        state = _bfm_state(tmp_path)
        dem = _bfm_dem()
    else:
        state = _hvt_state(tmp_path)
        dem = None
        synthetic_raster(
            tmp_path / "hvt.tif",
            np.stack([np.full((10, 10), 1.0), np.full((10, 10), 2.0), np.full((10, 10), 3.0)]),
            n=10,
            n_bands=3,
        )
    if case["source"] == "unknown":
        monkeypatch.setattr(
            "seiche.main_hazards.read_hazards_from_state", lambda state: ["bogus"]
        )
    if dem is not None:
        dem.rio.to_raster(tmp_path / "dem.tif")
        state["dem"] = {"path": tmp_path / "dem.tif"}
    if "raises" in case:
        run_case(case, lambda: generate_hazard(state))
        return
    out = generate_hazard(state)
    assert set(out["hazard"]) == set(case["expected_keys"])
    assert all(Path(p).exists() for p in out["hazard"].values())


@pytest.mark.parametrize("case", FROM_BANDS_CASES)
def test_generate_hazard_from_bands(tmp_path: Path, case: dict) -> None:
    """The hazard bands are combined, optionally filled with zeros."""
    fillna0 = case["fillna0"]
    value = 0.0 if fillna0 else np.nan
    dem = _bfm_dem().copy(data=[[[value] * 10] * 10])
    hzd = generate_hazard_from_bands(
        max_depth=dem,
        max_speed=dem,
        duration=dem,
        state=_bfm_state(tmp_path),
        fillna0=fillna0,
    )
    assert hzd.shape == (3, 10, 10)
    if case.get("expected_all_zero"):
        assert (hzd.values[~np.isnan(hzd.values)] == 0).all()
    else:
        assert np.isnan(hzd.values).all()


@pytest.mark.parametrize(
    "case", SLF_HAZARD_CASES, ids=[c["name"] for c in SLF_HAZARD_CASES]
)
def test_generate_slf_hazard(tmp_path, monkeypatch, case: dict) -> None:
    """Hazard variables are interpolated from the slf mesh."""
    state = _slf_state(
        tmp_path,
        **{
            "use.dmg.floodam": case["use"]["floodam"],
            "use.dmg.jrc": case["use"]["jrc"],
        },
    )
    if case.get("no_depth"):
        monkeypatch.setattr(
            "seiche.main_hazards.read_use_variables_from_state",
            lambda state: (False, True, True),
        )
    hazard = generate_slf_hazard(_slf_dem(), state)
    assert set(hazard) == set(case["expected_keys"])
    for name, hzd in hazard.items():
        assert hzd.shape[0] == 3
        if case.get("band0_finite"):
            assert np.isfinite(hzd.isel(band=0).values).any()
        if case.get("empty_speed_duration"):
            for band in (1, 2):
                values = hzd.isel(band=band).values
                assert set(np.unique(values[~np.isnan(values)])) <= {0, 255}
        if case.get("empty_depth"):
            values = hzd.isel(band=0).values
            assert set(np.unique(values[~np.isnan(values)])) <= {0, 255}
    if case.get("loads_existing"):
        assert set(generate_slf_hazard(_slf_dem(), state)) == set(case["expected_keys"])


@pytest.mark.parametrize(
    "case", HVT_HAZARD_CASES, ids=[c["name"] for c in HVT_HAZARD_CASES]
)
def test_generate_hvt_hazard(tmp_path, case: dict) -> None:
    """User-provided hvt rasters become 3-band hazards, clipped to the poly."""
    n_bands = case.get("n_bands", 3)
    values = np.stack(
        [np.full((10, 10), value) for value in (1.0, 2.0, 3.0)[:n_bands]]
    )
    synthetic_raster(tmp_path / "hvt.tif", values, n=10, n_bands=n_bands)
    state = _hvt_state(
        tmp_path,
        **{
            "use.dmg.floodam": case.get("use", {}).get("floodam", True),
            "use.dmg.jrc": case.get("use", {}).get("jrc", False),
        },
    )
    if "raises" in case:
        run_case(case, lambda: generate_hvt_hazard(state))
        return
    if case.get("loads_existing"):
        pre = synthetic_hazard_at(500000, 6300000, shape=(10, 10), pixel_size=100)
        pre.rio.to_raster(tmp_path / "out" / "hzd_hvt_test.tif")
    hazard = generate_hvt_hazard(state)
    assert set(hazard) == set(case["expected_keys"])
    for hzd in hazard.values():
        assert hzd.shape[0] == 3
    if case.get("loads_existing"):
        np.testing.assert_array_equal(hazard["hvt"].values, pre.values)
    if case.get("check_bands"):
        # the user values survive (e.g. V/T are not zeroed when only JRC is used)
        for band, expected in ((0, 1.0), (1, 2.0), (2, 3.0)):
            values_ = hazard["hvt"].isel(band=band).values
            # 255 is the raster nodata value written by synthetic_raster
            mask = np.isfinite(values_) & (values_ != 255)
            assert np.allclose(values_[mask], expected)


@pytest.mark.parametrize(
    "case", BFM_HAZARD_CASES, ids=[c["name"] for c in BFM_HAZARD_CASES]
)
def test_generate_bfm_hazard(tmp_path, case: dict) -> None:
    """BFM hazards are computed for every enabled defended method."""
    state = _bfm_state(tmp_path, **case.get("methods", {}))
    hazard = generate_bfm_hazard(_bfm_dem(), state)
    assert set(hazard) == set(case["expected_keys"])
    if case.get("reuse_duration"):
        duration_path = tmp_path / "out" / "duration_test.tif"
        assert duration_path.exists()
        mtime = duration_path.stat().st_mtime
        generate_bfm_hazard(_bfm_dem(), state)
        assert duration_path.stat().st_mtime == mtime



