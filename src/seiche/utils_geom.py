"""
Tools for geometric operations.
"""

from collections.abc import Sequence

import numpy as np


def bbox_intersection(
    bbox1: Sequence[float] | np.ndarray,
    bbox2: Sequence[float] | np.ndarray,
) -> tuple[float, float, float, float]:
    """
    Compute the intersection of two bounding boxes.

    The order: (W, S, E, N), (xmin, ymin, xmax, ymax), (left, down, right, up)
    match the conventions of GeoPandas and RioXarray.

    Parameters
    ----------
    bbox1 : Sequence[float]
        First bounding box (west, south, east, north).
    bbox2 : Sequence[float]
        Second bounding box (west, south, east, north).

    Returns
    -------
    tuple[float, float, float, float]
        The intersection bounding box (west, south, east, north).

    """
    return (
        float(max(bbox1[0], bbox2[0])),
        float(max(bbox1[1], bbox2[1])),
        float(min(bbox1[2], bbox2[2])),
        float(min(bbox1[3], bbox2[3])),
    )


def bbox_union(
    bbox1: Sequence[float] | np.ndarray,
    bbox2: Sequence[float] | np.ndarray,
) -> tuple[float, float, float, float]:
    """
    Compute the union of two bounding boxes.

    The order: (W, S, E, N), (xmin, ymin, xmax, ymax), (left, down, right, up)
    match the conventions of GeoPandas and RioXarray.

    Parameters
    ----------
    bbox1 : Sequence[float]
        First bounding box (west, south, east, north).
    bbox2 : Sequence[float]
        Second bounding box (west, south, east, north).

    Returns
    -------
    tuple[float, float, float, float]
        The union bounding box (west, south, east, north).

    """
    return (
        float(min(bbox1[0], bbox2[0])),
        float(min(bbox1[1], bbox2[1])),
        float(max(bbox1[2], bbox2[2])),
        float(max(bbox1[3], bbox2[3])),
    )
