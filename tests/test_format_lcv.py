"""
Tests for the land cover formatting utilities.
"""

from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from generate_synthetic_data import (
    load_test_data,
    run_case,
    synthetic_empty_vector,
    synthetic_raster,
    synthetic_state,
)

from seiche.utils_enum import Landcover, LandcoverType
from seiche.format_lcv import (
    _load_vector_lcv,
    generate_or_load_lcv,
)
from seiche.utils_gdf import read_sirene
from seiche.utils_state import read_epsg_from_state, read_poly_from_state

VECTOR_LCV_CASES = load_test_data("test_format_lcv_data.yml", "load_vector_lcv")
SIRENE_CASES = load_test_data("test_format_lcv_data.yml", "load_sirene")
OR_LOAD_CASES = load_test_data("test_format_lcv_data.yml", "generate_or_load_lcv")


def _vector_lcv(
    tmp_path: Path, name: str = "rpg.shp", codes: list[int] | None = None
) -> Path:
    """Write a small vector landcover shp fully inside the polygon."""
    gdf = synthetic_empty_vector(n_cells=4, pixel_size=100)
    gdf["CODE_GROUP"] = codes if codes is not None else [1, 2, 3, 4]
    gdf = gdf.set_geometry(gdf.geometry.translate(499500, 6299500))
    path = tmp_path / name
    gdf.to_file(path)
    return path


def _write_input(tmp_path: Path, case: dict) -> list[Path]:
    """Write the landcover input described by a regression case."""
    file = case["file"]
    path = tmp_path / file["name"]
    if file["name"].endswith(".tif"):
        synthetic_raster(path, file["value"], n=file["n"], x=file["x"], y=file["y"])
    elif file["name"].endswith(".shp"):
        _vector_lcv(tmp_path, name=file["name"])
    elif file["name"].endswith(".csv"):
        path.write_text(case["csv"], encoding="utf-8")
    else:
        path.write_text("x", encoding="utf-8")
    return [path]


@pytest.mark.parametrize(
    "case", VECTOR_LCV_CASES, ids=[c["id"] for c in VECTOR_LCV_CASES]
)
def test_load_vector_lcv(tmp_path: Path, case: dict) -> None:
    """A shp/gpkg is reprojected, clipped and cached as a gpkg."""
    (tmp_path / "out").mkdir(exist_ok=True)
    state = synthetic_state(tmp_path)
    savepath = tmp_path / "out" / "rpg.gpkg"
    if case.get("kind") == "gpkg":
        gdf = gpd.GeoDataFrame(
            {"USAGE1": case["usage"]},
            geometry=[box(499500, 6299500, 499600, 6299600)],
            crs="EPSG:2154",
        )
        gpkg = tmp_path / "bd.gpkg"
        gdf.to_file(gpkg, layer=case["layer"])
        paths = [gpkg]
    else:
        paths = [_vector_lcv(tmp_path, codes=case.get("codes"))]
        if case.get("n_files", 1) == 2:
            paths = [tmp_path / "a.shp", tmp_path / "b.shp"]
    if "raises" in case:
        run_case(
            case,
            lambda: _load_vector_lcv(
                paths,
                savepath,
                read_epsg_from_state(state),
                read_poly_from_state(state),
                case.get("layer"),
            ),
        )
        return
    if case.get("cached"):
        _load_vector_lcv(
            paths,
            savepath,
            read_epsg_from_state(state),
            read_poly_from_state(state),
            None,
        )
        cached = gpd.GeoDataFrame(
            {"CODE_GROUP": [9]},
            geometry=[box(499500, 6299500, 499600, 6299600)],
            crs="EPSG:2154",
        )
        cached.to_file(savepath, driver="GPKG")
    lcv = _load_vector_lcv(
        paths,
        savepath,
        read_epsg_from_state(state),
        read_poly_from_state(state),
        case.get("layer"),
    )
    if "expected_len" in case:
        assert len(lcv) == case["expected_len"]
        assert savepath.exists()
    if "expected_codes" in case:
        assert lcv["CODE_GROUP"].tolist() == case["expected_codes"]
    if "expected_usage" in case:
        assert lcv["USAGE1"].tolist() == case["expected_usage"]


@pytest.mark.parametrize("case", SIRENE_CASES, ids=[c["id"] for c in SIRENE_CASES])
def test_load_sirene(tmp_path: Path, case: dict) -> None:
    """A sirene csv is converted to points, reprojected and clipped."""
    (tmp_path / "out").mkdir(exist_ok=True)
    state = synthetic_state(tmp_path)
    savepath = tmp_path / "out" / "sirene.gpkg"
    paths = [tmp_path / "sirene.csv"]
    if case.get("n_files", 1) == 1:
        paths[0].write_text(case["csv"], encoding="utf-8")
    else:
        paths = [tmp_path / "a.csv", tmp_path / "b.csv"]
    if "raises" in case:
        run_case(
            case,
            lambda: _load_vector_lcv(
                paths,
                savepath,
                read_epsg_from_state(state),
                read_poly_from_state(state),
                reader=lambda p: read_sirene(p, epsg=read_epsg_from_state(state)),
            ),
        )
        return
    epsg = read_epsg_from_state(state)
    lcv = _load_vector_lcv(
        paths,
        savepath,
        epsg,
        read_poly_from_state(state),
        reader=lambda p: read_sirene(p, epsg=epsg),
    )
    assert len(lcv) == case["expected_len"]
    assert lcv.crs.to_epsg() == case["expected_crs"]
    assert savepath.exists()


@pytest.mark.parametrize("case", OR_LOAD_CASES, ids=[c["id"] for c in OR_LOAD_CASES])
def test_generate_or_load_lcv(tmp_path: Path, case: dict) -> None:
    """The landcover is generated or loaded from the configured file."""
    (tmp_path / "out").mkdir(exist_ok=True)
    _write_input(tmp_path, case)
    name = Landcover(case["landcover"])
    state = synthetic_state(
        tmp_path, **{f"path.inp.lcv.{name}": [case["file"]["name"]]}
    )
    if "raises" in case:
        run_case(case, lambda: generate_or_load_lcv(state, name))
        return
    if case.get("loads_existing"):
        generate_or_load_lcv(state, name)
    lcv, landcover_type = generate_or_load_lcv(state, name)
    assert landcover_type == LandcoverType(case["expected_type"])
    if "expected_shape" in case:
        assert lcv.shape == tuple(case["expected_shape"])
    if "expected_len" in case:
        assert len(lcv) == case["expected_len"]
