"""
Tests for the JRC damage functions.
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from generate_synthetic_data import (
    _empty_raster,
    load_test_data,
    run_case,
    synthetic_empty_vector,
)

from seiche.dmgfunc_jrc import (
    N_UNIQUE_VALUES_SINGLE_CLASS,
    JRC,
    _read_precompiled,
)
from seiche.utils_enum import HciMode, JrcClass, JrcRegion

jrc = JRC()

DMGFAC_VECTOR_CASES = load_test_data("test_dmgfunc_jrc_data.yml", "dmgfac_vector")
DMGFAC_VECTOR_REJECTS = load_test_data(
    "test_dmgfunc_jrc_data.yml", "dmgfac_vector_rejects"
)
CLASSE_REJECTS = load_test_data("test_dmgfunc_jrc_data.yml", "classe_rejects")
MISSING_COLUMNS = load_test_data("test_dmgfunc_jrc_data.yml", "missing_columns")
ALL_COMBOS = load_test_data("test_dmgfunc_jrc_data.yml", "maxdmg_classe_all_combos")
MAXDMG_CLASSE_REJECTS = load_test_data(
    "test_dmgfunc_jrc_data.yml", "maxdmg_classe_rejects"
)
MAP_JRC = load_test_data("test_dmgfunc_jrc_data.yml", "map_jrc")
INIT_CASES = load_test_data("test_dmgfunc_jrc_data.yml", "init")
PRECOMPILED_CASES = load_test_data("test_dmgfunc_jrc_data.yml", "read_precompiled")
RASTER_LC_CASES = load_test_data("test_dmgfunc_jrc_data.yml", "raster_lc")
VECTOR_LC_CASES = load_test_data("test_dmgfunc_jrc_data.yml", "vector_lc")
MAX_DMG_RASTER_CASES = load_test_data("test_dmgfunc_jrc_data.yml", "max_dmg_raster_lc")
MAXDMG_H_BUILDING = load_test_data(
    "test_dmgfunc_jrc_data.yml", "maxdmg_classe_h_building"
)
ENUM_REJECTS = load_test_data("test_dmgfunc_jrc_data.yml", "maxdmg_classe_enum_rejects")
MAXDMG_VECTOR_CASES = load_test_data("test_dmgfunc_jrc_data.yml", "maxdmg_vector")
CONSTANT_CASES = load_test_data("test_dmgfunc_jrc_data.yml", "constants")

_ENUMS = {"JrcClass": JrcClass, "HciMode": HciMode}


@pytest.fixture(autouse=True)
def _restore_dmgfac():
    """Restore the real damage factor table after tests that mutate it."""
    yield
    jrc._dmgfac = pd.read_csv("data/jrc/precompiled/dmgfac.csv", index_col=0)


def _make_precompiled_dir(tmp_path: Path, wrong_hash: bool = False) -> Path:
    """
    Build a tiny fake precompiled dir with the 7 CSVs and a sha256.txt manifest.
    """
    files = {
        "dmgfac.csv": "_dmgfac",
        "hmaxdmg.csv": "_hmaxdmg",
        "cmaxdmg.csv": "_cmaxdmg",
        "imaxdmg.csv": "_imaxdmg",
        "tmaxdmg.csv": "_tmaxdmg",
        "rmaxdmg.csv": "_rmaxdmg",
        "amaxdmg.csv": "_amaxdmg",
    }
    for filename in files:
        (tmp_path / filename).write_text("a,b\n1,2\n", encoding="utf-8")
        digest = hashlib.sha256((tmp_path / filename).read_bytes()).hexdigest()
        if wrong_hash:
            digest = "0" * 64
        (tmp_path / f"{filename}.sha").write_text(digest, encoding="utf-8")
    lines = []
    for filename in files:
        digest = (tmp_path / f"{filename}.sha").read_text(encoding="utf-8").strip()
        lines.append(f"{digest} {filename}")
    (tmp_path / "sha256.txt").write_text("\n".join(lines), encoding="utf-8")
    return tmp_path


def _landcover(case: dict) -> object:
    """Return the 5x5 landcover raster of a regression case."""
    rows = case["rows"]
    return _empty_raster((5, 5), 10, 2154).copy(data=[[[r] * 5 for r in rows]])


def _max_depth() -> object:
    """Return a 5x5 max depth raster filled with 0.5."""
    return _empty_raster((5, 5), 10, 2154).copy(data=[[[0.5] * 5] * 5])


@pytest.mark.parametrize("case", INIT_CASES)
def test_init_sets_attributes(case: dict) -> None:
    """JRC() loads the precompiled data and exposes classes and regions."""
    key = case["key"]
    if key == "classes":
        assert [c.value for c in jrc.CLASSES] == case["expected"]
    elif key == "regions":
        assert [r.value for r in jrc.REGIONS] == case["expected"]
    else:
        assert isinstance(jrc._dmgfac, pd.DataFrame)


@pytest.mark.parametrize("case", PRECOMPILED_CASES)
def test_read_precompiled_raises_on_sha_mismatch(tmp_path: Path, case: dict) -> None:
    """_read_precompiled raises RuntimeError when a file hash mismatches."""
    dirpath = _make_precompiled_dir(tmp_path, wrong_hash=case["wrong_hash"])
    run_case(case, lambda: _read_precompiled(dirpath))


@pytest.mark.parametrize("case", CLASSE_REJECTS)
def test_get_dmg_fac_classe_interpolators_rejects(case: dict) -> None:
    """Invalid class and region inputs are rejected."""
    with pytest.raises(ValueError, match=case["match"]):
        jrc._get_dmgfac_classe_interpolators(case["classe"], JrcRegion(case["region"]))


@pytest.mark.parametrize("case", DMGFAC_VECTOR_CASES)
def test_get_dmgfac_vector_interpolators(case: dict) -> None:
    """The interpolator follows the single-class, zero and mixed behaviours."""
    class_vector = case["class_vector"]
    if case.get("as_np"):
        class_vector = np.array(class_vector)
    dmg, std = jrc._get_dmgfac_vector_interpolators(class_vector, JrcRegion.eu)
    assert dmg(0.5) == pytest.approx(case["expected"])
    if case["std_expected"] is not None:
        assert std(0.5) == case["std_expected"]


@pytest.mark.parametrize("case", DMGFAC_VECTOR_REJECTS)
def test_get_dmgfac_vector_interpolators_rejects(case: dict) -> None:
    """Invalid class vectors and regions are rejected."""
    with pytest.raises(ValueError, match=case["match"]):
        jrc._get_dmgfac_vector_interpolators(
            case["class_vector"], JrcRegion(case["region"])
        )


@pytest.mark.parametrize("case", MISSING_COLUMNS)
def test_get_dmgfac_classe_interpolators_missing_columns(case: dict) -> None:
    """A missing regional column falls back to a NaN interpolator."""
    jrc._dmgfac = jrc._dmgfac.drop(columns=case["drop_cols"])
    interpolators = jrc._get_dmgfac_classe_interpolators(JrcClass.h, JrcRegion.eu)
    assert np.isnan(interpolators[case["index"]](0.5))


@pytest.mark.parametrize("case", RASTER_LC_CASES)
def test_get_dmg_fac_raster_lc(case: dict) -> None:
    """Raster landcover: damage factor and std rasters per pixel."""
    landcover = _landcover(case)
    dmgs, stds = jrc.get_dmg_fac_raster_lc(
        landcover, _max_depth(), MAP_JRC, JrcRegion.eu
    )
    assert dmgs.shape == (1, 5, 5)
    if case.get("expected_all_nan"):
        assert np.isnan(dmgs.values).all()
        return
    np.testing.assert_allclose(dmgs.values[0, :, 0], case["expected_col0"], atol=1e-5)


@pytest.mark.parametrize("case", VECTOR_LC_CASES)
def test_get_dmg_fac_vector_lc(case: dict) -> None:
    """Vector landcover gets per-row dmg and std columns."""
    map_jrc = {**MAP_JRC, 99: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]}
    landcover = synthetic_empty_vector(n_cells=4, pixel_size=50)
    landcover["class"] = case["classes"]
    hazard = _empty_raster((2, 2), 50, 2154, n_bands=3)
    hazard = hazard.copy(
        data=[np.full((2, 2), 0.5), np.zeros((2, 2)), np.zeros((2, 2))]
    )
    out = jrc.get_dmg_fac_vector_lc(landcover, hazard, "class", map_jrc, JrcRegion.eu)
    assert {"class", "dmg", "std", "geometry"}.issubset(set(out.columns))
    np.testing.assert_allclose(out["dmg"].to_numpy(), case["expected_dmg"])


@pytest.mark.parametrize("case", MAX_DMG_RASTER_CASES)
def test_get_max_dmg_raster_lc(case: dict) -> None:
    """Maximum damage raster is computed per landcover code."""
    map_jrc = {**MAP_JRC, 99: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]}
    out = jrc.get_max_dmg_raster_lc(_landcover(case), map_jrc, "FRA", HciMode.landuse)
    assert out.shape == (1, 5, 5)
    assert out.values[0, 0, 0] == pytest.approx(case["expected_corner"])
    assert out.values[0, 4, 0] == pytest.approx(case["expected_zero"])


@pytest.mark.parametrize("case", MAXDMG_H_BUILDING)
def test_get_maxdmg_classe_h_building(case: dict) -> None:
    """h building max damage is read from the hmaxdmg table, a3 is uppercased."""
    assert jrc._get_maxdmg_classe(
        case["a3"], JrcClass.h, HciMode.building
    ) == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", ENUM_REJECTS)
def test_get_maxdmg_classe_rejects_invalid_enums(case: dict) -> None:
    """Invalid classe and hci_mode values are rejected at enum construction."""
    run_case(case, lambda: _ENUMS[case["enum"]](case["value"]))


@pytest.mark.parametrize("classe,hci_mode", ALL_COMBOS)
def test_get_maxdmg_classe_all_combos(classe, hci_mode):
    """Every (classe, hci_mode) combination returns a finite value."""
    assert np.isfinite(jrc._get_maxdmg_classe("FRA", classe, hci_mode))


@pytest.mark.parametrize("case", MAXDMG_CLASSE_REJECTS)
def test_get_maxdmg_classe_rejects(case: dict) -> None:
    """Invalid a3, classe and hci_mode inputs are rejected."""
    with pytest.raises(ValueError, match=case["match"]):
        jrc._get_maxdmg_classe(case["a3"], case["classe"], case["hci_mode"])


@pytest.mark.parametrize("case", MAXDMG_VECTOR_CASES)
def test_get_maxdmg_vector(case: dict) -> None:
    """The max damage vector follows the zero and single-class behaviours."""
    assert jrc._get_maxdmg_vector(
        "FRA", case["class_vector"], HciMode(case["hci_mode"])
    ) == pytest.approx(case["expected"])


@pytest.mark.parametrize("case", CONSTANT_CASES)
def test_constants(case: dict) -> None:
    """Module constants match their documented values."""
    assert N_UNIQUE_VALUES_SINGLE_CLASS == case["expected"]
