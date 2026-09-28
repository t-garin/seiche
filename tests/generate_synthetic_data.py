"""
Synthetic data generation for tests.
"""

from pathlib import Path
from typing import Callable

import geopandas as gpd
import numpy as np
import pytest
import shapely
import xarray as xr
import yaml

from seiche.utils_da import generate_empty_da_from_bounds

REAL_XY = (500000, 6300000)  # central France, EPSG:2154

_RAISES = {
    "IndexError": IndexError,
    "KeyError": KeyError,
    "NameError": NameError,
    "NotImplementedError": NotImplementedError,
    "RuntimeError": RuntimeError,
    "SystemExit": SystemExit,
    "TypeError": TypeError,
    "ValueError": ValueError,
}


def load_test_data(data_file: str, *keys: str) -> object:
    """
    Load a nested value from ``tests/<data_file>``.

    Parameters
    ----------
    data_file : str
        Name of the data file in ``tests/``, e.g. ``test_utils_geom_data.yml``.
    *keys : str
        Path to the value, e.g. ``load_test_data("test_utils_geom_data.yml", "union")``.

    Returns
    -------
    object
        The parsed YAML value.

    """
    with (Path("tests") / data_file).open() as f:
        data = yaml.safe_load(f)
    for key in keys:
        data = data[key]
    return data


def run_case(case: dict, call: Callable[[], object]) -> None:
    """
    Execute ``call`` against one regression case.

    A regression case is a dict that either pins an exception or an expected
    result:

    - ``raises`` (optional): name of the exception ``call`` must raise.
    - ``match`` (optional): regex matched against the exception message.
    - ``expected``: the pinned result, compared with :func:`assert_matches`.

    Parameters
    ----------
    case : dict
        The regression case from a ``_data.yml`` file.
    call : Callable[[], object]
        Zero-argument callable returning the value under test. Drivers build
        the inputs from the case and close over them.

    """
    if "raises" in case:
        kwargs = {"match": case["match"]} if "match" in case else {}
        with pytest.raises(_RAISES[case["raises"]], **kwargs):
            call()
        return
    assert_matches(call(), case["expected"])


def assert_matches(result: object, expected: object) -> None:
    """
    Compare a function result to a pinned expected value.

    Flat space-joined snapshot strings and numeric values/arrays are compared
    with :func:`numpy.testing.assert_allclose`, everything else with ``==``.

    Parameters
    ----------
    result : object
        The value produced by the function under test.
    expected : object
        The pinned value from the regression case.

    """
    if isinstance(expected, str) and is_flat_snapshot(expected):
        np.testing.assert_allclose(
            np.asarray(result, dtype=float).flatten(),
            decode_flat(expected),
            equal_nan=True,
        )
    elif isinstance(result, np.ndarray) or isinstance(expected, (int, float)):
        np.testing.assert_allclose(result, expected, equal_nan=True)
    else:
        assert result == expected


def is_flat_snapshot(value: str) -> bool:
    """
    Return whether a string looks like a flat space-joined numeric snapshot.

    Parameters
    ----------
    value : str
        The string to test.

    Returns
    -------
    bool
        True when every whitespace-separated token parses as a number.

    """
    return all(
        token in ("nan", "inf", "-inf")
        or token.replace(".", "").replace("-", "").isdigit()
        for token in value.split()
    )


def decode_flat(value: str) -> np.ndarray:
    """
    Parse a flat space-joined snapshot string into a float array.

    Parameters
    ----------
    value : str
        Flat snapshot, e.g. ``"1.0 nan 2.0"``.

    Returns
    -------
    np.ndarray
        1D float array.

    """
    return np.fromstring(value, sep=" ")


def synthetic_state(
    tmp_path: Path,
    **config_overrides: object,
) -> dict[str, object]:
    """
    Build a minimal SEICHE state with a real polygon and an output directory.

    All rasters created with ``synthetic_raster`` and the returned state share
    the same location, so reprojections and clips stay meaningful.

    Parameters
    ----------
    tmp_path : Path
        Directory to host the input polygon and the ``out`` folder.
    **config_overrides
        Extra config keys, merged over the defaults.

    Returns
    -------
    dict
        A state with ``config``, ``config_path`` and ``done`` keys.

    """
    x, y = REAL_XY
    config: dict[str, object] = {
        "path.inp": str(tmp_path),
        "path.inp.POLY": "poly.geojson",
        "path.out": str(tmp_path / "out"),
        "param.EPSG": 2154,
        "param.expname": "test",
    }
    config.update(config_overrides)
    poly = gpd.GeoDataFrame(
        geometry=[shapely.geometry.box(x - 500, y - 500, x + 500, y + 500)],
        crs="EPSG:2154",
    )
    poly.to_file(tmp_path / "poly.geojson", driver="GeoJSON")
    return {
        "config": config,
        "config_path": str(tmp_path / "test.yml"),
        "done": {},
    }


