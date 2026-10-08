"""
Tests for the quality-of-life utilities.
"""

import logging
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from generate_synthetic_data import load_test_data, run_case

from seiche.utils_qol import (
    asinstance,
    check_sha256_manifest,
    compute_file_sha256,
    compute_gpkg_sha256,
    is_file_ok,
    is_gpkg_ok,
    parse_args,
    require,
    setup_logging,
)

ASINSTANCE_CASES = load_test_data("test_utils_qol_data.yml", "asinstance")
REQUIRE_CASES = load_test_data("test_utils_qol_data.yml", "require")
PARSE_CASES = load_test_data("test_utils_qol_data.yml", "parse_args")
SHA256_CASES = load_test_data("test_utils_qol_data.yml", "file_sha256")
FILE_OK_CASES = load_test_data("test_utils_qol_data.yml", "is_file_ok")
GPKG_CASES = load_test_data("test_utils_qol_data.yml", "gpkg_sha256")
GPKG_OK_CASES = load_test_data("test_utils_qol_data.yml", "is_gpkg_ok")

_TYPES = {"str": str, "int": int}


def _write_gpkg(tmp_path: Path, case: dict) -> Path:
    """Write a small GeoPackage from a regression case."""
    gdf = gpd.GeoDataFrame(
        {"ind": case["ind"]},
        geometry=[box(*case["geometry"])],
        crs=case["crs"],
    )
    path = tmp_path / "data.gpkg"
    gdf.to_file(path, driver="GPKG")
    return path


@pytest.mark.parametrize("case", ASINSTANCE_CASES)
def test_asinstance(case: dict) -> None:
    """asinstance returns the value or raises on a type mismatch."""
    run_case(case, lambda: asinstance(case["obj"], _TYPES[case["cls"]]))


@pytest.mark.parametrize("case", REQUIRE_CASES)
def test_require(case: dict) -> None:
    """require returns the value or raises on None."""
    run_case(case, lambda: require(case["x"]))


@pytest.mark.parametrize("case", PARSE_CASES)
def test_parse_args(monkeypatch, case: dict) -> None:
    """parse_args reads the config file and verbosity from sys.argv."""
    monkeypatch.setattr(sys, "argv", case["argv"])
    if "raises" in case:
        with pytest.raises(SystemExit):
            parse_args()
        return
    args = parse_args()
    assert args.configfile == case["configfile"]
    assert args.verbose == case["verbose"]
    assert args.override == case.get("override", [])


@pytest.mark.parametrize("case", SHA256_CASES)
def test_compute_file_sha256(tmp_path: Path, case: dict) -> None:
    """The SHA-256 digest matches the pinned value."""
    path = tmp_path / "data.txt"
    path.write_text(case["content"], encoding="utf-8")
    assert compute_file_sha256(path) == case["expected"]


@pytest.mark.parametrize("case", FILE_OK_CASES)
def test_is_file_ok(tmp_path: Path, case: dict) -> None:
    """is_file_ok checks the file against the supplied hash."""
    path = tmp_path / "data.txt"
    path.write_text(case["content"], encoding="utf-8")
    assert is_file_ok(str(path), case["hash"]) == case["expected"]


@pytest.mark.parametrize("case", GPKG_CASES)
def test_compute_gpkg_sha256(tmp_path: Path, case: dict) -> None:
    """The deterministic gpkg hash matches the pinned value."""
    assert compute_gpkg_sha256(str(_write_gpkg(tmp_path, case))) == case["expected"]


def test_compute_gpkg_sha256_rejects_non_gpkg(tmp_path: Path) -> None:
    """compute_gpkg_sha256 rejects a non .gpkg file."""
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expects a .gpkg file"):
        compute_gpkg_sha256(str(path))


@pytest.mark.parametrize("case", GPKG_OK_CASES)
def test_is_gpkg_ok(tmp_path: Path, case: dict) -> None:
    """is_gpkg_ok checks the gpkg against the supplied hash."""
    assert (
        is_gpkg_ok(str(_write_gpkg(tmp_path, case)), case["hash"]) == case["expected"]
    )


def test_check_sha256_manifest_ok(tmp_path: Path) -> None:
    """check_sha256_manifest passes when every file matches the manifest."""
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    digest = compute_file_sha256(tmp_path / "a.txt")
    # blank lines in the manifest are skipped
    (tmp_path / "sha256.txt").write_text(
        f"\n{digest}  a.txt\n\n", encoding="utf-8"
    )
    check_sha256_manifest(tmp_path, ["a.txt"], rerun_hint="make data")


def test_check_sha256_manifest_raises_on_mismatch(tmp_path: Path) -> None:
    """check_sha256_manifest raises on a digest mismatch with the rerun hint."""
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "sha256.txt").write_text(
        f"{'0' * 64}  a.txt\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="sha256 mismatch"):
        check_sha256_manifest(tmp_path, ["a.txt"], rerun_hint="make data")


def test_setup_logging() -> None:
    """setup_logging only lets seiche log records through."""
    setup_logging(level=logging.DEBUG)
    assert logging.getLogger().level == logging.DEBUG
    filt = logging.getLogger().handlers[0].filters[0]
    assert filt.filter(
        logging.LogRecord("seiche.x", logging.INFO, "", 0, "m", (), None)
    )
    assert not filt.filter(
        logging.LogRecord("other", logging.INFO, "", 0, "m", (), None)
    )
