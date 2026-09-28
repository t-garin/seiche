"""
Tests for the geometric utilities.
"""


import numpy as np
import pytest

from generate_synthetic_data import load_test_data

from seiche.utils_geom import bbox_intersection, bbox_union

INTERSECTION_CASES = load_test_data("test_utils_geom_data.yml", "intersection")
UNION_CASES = load_test_data("test_utils_geom_data.yml", "union")


def _bbox(case: dict, key: str) -> object:
    """Return a bbox from a case, as an ndarray when flagged."""
    bbox = case[key]
    return np.array(bbox) if case.get("as_np") else bbox


@pytest.mark.parametrize("case", INTERSECTION_CASES)
def test_bbox_intersection(case: dict) -> None:
    """The intersection spans the overlapping region."""
    assert bbox_intersection(_bbox(case, "bbox1"), _bbox(case, "bbox2")) == tuple(
        case["expected"]
    )


@pytest.mark.parametrize("case", UNION_CASES)
def test_bbox_union(case: dict) -> None:
    """The union spans both bounding boxes."""
    assert bbox_union(_bbox(case, "bbox1"), _bbox(case, "bbox2")) == tuple(
        case["expected"]
    )
