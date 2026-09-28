"""
Tests for the population impact computation.
"""

from pathlib import Path

import pytest

from generate_synthetic_data import (
    load_test_data,
    synthetic_empty_vector,
    synthetic_hazard_at,
    synthetic_raster,
    synthetic_state,
)

from seiche.main_impact_pop import (
    _process_filosofi,
    _process_ghslpop,
    impact_pop,
)

CONDITIONS = {"always_true": "True", "is_above_30cm": "h > 0.3"}

IMPACT_POP_CASES = load_test_data("test_main_impact_pop_data.yml", "impact_pop")


def _write_pop_inputs(tmp_path: Path) -> None:
    """Write the ghslpop raster and the filosofi vector in tmp_path."""
    synthetic_raster(tmp_path / "ghslpop.tif", 5.0, n=10, x=500000, y=6300000)
    fil = synthetic_empty_vector(n_cells=4, pixel_size=100)
    fil["ind"] = [10, 20, 30, 40]
    fil = fil.set_geometry(fil.geometry.translate(500000, 6300000))
    fil.to_file(tmp_path / "filosofi.gpkg")


def _hazard_tif(tmp_path: Path) -> Path:
    """Write a 3-band hazard tif and return its path."""
    hzd = synthetic_hazard_at(500000, 6300000)
    path = tmp_path / "hzd_hf_test.tif"
    hzd.rio.to_raster(path)
    return path


def _state(tmp_path: Path, **overrides: object) -> dict[str, object]:
    """Return a state with both population datasets enabled."""
    _write_pop_inputs(tmp_path)
    (tmp_path / "out").mkdir(exist_ok=True)
    return synthetic_state(
        tmp_path,
        **{
            "path.inp.pop.ghslpop": ["ghslpop.tif"],
            "path.inp.pop.filosofi": ["filosofi.gpkg"],
            "param.pop.conditions": CONDITIONS,
            **overrides,
        },
    )


@pytest.mark.parametrize(
    "case", IMPACT_POP_CASES, ids=[c["name"] for c in IMPACT_POP_CASES]
)
def test_impact_pop(tmp_path: Path, case: dict) -> None:
    """impact_pop writes the expected outputs for the enabled datasets."""
    overrides: dict[str, object] = {}
    if not case["filosofi"]:
        overrides["path.inp.pop.filosofi"] = None
    if not case["ghslpop"]:
        overrides["path.inp.pop.ghslpop"] = None
    state = _state(tmp_path, **overrides)
    state["hazard"] = {"hf": _hazard_tif(tmp_path)}
    impact_pop(state)
    out = tmp_path / "out"
    for filename in case["expected_files"]:
        assert (out / filename).exists()
    for pattern in case.get("absent_patterns", []):
        assert not list(out.glob(pattern))


def test_impact_pop_unknown_pop_skipped(tmp_path, monkeypatch):
    """An unknown population dataset name is skipped."""
    state = _state(tmp_path)
    state["hazard"] = {"hf": _hazard_tif(tmp_path)}
    monkeypatch.setattr(
        "seiche.main_impact_pop.read_pop_datasets_from_state",
        lambda state: ["bogus"],
    )
    impact_pop(state)
    assert not list((tmp_path / "out").glob("bogus_*"))


def test_process_ghslpop_skips_when_output_exists(tmp_path):
    """_process_ghslpop does nothing when the output already exists."""
    state = _state(tmp_path)
    out = tmp_path / "out"
    (out / "ghslpop_hf_always_true_test.tif").write_bytes(b"x")
    hazard = synthetic_hazard_at(500000, 6300000)
    from generate_synthetic_data import generate_empty_da_from_bounds

    pop = generate_empty_da_from_bounds(
        (500000, 6300000, 501000, 6301000), 100, 2154
    ).copy(data=[[[10] * 10] * 10])
    _process_ghslpop(state, nickname="hf", hzd_filled=hazard, ghslpop=pop)
    assert (out / "ghslpop_hf_always_true_test.tif").read_bytes() == b"x"


def test_process_filosofi_skips_when_output_exists(tmp_path):
    """_process_filosofi does nothing when the output already exists."""
    state = _state(tmp_path)
    out = tmp_path / "out"
    (out / "filosofi_hf_always_true_test.gpkg").write_bytes(b"x")
    hazard = synthetic_hazard_at(500000, 6300000)
    filosofi = synthetic_empty_vector(n_cells=4, pixel_size=100)
    filosofi["ind"] = [10, 20, 30, 40]
    _process_filosofi(state, nickname="hf", hzd_filled=hazard, filosofi=filosofi)
    assert (out / "filosofi_hf_always_true_test.gpkg").read_bytes() == b"x"
