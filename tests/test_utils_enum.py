"""
Tests for the shared string enums.
"""

from pathlib import Path

import pytest

from generate_synthetic_data import load_test_data

from seiche import utils_enum as ue

ENUMS = load_test_data("test_utils_enum_data.yml", "enums")
BAND_CASES = load_test_data("test_utils_enum_data.yml", "hazard_band_indices")
NAME_CASES = load_test_data("test_utils_enum_data.yml", "output_names")
FALLBACK_CASES = load_test_data("test_utils_enum_data.yml", "output_name_fallback")


@pytest.mark.parametrize("name", list(ENUMS))
def test_enum_is_str(name: str) -> None:
    """Every enum member is a str and iterates in declaration order."""
    enum_cls = getattr(ue, name)
    assert [member.value for member in enum_cls] == ENUMS[name]
    for member in enum_cls:
        assert isinstance(member, str)
        assert str(member) == member.value
        assert enum_cls(member.value) is member


@pytest.mark.parametrize("name", list(ENUMS))
def test_enum_rejects_unknown_value(name: str) -> None:
    """Constructing an enum from an unknown value raises ValueError."""
    with pytest.raises(ValueError):
        getattr(ue, name)("bogus")


@pytest.mark.parametrize("case", BAND_CASES)
def test_hazard_band_index(case: dict) -> None:
    """HazardBand band indices are the band positions."""
    assert ue.HazardBand[case["band"]].band_index == case["index"]


@pytest.mark.parametrize("case", NAME_CASES, ids=[c["member"] for c in NAME_CASES])
def test_output_name_and_savepath(case: dict) -> None:
    """OutputFiles members resolve their name and full path."""
    state = {"config": {"param.expname": "marmande_2019", "path.out": "out"}}
    member = ue.OutputFiles[case["member"]]
    assert member.filename(state, **case["parts"]) == case["expected"]
    assert member.savepath(state, **case["parts"]) == Path("out") / case["expected"]


@pytest.mark.parametrize("case", FALLBACK_CASES)
def test_output_name_falls_back_to_config_stem(case: dict) -> None:
    """The experiment name falls back to the config file stem."""
    state = {"config": case["config"], "config_path": case["config_path"]}
    assert ue.OutputFiles.dem.filename(state) == case["expected"]
