"""
Tests for the automatic plotting.
"""

import warnings
from pathlib import Path

import hvplot.pandas  # noqa: F401 - registers the polygon hvplot backend
import hvplot.xarray
import matplotlib.colors as mcolors
import numpy as np
import pytest
import xarray as xr
from matplotlib.transforms import Bbox

from holoviews.plotting.mpl.renderer import MPLRenderer

from generate_synthetic_data import (
    load_test_data,
    run_case,
    synthetic_empty_vector,
    synthetic_hazard_at,
    synthetic_raster,
    synthetic_state,
)

from seiche.main_plot import (
    _plot_rpg,
    _save_hvplot,
    plot,
)
from seiche.utils_plot import Colors

PLOT_CASES = load_test_data("test_main_plot_data.yml", "plot")
SAVE_HVPLOT_CASES = load_test_data("test_main_plot_data.yml", "save_hvplot")


def _write_outputs(tmp_path: Path) -> None:
    """Write the pipeline outputs that the plot functions read."""
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    dem = synthetic_hazard_at(500000, 6300000, shape=(10, 10))
    dem.isel(band=0).expand_dims("band").rio.to_raster(out / "dem_test.tif")
    hazard = synthetic_hazard_at(500000, 6300000)
    hazard.rio.to_raster(out / "hzd_hf_test.tif")
    synthetic_raster(out / "lcv_esawc_test.tif", 50.0, n=10, x=499500, y=6299500)
    synthetic_raster(out / "lcv_oso23_test.tif", 1.0, n=10, x=499500, y=6299500)
    gdf = synthetic_empty_vector(n_cells=4, pixel_size=100)
    gdf["CODE_GROUP"] = [1, 2, 5, 16]
    gdf = gdf.set_geometry(gdf.geometry.translate(499500, 6299500))
    gdf.to_file(out / "lcv_rpg_test.gpkg")
    synthetic_raster(
        out / "ghslpop_hf_always_true_test.tif", 5.0, n=10, x=499500, y=6299500
    )
    synthetic_raster(
        out / "filosofi_hf_always_true_test.tif", 5.0, n=10, x=499500, y=6299500
    )


def _state(tmp_path: Path, **overrides: object) -> dict[str, object]:
    """Return a state pointing at the written outputs."""
    _write_outputs(tmp_path)
    return synthetic_state(
        tmp_path,
        **{
            "param.autoplot": True,
            "path.inp.lcv.esawc": ["esawc.tif"],
            "path.inp.lcv.oso23": ["oso23.tif"],
            "path.inp.lcv.rpg": ["rpg.shp"],
            "path.inp.lcv.bdtopo": None,
            "path.inp.lcv.sirene": None,
            "path.inp.pop.ghslpop": ["ghslpop.tif"],
            "path.inp.pop.filosofi": None,
            **overrides,
        },
    )


@pytest.mark.parametrize("case", PLOT_CASES, ids=[c["name"] for c in PLOT_CASES])
def test_plot(tmp_path: Path, case: dict) -> None:
    """plot() renders (or skips) the configured plots as pngs."""
    state = _state(tmp_path, **{"param.autoplot": case["autoplot"]})
    if case.get("no_dem"):
        (tmp_path / "out" / "dem_test.tif").unlink()
    plot(state)
    pngs = sorted(p.name for p in (tmp_path / "out").glob("*.png"))
    assert pngs == sorted(case["expected_pngs"])


@pytest.mark.parametrize("case", SAVE_HVPLOT_CASES)
def test_save_hvplot_typeerror(tmp_path: Path, case: dict) -> None:
    """_save_hvplot rejects a non-string filename."""
    state = _state(tmp_path)
    run_case(case, lambda: _save_hvplot(state, fig=object(), filename=case["filename"]))


def test_save_hvplot_clears_renderer_bbox_cache(tmp_path: Path) -> None:
    """
    _save_hvplot clears the holoviews tight-bbox cache before saving.

    Holoviews caches tight bounding boxes keyed by the matplotlib figure id
    and never clears them; a new figure that reuses a dead figure's id would
    inherit its bbox and render non-deterministic PNG margins. The stale
    entry must be dropped on each save.
    """
    state = _state(tmp_path)
    hvplot.extension("matplotlib")
    fig = xr.DataArray(np.ones((5, 5)), dims=("y", "x"), name="_").hvplot()
    MPLRenderer.drawn[987654321] = Bbox([[0.0, 0.0], [1.0, 1.0]])
    _save_hvplot(state, fig, "cache_regression")
    assert 987654321 not in MPLRenderer.drawn


def test_plot_rpg_colors_map_exactly_to_code_group(monkeypatch, tmp_path):
    """RPG polygons are colored by their exact CODE_GROUP even when the
    dataset does not span the full 1-28 range (clim pins the norm)."""
    codes = [11, 18, 19, 25, 28, 2, 3, 4, 5]
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    rpg = synthetic_empty_vector(n_cells=len(codes), pixel_size=100)
    rpg["CODE_GROUP"] = codes
    rpg = rpg.set_geometry(rpg.geometry.translate(499500, 6299500))
    rpg.to_file(out / "lcv_rpg_test.gpkg")

    state = synthetic_state(
        tmp_path,
        **{
            "param.autoplot": True,
            "path.inp.lcv.rpg": ["rpg.shp"],
            "path.inp.lcv.bdtopo": None,
            "path.inp.lcv.sirene": None,
            "path.inp.pop.ghslpop": None,
            "path.inp.pop.filosofi": None,
        },
    )

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "seiche.main_plot._save_hvplot",
        lambda st, fig, filename: captured.__setitem__("fig", fig),
    )
    _plot_rpg(state)

    hvplot.extension("matplotlib")
    rendered = hvplot.render(captured["fig"], backend="matplotlib")
    facecolors = np.asarray(rendered.axes[0].collections[0].get_facecolor())[:, :3]
    expected = np.asarray(
        [mcolors.to_rgb(Colors.rpg_code_group_list.colors[c - 1]) for c in codes]
    )
    assert np.allclose(facecolors, expected, atol=1e-6)


def test_plot_hzd_skips_all_nan_band(tmp_path: Path) -> None:
    """An entirely nodata hazard band (e.g. no speed for fwdet) is not plotted."""
    state = _state(tmp_path)
    hazard = synthetic_hazard_at(500000, 6300000)
    hazard = hazard.copy(
        data=[
            hazard.isel(band=0).values,
            np.full_like(hazard.isel(band=0).values, np.nan),
            hazard.isel(band=2).values,
        ]
    )
    hazard.rio.to_raster(tmp_path / "out" / "hzd_hf_test.tif")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plot(state)
    pngs = sorted(p.name for p in (tmp_path / "out").glob("*.png"))
    assert "hzd_hf_test.tif_V.png" not in pngs
    assert "hzd_hf_test.tif_H.png" in pngs
    assert "hzd_hf_test.tif_T.png" in pngs
    assert not any("All-NaN" in str(w.message) for w in caught)