def synthetic_raster(
    path: Path,
    values: float | np.ndarray,
    pixel_size: float = 100,
    n: int = 8,
    epsg: int = 2154,
    n_bands: int = 1,
    x: float | None = None,
    y: float | None = None,
) -> None:
    """
    Write a georeferenced GeoTIFF filled with ``values`` at a real location.

    Parameters
    ----------
    path : Path
        Destination .tif file.
    values : float | np.ndarray
        Fill value, or a (n_bands, n, n) array.
    pixel_size : float
        Pixel size in meters. Default 100.
    n : int
        Number of pixels per side. Default 8.
    epsg : int
        EPSG code (meters only). Default 2154.
    n_bands : int
        Number of bands. Default 1.
    x, y : float | None
        West/south coordinate of the raster. Defaults to ``REAL_XY``.

    """
    x = REAL_XY[0] if x is None else x
    y = REAL_XY[1] if y is None else y
    da = generate_empty_da_from_bounds(
        (x, y, x + n * pixel_size, y + n * pixel_size), pixel_size, epsg, n_bands
    )
    if isinstance(values, np.ndarray):
        data = values
    else:
        data = np.full((n_bands, n, n), values)
    da.copy(data=data).rio.write_nodata(255).rio.to_raster(path)


def _empty_raster(
    shape: tuple[int, int],
    pixel_size: float,
    epsg: int,
    n_bands: int = 1,
) -> xr.DataArray:
    """
    Return an empty raster aligned to an origin-anchored extent.

    Bounds span `(0, 0, shape[1]*pixel_size, shape[0]*pixel_size)`.
    """
    w = 0
    s = 0
    e = w + shape[1] * pixel_size
    n = s + shape[0] * pixel_size
    return generate_empty_da_from_bounds(
        (w, s, e, n), pixel_size, epsg, n_bands=n_bands
    )


