"""
Tests for the Floodam damage functions.
"""

import hashlib
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import xarray as xr
from shapely.geometry import Polygon, box

from generate_synthetic_data import (
    _empty_raster,
    load_test_data,
    run_case,
    synthetic_empty_vector,
)

from seiche.dmgfunc_floodam import Floodam, _read_precompiled
from seiche.utils_enum import FloodamAlea, FloodamSeason

floodam = Floodam()

COMMERCIAL_CASES = load_test_data("test_dmgfunc_floodam_data.yml", "commercial")
HOUSING_CASES = load_test_data("test_dmgfunc_floodam_data.yml", "housing")
SIRENE_CASES = load_test_data("test_dmgfunc_floodam_data.yml", "sirene")
INIT_CASES = load_test_data("test_dmgfunc_floodam_data.yml", "init")
PRECOMPILED_CASES = load_test_data("test_dmgfunc_floodam_data.yml", "read_precompiled")
AGRI_CASES = load_test_data("test_dmgfunc_floodam_data.yml", "agri_rpg")
SIRENE_REJECTS = load_test_data("test_dmgfunc_floodam_data.yml", "sirene_rejects")
COMMERCIAL_REJECTS = load_test_data(
    "test_dmgfunc_floodam_data.yml", "commercial_rejects"
)
FUNCTYPE_CASES = load_test_data(
    "test_dmgfunc_floodam_data.yml", "commercial_unknown_functype"
)

FILES = [
    "a.nc",
    "h.nc",
    "p.nc",
    "batisurf.nc",
    "stockemp.nc",
    "totalemp.nc",
    "seuilemp.csv",
    "sirenemp.csv",
    "ct.csv",
    "wext.nc",
    "wint.nc",
]


