"""
Tests for the GeoDataFrame utilities.
"""

import pandas as pd
import pytest

from generate_synthetic_data import (
    load_test_data,
    run_case,
    synthetic_empty_vector,
    synthetic_hazard,
)

from seiche.utils_gdf import concat_hazard, find_column, streamline

STREAMLINE_CASES = load_test_data("test_utils_gdf_data.yml", "streamline")
CONCAT_CASES = load_test_data("test_utils_gdf_data.yml", "concat_hazard")
CONCAT_REJECTS = load_test_data("test_utils_gdf_data.yml", "concat_hazard_rejects")
FIND_COLUMN_CASES = load_test_data("test_utils_gdf_data.yml", "find_column")


@pytest.mark.parametrize("case", STREAMLINE_CASES)
def test_streamline(case: dict) -> None:
    """streamline keeps only the geometry and the chosen class column."""
    gdf = synthetic_empty_vector(n_cells=5)
    gdf[case["col"]] = case["value"]
    gdf["dropped"] = 9
    out = streamline(gdf, case["col2keep"], newcol=case["newcol"])
    assert list(out.columns) == ["geometry", case["newcol"]]
    assert out[case["newcol"]].tolist() == case["expected"]


@pytest.mark.parametrize("case", CONCAT_CASES)
def test_concat_hazard(case: dict) -> None:
    """concat_hazard adds the requested hazard columns to the landcover."""
    da = synthetic_hazard(seed=case["seed"])
    landcover = synthetic_empty_vector(
        n_cells=case["n_cells"], pixel_size=case["pixel_size"]
    )
    if case.get("index"):
        landcover = landcover.iloc[case["index"]]
    out = concat_hazard(
        landcover,
        da,
        use_max_speed=case.get("use_max_speed", True),
        use_duration=case.get("use_duration", True),
    )
    for col, mean in case.get("expected_means", {}).items():
        run_case({"expected": mean}, lambda: out[col].mean())
    if "expected_columns" in case:
        assert list(out.columns) == case["expected_columns"]
    if "expected_index" in case:
        assert list(out.index) == case["expected_index"]


@pytest.mark.parametrize("case", CONCAT_REJECTS)
def test_concat_hazard_rejects(case: dict) -> None:
    """concat_hazard rejects a landcover in a different CRS."""
    da = synthetic_hazard()
    landcover = synthetic_empty_vector(n_cells=100, pixel_size=10).to_crs(
        epsg=case["to_crs"]
    )
    run_case(case, lambda: concat_hazard(landcover, da))


@pytest.mark.parametrize("case", FIND_COLUMN_CASES)
def test_find_column(case: dict) -> None:
    """find_column finds the first matching candidate or raises."""
    df = pd.DataFrame({col: [1] for col in case["columns"]})
    run_case(case, lambda: find_column(df, *case["candidates"]))
