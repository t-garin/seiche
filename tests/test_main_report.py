"""
Tests for the automatic Typst report generation.
"""

import base64
from pathlib import Path

import pytest

from generate_synthetic_data import load_test_data, synthetic_state

import seiche.main_report as mr
from seiche.main_report import (
    _build_doc,
    _compile,
    _group_plots,
    _metadata,
    _quote,
    _write_template,
    report,
)
from seiche.utils_enum import OutputFiles

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhf"
    "DwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

QUOTE_CASES = load_test_data("test_main_report_data.yml", "quote")
GROUP_CASES = load_test_data("test_main_report_data.yml", "group_plots")
METADATA_CASES = load_test_data("test_main_report_data.yml", "metadata")
BUILD_DOC_CASES = load_test_data("test_main_report_data.yml", "build_doc")


def _state(tmp_path: Path, **overrides: object) -> dict[str, object]:
    """Return a state with all the config keys the report needs."""
    return synthetic_state(
        tmp_path,
        **{
            "param.autoreport": True,
            "path.inp.slf": None,
            "path.inp.bfm.root": None,
            "use.dmg.floodam": True,
            "use.dmg.jrc": False,
            "path.inp.lcv.esawc": ["esawc.tif"],
            "path.inp.lcv.oso23": None,
            "path.inp.lcv.rpg": None,
            "path.inp.lcv.bdtopo": None,
            "path.inp.lcv.sirene": None,
            "path.inp.pop.ghslpop": None,
            "path.inp.pop.filosofi": None,
            "param.pop.conditions": {"always_true": "True"},
            **overrides,
        },
    )


def _write_pngs(tmp_path: Path, *names: str) -> None:
    """Write fake single-pixel pngs into the output directory."""
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    for name in names:
        (out / name).write_bytes(_ONE_PIXEL_PNG)


@pytest.mark.parametrize("case", QUOTE_CASES)
def test_quote(case: dict) -> None:
    """_quote escapes quotes and backslashes into a Typst literal."""
    assert _quote(case["text"]) == case["expected"]


@pytest.mark.parametrize("case", GROUP_CASES)
def test_group_plots(case: dict) -> None:
    """Plots are grouped by their output file prefix."""
    plots = [Path(name) for name in case["plots"]]
    groups = _group_plots(plots)
    for key, expected in case["expected"].items():
        group = groups[key] if key == "Other" else groups[OutputFiles(key)]
        assert [p.name for p in group] == expected
    for output in OutputFiles:
        if output.value not in case["expected"]:
            assert groups[output] == []


@pytest.mark.parametrize("case", METADATA_CASES)
def test_metadata(tmp_path: Path, case: dict) -> None:
    """The metadata lines are read from the state config."""
    state = synthetic_state(tmp_path, **case["config"])
    assert dict(_metadata(state)) == case["expected"]


@pytest.mark.parametrize("case", BUILD_DOC_CASES)
def test_build_doc_calls_template(case: dict) -> None:
    """_build_doc generates the Typst document from the run's data."""
    groups: dict[OutputFiles | str, list[Path]] = {}
    for key, plots in case["groups"].items():
        groups[key if key == "Other" else OutputFiles(key)] = [
            Path(name) for name in plots
        ]
    doc = _build_doc(
        case["experiment"], [tuple(pair) for pair in case["metadata"]], groups
    )
    assert doc == case["expected"]


def test_write_template(tmp_path: Path) -> None:
    """_write_template writes the Typst report template."""
    _write_template(tmp_path)
    template = (tmp_path / "report_template.typ").read_text(encoding="utf-8")
    assert "#let report" in template


def test_compile(monkeypatch) -> None:
    """_compile calls typst.compile with the expected arguments."""
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        mr.typst,
        "compile",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    _compile(Path("/out"), Path("/out/x.typ"), Path("/out/x.pdf"))
    assert calls == [
        (
            (Path("/out/x.typ"),),
            {
                "root": Path("/out"),
                "output": Path("/out/x.pdf"),
                "timestamp": mr._PDF_TIMESTAMP,
            },
        )
    ]


def test_report_compiles_pdf(tmp_path: Path) -> None:
    """report() writes the template, typ and pdf files."""
    _write_pngs(tmp_path, "dem_test.tif.png", "hzd_hf_test.tif_H.png")
    state = _state(tmp_path)
    assert report(state) is state
    out = tmp_path / "out"
    assert (out / "report_template.typ").exists()
    typ_path = out / "report_test.typ"
    pdf_path = out / "report_test.pdf"
    assert typ_path.exists()
    assert pdf_path.exists()
    assert "hzd_hf_test.tif_H.png" in typ_path.read_text(encoding="utf-8")


def test_report_skips_when_autoreport_disabled(tmp_path: Path) -> None:
    """report() does nothing when autoreport is disabled."""
    _write_pngs(tmp_path, "dem_test.tif.png")
    state = _state(tmp_path, **{"param.autoreport": False})
    assert report(state) is state
    assert not list((tmp_path / "out").glob("report_*"))