def _make_precompiled_dir(tmp_path: Path, wrong_hash: bool = False) -> Path:
    """
    Build a tiny fake precompiled dir with all files and a sha256.txt manifest.
    """
    for filename in FILES:
        if filename.endswith(".nc"):
            data_vars = {"value": (("x",), [1.0, 2.0])}
            ds = xr.Dataset(data_vars)
            path = tmp_path / filename
            ds.to_netcdf(path)
        else:
            path = tmp_path / filename
            path.write_text("a,b\n1,2\n", encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if wrong_hash:
            digest = "0" * 64
        (tmp_path / f"{filename}.sha").write_text(digest, encoding="utf-8")
    lines = []
    for filename in FILES:
        digest = (tmp_path / f"{filename}.sha").read_text(encoding="utf-8").strip()
        lines.append(f"{digest} {filename}")
    (tmp_path / "sha256.txt").write_text("\n".join(lines), encoding="utf-8")
    return tmp_path


def _hazard() -> object:
    """Return a small 3-band hazard raster (depth, speed, duration)."""
    hzd = _empty_raster((2, 2), 50, 2154, n_bands=3)
    return hzd.copy(
        data=[np.full((2, 2), 0.5), np.full((2, 2), 0.5), np.full((2, 2), 3600)]
    )


def _sirene_landcover(
    rows: list[tuple[str, str, str]], geoms: list[Polygon]
) -> gpd.GeoDataFrame:
    """Build a Sirene-like landcover from (siret, naf, etat) rows."""
    return gpd.GeoDataFrame(
        {
            "siret": [row[0] for row in rows],
            "activitePrincipaleEtablissement": [row[1] for row in rows],
            "nomenclatureActivitePrincipaleEtablissement": ["NAFRev2"] * len(rows),
            "trancheEffectifsEtablissement": ["00"] * len(rows),
            "etatAdministratifEtablissement": [row[2] for row in rows],
        },
        geometry=geoms,
        crs="EPSG:2154",
    )


@pytest.mark.parametrize("case", INIT_CASES)
def test_init_sets_attributes(case: dict) -> None:
    """Floodam() loads the precompiled files and computes the classes."""
    key = case["key"]
    if "expected_contains" in case:
        assert set(case["expected_contains"]).issubset(floodam.CLASSES[key])
    elif key == "datadir":
        assert floodam.DATADIR.name == case["expected"]
    else:
        assert floodam.CLASSES[key] == case["expected"]


@pytest.mark.parametrize("case", PRECOMPILED_CASES)
def test_read_precompiled_raises_on_sha_mismatch(tmp_path: Path, case: dict) -> None:
    """_read_precompiled raises RuntimeError when a file hash mismatches."""
    dirpath = _make_precompiled_dir(tmp_path, wrong_hash=case["wrong_hash"])
    run_case(case, lambda: _read_precompiled(dirpath))


@pytest.mark.parametrize("case", AGRI_CASES)
def test_get_dmg_agri_rpg(case: dict) -> None:
    """RPG agriculture damages use the damage-per-m2 and the parcel area."""
    landcover = synthetic_empty_vector(n_cells=4, pixel_size=50)
    landcover["classe"] = case["classes"]
    landcover["SURF_PARC"] = case["surf_parc"]
    hzd = _hazard()
    if case.get("nan_depth"):
        hzd.values[0, 0, 0] = np.nan
    out = floodam.get_dmg_agri_rpg(landcover, hzd, FloodamSeason.hiver, "classe")
    assert {"dmg_per_m2", "dmg"}.issubset(set(out.columns))
    if "expected_len" in case:
        assert len(out) == case["expected_len"]
    if "expected_dmg" in case:
        np.testing.assert_allclose(out["dmg"].values, case["expected_dmg"])


@pytest.mark.parametrize("case", HOUSING_CASES)
def test_get_dmg_housing_bdtopo(case: dict) -> None:
    """BdTopo housing damages keep only residential, active buildings."""
    landcover = synthetic_empty_vector(n_cells=4, pixel_size=50)
    landcover["USAGE1"] = case["usages"]
    landcover["USAGE2"] = [""] * 4
    landcover["ETAT"] = case["etats"]
    landcover["NB_ETAGES"] = case["n_etages"]
    landcover["NB_LOGTS"] = case["n_logts"]
    out = floodam.get_dmg_housing_bdtopo(landcover, _hazard(), FloodamAlea.fluvial)
    assert set(out["classe"]) == set(case["expected"])
    assert {"dmg_per_m2", "dmg", "area"}.issubset(set(out.columns))


@pytest.mark.parametrize("case", SIRENE_CASES)
def test_get_dmg_commercial_standalone_sirene(case: dict) -> None:
    """Sirene commercial damages only keep active, valid-NAF companies."""
    landcover = _sirene_landcover(case["rows"], [box(*g) for g in case["geoms"]])
    out = floodam.get_dmg_commercial_standalone_sirene(
        landcover,
        _hazard(),
        FloodamAlea.fluvial,
        return_minimum_price_if_above_thresh=True,
    )
    assert out["siret"].tolist() == case["expected"]
    assert "dmg" in out.columns


@pytest.mark.parametrize("case", SIRENE_REJECTS)
def test_get_dmg_commercial_standalone_sirene_rejects(case: dict) -> None:
    """A non-NAFRev2 nomenclature is rejected."""
    landcover = _sirene_landcover([("a", "1011Z", "A")], [box(0, 0, 50, 50)])
    landcover["nomenclatureActivitePrincipaleEtablissement"] = [case["nomenclature"]]
    run_case(
        case,
        lambda: floodam.get_dmg_commercial_standalone_sirene(
            landcover,
            _hazard(),
            FloodamAlea.fluvial,
            return_minimum_price_if_above_thresh=True,
        ),
    )


@pytest.mark.parametrize(
    "case", COMMERCIAL_CASES, ids=[c["id"] for c in COMMERCIAL_CASES]
)
def test_get_dmg_commercial(case: dict) -> None:
    """_get_dmg_commercial covers the Floodam commercial damage methods."""
    dmg = floodam._get_dmg_commercial(
        max_depth=0.5, duration=3600, alea=FloodamAlea.fluvial, **case["kwargs"]
    )
    if case["is_nan"]:
        assert np.isnan(dmg)
    else:
        assert dmg == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", COMMERCIAL_REJECTS)
def test_get_dmg_commercial_raises_on_wrong_types(case: dict) -> None:
    """_get_dmg_commercial rejects non-string naf/alea and non-numeric inputs."""
    run_case(
        case,
        lambda: floodam._get_dmg_commercial(
            duration=3600, alea=FloodamAlea.fluvial, **case["kwargs"]
        ),
    )


@pytest.mark.parametrize("case", FUNCTYPE_CASES)
def test_get_dmg_commercial_unknown_functype_raises(monkeypatch, case: dict) -> None:
    """A naf whose functype is neither c, p nor WIP raises ValueError."""
    ct = floodam.ct.copy()
    ct.loc[case["naf"]] = {"functype": case["functype"], "classe": "something"}
    monkeypatch.setattr(floodam, "ct", ct)
    run_case(
        case,
        lambda: floodam._get_dmg_commercial(
            naf=case["naf"],
            max_depth=0.5,
            duration=3600,
            alea=FloodamAlea.fluvial,
        ),
    )