def _fbm_noise(shape: tuple[int, int], seed: int, octaves: int = 3) -> np.ndarray:
    """
    Return fractal value-noise normalized to [0, 1], mimicking real elevation.

    Value noise on a coarse random grid, bilinearly interpolated, summed over
    octaves with decreasing amplitude. Implemented with numpy only (no Perlin
    dependency) so the test suite stays dependency-light.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.indices(shape, dtype=float)
    total = np.zeros(shape)
    amplitude, frequency = 1.0, 1.0
    for _ in range(octaves):
        grid_h, grid_w = (
            max(2, int(np.sqrt(shape[0] * shape[1]) / frequency)),
            max(2, int(np.sqrt(shape[0] * shape[1]) / frequency)),
        )
        grid = rng.random((grid_h, grid_w))
        sample_y = yy / shape[0] * (grid_h - 1)
        sample_x = xx / shape[1] * (grid_w - 1)
        y0, x0 = sample_y.astype(int), sample_x.astype(int)
        y1, x1 = np.clip(y0 + 1, 0, grid_h - 1), np.clip(x0 + 1, 0, grid_w - 1)
        fy, fx = sample_y - y0, sample_x - x0
        top = grid[y0, x0] * (1 - fx) + grid[y0, x1] * fx
        bottom = grid[y1, x0] * (1 - fx) + grid[y1, x1] * fx
        total += (top * (1 - fy) + bottom * fy) * amplitude
        amplitude *= 0.5
        frequency *= 2
    return (total - total.min()) / (total.max() - total.min())


def _flood_lowlands(dem: xr.DataArray, water_level: float) -> np.ndarray:
    """
    Return a wet mask flooding all pixels below water_level.

    Water pools in the valleys, giving a flat-water-surface flood that is
    physically consistent with the DEM.
    """
    return (dem.isel(band=0).values < water_level).astype(int)


def _flood_blobs(shape: tuple[int, int], seed: int, fraction: float) -> np.ndarray:
    """
    Return a wet mask of seeded region-grown blobs covering `fraction` of pixels.

    Start from a few random source pixels and grow them out by adding random
    neighbours until the target flooded fraction is reached. Gives varied
    connected components, independent of the DEM relief.
    """
    rng = np.random.default_rng(seed)
    target = round(shape[0] * shape[1] * fraction)
    wet = np.zeros(shape, dtype=int)
    h, w = shape
    sources = rng.integers([0, 0], [h, w], size=(max(2, int(fraction * 6)), 2))
    for y, x in sources:
        wet[y, x] = 1
    frontier = [(y, x) for y, x in sources if wet[y, x]]
    while wet.sum() < target and frontier:
        cy, cx = frontier.pop(rng.integers(len(frontier)))
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w and not wet[ny, nx]:
                wet[ny, nx] = 1
                frontier.append((ny, nx))
                if wet.sum() >= target:
                    break
    return wet


def _flood_random(shape: tuple[int, int], seed: int, fraction: float) -> np.ndarray:
    """
    Return a wet mask of randomly scattered wet pixels covering `fraction`.

    Pure speckle, independent of the DEM relief.
    """
    rng = np.random.default_rng(seed)
    n = round(shape[0] * shape[1] * fraction)
    flat = rng.permutation(shape[0] * shape[1])[:n]
    y, x = np.unravel_index(flat, shape)
    wet = np.zeros(shape, dtype=int)
    wet[y, x] = 1
    return wet


def synthetic_dem(
    shape: tuple[int, int] = (10, 10),
    pixel_size: float = 10.0,
    epsg: int = 2154,
    base: float = 0.0,
    relief: float = 100.0,
    seed: int = 0,
    n_octaves: int = 3,
) -> xr.DataArray:
    """
    Generate a synthetic DEM (rioxarray DataArray, band dim) for tests.

    Fractal noise relief mimics real elevation so defended methods behave as on
    actual terrain. Fixed seed → reproducible.

    Parameters
    ----------
    shape : tuple[int, int]
        (height, width) in pixels. Default (10, 10).
    pixel_size : float
        Pixel size in meters. Default 10.
    epsg : int
        EPSG code (meters only). Default 2154.
    base : float
        Elevation offset. Default 0.
    relief : float
        Amplitude of the noise (meters). Default 100.
    seed : int
        RNG seed for the noise. Default 0.
    n_octaves : int
        Number of noise octaves. Default 3.

    Returns
    -------
    xr.DataArray
        3D DEM (band, y, x) with CRS and transform set.

    """
    da = _empty_raster(shape, pixel_size, epsg)
    values = base + relief * _fbm_noise(shape, seed, n_octaves)
    return da.copy(data=[values])


def synthetic_population_raster(
    shape: tuple[int, int] = (10, 10),
    pixel_size: float = 10.0,
    epsg: int = 2154,
    seed: int = 0,
) -> xr.DataArray:
    """
    Generate a synthetic GHSL population raster for tests.

    Values are random non-negative integers, fixed seed → reproducible.

    Parameters
    ----------
    shape : tuple[int, int]
        (height, width) in pixels. Default (10, 10).
    pixel_size : float
        Pixel size in meters. Default 10.
    epsg : int
        EPSG code (meters only). Default 2154.
    seed : int
        RNG seed. Default 0.

    Returns
    -------
    xr.DataArray
        3D population raster (band, y, x) with CRS and transform set.

    """
    da = _empty_raster(shape, pixel_size, epsg)
    rng = np.random.default_rng(seed)
    values = rng.integers(0, 100, size=shape)
    return da.copy(data=[values])


def synthetic_empty_vector(
    n_cells: int = 10,
    pixel_size: float = 10.0,
    epsg: int = 2154,
) -> gpd.GeoDataFrame:
    """
    Generate an empty regular grid GeoDataFrame of square cells.

    Cells cover the same extent as the synthetic rasters, i.e. a
    sqrt(n) x sqrt(n) grid of `pixel_size` squares in `epsg`.

    Parameters
    ----------
    n_cells : int
        Number of square cells, arranged on a sqrt(n) x sqrt(n) grid. Default 10.
    pixel_size : float
        Cell size in meters. Default 10.
    epsg : int
        EPSG code (meters only). Default 2154.

    Returns
    -------
    gpd.GeoDataFrame
        Grid of polygon cells in `epsg`.

    """
    side = int(np.sqrt(n_cells))
    cells = [
        shapely.geometry.box(
            j * pixel_size,
            i * pixel_size,
            (j + 1) * pixel_size,
            (i + 1) * pixel_size,
        )
        for i in range(side)
        for j in range(side)
    ]
    return gpd.GeoDataFrame(geometry=cells, crs=f"EPSG:{epsg}")


def synthetic_population_vector(
    n_cells: int = 10,
    pixel_size: float = 10.0,
    epsg: int = 2154,
    seed: int = 0,
) -> gpd.GeoDataFrame:
    """
    Generate a synthetic Filosofi population vector for tests.

    A regular grid of square cells covering the same extent as the synthetic
    rasters, each with a random non-negative 'ind' population count. Fixed seed →
    reproducible.

    Parameters
    ----------
    n_cells : int
        Number of square cells, arranged on a sqrt(n) x sqrt(n) grid. Default 100.
    pixel_size : float
        Cell size in meters. Default 10.
    epsg : int
        EPSG code (meters only). Default 2154.
    seed : int
        RNG seed. Default 0.

    Returns
    -------
    gpd.GeoDataFrame
        Vector population with an 'ind' column and polygon geometry in `epsg`.

    """
    cells = synthetic_empty_vector(n_cells=n_cells, pixel_size=pixel_size, epsg=epsg)
    rng = np.random.default_rng(seed)
    pop = rng.integers(0, 100, size=len(cells))
    return gpd.GeoDataFrame({"ind": pop}, geometry=cells.geometry, crs=cells.crs)


def synthetic_hazard(
    shape: tuple[int, int] = (10, 10),
    pixel_size: float = 10.0,
    epsg: int = 2154,
    seed: int = 0,
) -> xr.DataArray:
    """
    Generate a synthetic hazard raster for tests.

    Three bands (0: H max depth, 1: V max velocity, 2: T duration) with
    distinct magnitude ranges so conditions on h, v and t all exercise non-trivial
    masks. Fixed seed → reproducible.

    Parameters
    ----------
    shape : tuple[int, int]
        (height, width) in pixels. Default (10, 10).
    pixel_size : float
        Pixel size in meters. Default 10.
    epsg : int
        EPSG code (meters only). Default 2154.
    seed : int
        RNG seed. Default 0.

    Returns
    -------
    xr.DataArray
        3D hazard raster (band, y, x) with CRS and transform set.

    """
    da = _empty_raster(shape, pixel_size, epsg, n_bands=3)
    rng = np.random.default_rng(seed)
    h = rng.uniform(0, 2, size=shape)
    v = rng.uniform(0, 1.5, size=shape)
    t = rng.uniform(0, 24, size=shape)
    return da.copy(data=[h, v, t])


def synthetic_hazard_at(
    x: float,
    y: float,
    shape: tuple[int, int] = (10, 10),
    pixel_size: float = 100,
    epsg: int = 2154,
    seed: int = 0,
) -> xr.DataArray:
    """
    Generate a synthetic hazard raster at a real location, properly georeferenced.

    Unlike ``synthetic_hazard`` (anchored at the origin), the transform matches
    the ``(x, y)`` origin, so operations relying on ``rio`` windows work.

    Parameters
    ----------
    x, y : float
        West/south coordinate of the raster.
    shape : tuple[int, int]
        (height, width) in pixels. Default (10, 10).
    pixel_size : float
        Pixel size in meters. Default 100.
    epsg : int
        EPSG code (meters only). Default 2154.
    seed : int
        RNG seed. Default 0.

    Returns
    -------
    xr.DataArray
        3D hazard raster (band, y, x) with CRS and transform set.

    """
    da = generate_empty_da_from_bounds(
        (x, y, x + shape[1] * pixel_size, y + shape[0] * pixel_size),
        pixel_size,
        epsg,
        n_bands=3,
    )
    rng = np.random.default_rng(seed)
    h = rng.uniform(0, 2, size=shape)
    v = rng.uniform(0, 1.5, size=shape)
    t = rng.uniform(0, 24, size=shape)
    return da.copy(data=[h, v, t])


def synthetic_wet_mask(
    dem: xr.DataArray,
    style: str,
    extent: str,
    water_level: float | None = None,
    fraction: float | None = None,
    seed: int = 0,
) -> xr.DataArray:
    """
    Generate a synthetic wet mask (bfm-style: 0 dry, 1 flooded) for a DEM.

    Three styles:
        - 'threshold': floods pixels below `water_level` (valleys).
        - 'blob': region-grown blobs covering `fraction` of pixels.
        - 'random': randomly scattered wet pixels covering `fraction` of pixels.

    Parameters
    ----------
    dem : xr.DataArray
        The DEM to flood.
    style : str
        'threshold', 'blob' or 'random'.
    extent : str
        'small' or 'large' flood.
    water_level : float | None
        Water level for 'threshold' style. Ignored otherwise.
    fraction : float | None
        Target flooded fraction for 'blob' and 'random' styles. Ignored otherwise.
    seed : int
        RNG seed for 'blob' and 'random' styles.

    Returns
    -------
    xr.DataArray
        Wet mask (band, y, x) matching dem coords.

    """
    shape = dem.sizes["y"], dem.sizes["x"]
    if style == "threshold":
        assert water_level is not None
        values = _flood_lowlands(dem, water_level)
    elif style == "blob":
        assert fraction is not None
        values = _flood_blobs(shape, seed, fraction)
    elif style == "random":
        assert fraction is not None
        values = _flood_random(shape, seed, fraction)
    else:
        raise ValueError(f"Unknown style: {style}")
    return dem.copy(data=[values])
