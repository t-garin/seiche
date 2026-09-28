"""
Tests for the state read utilities.
"""

from pathlib import Path

import geopandas as gpd
import pytest
import yaml
from shapely.geometry import box

from generate_synthetic_data import load_test_data, run_case

from seiche.utils_state import (
    get_config,
    read_epsg_from_state,
    read_expname_from_state,
    read_pop_conditions_from_state,
    read_use_variables_from_state,
)

with open("src/seiche/config_template.yml") as f:
    TEMPLATE = yaml.safe_load(f)

EXPNAME_CASES = load_test_data("test_utils_state_data.yml", "expname")
EPSG_CASES = load_test_data("test_utils_state_data.yml", "epsg")
USE_VARIABLES_CASES = load_test_data("test_utils_state_data.yml", "use_variables")
POP_CONDITIONS_CASES = load_test_data("test_utils_state_data.yml", "pop_conditions")
GET_CONFIG_CASES = load_test_data("test_utils_state_data.yml", "get_config")


def _make_state(tmp_path: Path, **overrides: object) -> dict[str, object]:
    """Return a state with the template config, overridden by ``overrides``."""
    config = {k: v for k, v in TEMPLATE.items()}
    config.update(overrides)
    return {"config": config, "config_path": str(tmp_path / "marmande.yml")}


def _write_poly(tmp_path: Path) -> Path:
    """Write a small GeoJSON polygon and return its path."""
    poly_path = tmp_path / "marmande.geojson"
    gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326").to_file(
        poly_path, driver="GeoJSON"
    )
    return poly_path


@pytest.mark.parametrize("case", EXPNAME_CASES)
def test_read_expname_from_state(tmp_path: Path, case: dict) -> None:
    """The experiment name comes from config, falling back to the file stem."""
    state = _make_state(tmp_path, **{"param.expname": case["expname"]})
    assert read_expname_from_state(state) == case["expected"]


@pytest.mark.parametrize("case", EPSG_CASES)
def test_read_epsg_from_state(tmp_path: Path, case: dict) -> None:
    """The EPSG comes from config, falling back to the polygon CRS."""
    overrides: dict[str, object] = {"param.EPSG": case["epsg"]}
    if case["write_poly"]:
        poly_path = _write_poly(tmp_path)
        overrides["path.inp"] = str(tmp_path)
        overrides["path.inp.POLY"] = poly_path.name
    state = _make_state(tmp_path, **overrides)
    assert read_epsg_from_state(state) == case["expected"]


@pytest.mark.parametrize("case", USE_VARIABLES_CASES)
def test_read_use_variables(tmp_path: Path, case: dict) -> None:
    """The used hazard variables follow the enabled damage functions."""
    state = _make_state(
        tmp_path,
        **{"use.dmg.floodam": case["floodam"], "use.dmg.jrc": case["jrc"]},
    )
    if "raises" in case:
        run_case(case, lambda: read_use_variables_from_state(state))
        return
    assert read_use_variables_from_state(state) == tuple(case["expected"])


@pytest.mark.parametrize("case", POP_CONDITIONS_CASES)
def test_read_pop_conditions_from_state(tmp_path: Path, case: dict) -> None:
    """Pop conditions must be a non-empty dict."""
    state = _make_state(tmp_path, **{"param.pop.conditions": case["conditions"]})
    run_case(case, lambda: read_pop_conditions_from_state(state))


@pytest.mark.parametrize("case", GET_CONFIG_CASES)
def test_get_config(tmp_path: Path, case: dict) -> None:
    """get_config parses a well-formed config and rejects a bad one."""
    config = (
        {**TEMPLATE, **case.get("overrides", {})}
        if case.get("template", True)
        else {"only_this": 1}
    )
    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    if "raises" in case:
        run_case(case, lambda: get_config(config_path))
        return
    loaded = get_config(config_path)
    assert loaded["path.out"] == case["expected"]["path.out"]
    assert loaded["param.EPSG"] == case["expected"]["param.EPSG"]
