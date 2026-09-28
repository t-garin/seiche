"""
Tests for the economic impact computation.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from generate_synthetic_data import (
    load_test_data,
    synthetic_empty_vector,
    synthetic_hazard_at,
    synthetic_raster,
    synthetic_state,
)

from seiche.dmgfunc_floodam import Floodam
from seiche.dmgfunc_jrc import JRC
from seiche.utils_enum import Landcover, LandcoverType
from seiche.main_impact_eco import (
    _compute_floodam,
    impact_eco,
)

SIRENE_CSV = (
    "longitude,latitude,siret,activitePrincipaleEtablissement,"
    "nomenclatureActivitePrincipaleEtablissement,trancheEffectifsEtablissement,"
    "etatAdministratifEtablissement\n"
    "0.516,43.77,0001,1011Z,NAFRev2,00,A\n"
)

IMPACT_ECO_CASES = load_test_data("test_main_impact_eco_data.yml", "impact_eco")


@pytest.fixture(scope="module")
def floodam():
    """The Floodam damage functions, loaded once."""
    return Floodam()


@pytest.fixture(scope="module")
def jrc():
    """The JRC damage functions, loaded once."""
    return JRC()


def _write_inputs(tmp_path: Path) -> None:
    """Write the landcover inputs (raster + vector + sirene) in tmp_path."""
    synthetic_raster(tmp_path / "esawc.tif", 50.0, n=10, x=499500, y=6299500)
    synthetic_raster(tmp_path / "oso23.tif", 1.0, n=10, x=499500, y=6299500)
    gdf = synthetic_empty_vector(n_cells=4, pixel_size=100)
    gdf["CODE_GROUP"] = [1, 2, 5, 16]
    gdf["SURF_PARC"] = [1.0] * 4
    gdf = gdf.set_geometry(gdf.geometry.translate(499500, 6299500))
    gdf.to_file(tmp_path / "rpg.shp")
    bd = gpd.GeoDataFrame(
        {
            "USAGE1": ["Résidentiel"] * 4,
            "USAGE2": [""] * 4,
            "ETAT": ["En service"] * 4,
            "NB_ETAGES": [1, 1, 1, 1],
            "NB_LOGTS": [1, 1, 1, 1],
        },
        geometry=[
            box(499500, 6299500, 499600, 6299600),
            box(499600, 6299500, 499700, 6299600),
            box(499700, 6299500, 499800, 6299600),
            box(499800, 6299500, 499900, 6299600),
        ],
        crs="EPSG:2154",
    )
    bd.to_file(tmp_path / "bd.gpkg", layer="batiment")
    (tmp_path / "sirene.csv").write_text(SIRENE_CSV, encoding="utf-8")


def _hazard() -> object:
    """Return a properly georeferenced hazard raster at the poly location."""
    return synthetic_hazard_at(500000, 6300000)


def _hazard_tif(tmp_path: Path) -> Path:
    """Write a 3-band hazard tif and return its path."""
    hzd = _hazard()
    path = tmp_path / "hzd_hf_test.tif"
    hzd.rio.to_raster(path)
    return path


def _state(tmp_path: Path, **overrides: object) -> dict[str, object]:
    """Return a state with all landcovers and damage functions enabled."""
    _write_inputs(tmp_path)
    (tmp_path / "out").mkdir(exist_ok=True)
    return synthetic_state(
        tmp_path,
        **{
            "path.inp.lcv.esawc": ["esawc.tif"],
            "path.inp.lcv.oso23": ["oso23.tif"],
            "path.inp.lcv.rpg": ["rpg.shp"],
            "path.inp.lcv.bdtopo": ["bd.gpkg"],
            "path.inp.lcv.sirene": ["sirene.csv"],
            "use.dmg.jrc": True,
            "use.dmg.floodam": True,
            "param.jrc.region": "eu",
            "param.jrc.a3": "FRA",
            "param.floodam.season": "hiver",
            "param.floodam.alea": "fluvial",
            **overrides,
        },
    )


@pytest.mark.parametrize(
    "case", IMPACT_ECO_CASES, ids=[c["name"] for c in IMPACT_ECO_CASES]
)
def test_impact_eco(tmp_path, floodam, jrc, case: dict, caplog) -> None:
    """impact_eco writes the expected outputs for the enabled combos."""
    state = _state(
        tmp_path,
        **{
            "use.dmg.jrc": case["use"]["jrc"],
            "use.dmg.floodam": case["use"]["floodam"],
        },
    )
    state["hazard"] = {"hf": _hazard_tif(tmp_path)}
    with caplog.at_level("INFO"):
        impact_eco(state)
    out = tmp_path / "out"
    for filename in case.get("expected_files", []):
        assert (out / filename).exists()
    for pattern in case.get("absent_files", []):
        assert not list(out.glob(pattern))
    if case.get("expect_log"):
        assert any(case["expect_log"] in r.message for r in caplog.records)


def test_impact_eco_vector_jrc_dispatch(tmp_path, floodam, jrc, monkeypatch):
    """A vector landcover combined with jrc uses the vector jrc path."""
    state = _state(tmp_path, **{"use.dmg.floodam": False, "use.dmg.jrc": True})
    state["hazard"] = {"hf": _hazard_tif(tmp_path)}
    vector_lcv = synthetic_empty_vector(n_cells=4, pixel_size=100)
    vector_lcv["CODE_GROUP"] = [1, 2, 5, 16]
    vector_lcv = vector_lcv.set_geometry(vector_lcv.geometry.translate(500000, 6300000))
    from seiche import maps

    # only "rpg" defines column_for_jrc, so give esawc one to reach the case
    monkeypatch.setitem(
        maps.MAPS[Landcover.esawc],
        "column_for_jrc",
        "CODE_GROUP",
    )
    monkeypatch.setattr(
        "seiche.main_impact_eco.generate_or_load_lcv",
        lambda state, name: (vector_lcv, LandcoverType.vector),
    )
    monkeypatch.setattr(
        "seiche.main_impact_eco.read_landcovers_from_state",
        lambda state: [Landcover.esawc],
    )
    impact_eco(state)
    assert (tmp_path / "out" / "dmg_hf_esawc_test.gpkg").exists()


def test_compute_floodam_skips_when_output_exists(tmp_path, floodam):
    """_compute_floodam does nothing when the output already exists."""
    state = _state(tmp_path)
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    (out / "dmg_hf_rpg_test.gpkg").write_bytes(b"x")
    hzd = _hazard()
    _compute_floodam(
        floodam,
        state,
        landcover_name=Landcover.rpg,
        nickname="hf",
        hzd=hzd,
        landcover=synthetic_empty_vector(n_cells=4, pixel_size=100),
    )
    assert (out / "dmg_hf_rpg_test.gpkg").read_bytes() == b"x"
