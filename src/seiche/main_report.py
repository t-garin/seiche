"""
Automatic report generation with Typst from the SEICHE outputs.

The report gathers the experiment configuration (the same data as
``state.yml``) and the plots produced by :mod:`seiche.main_plot`, embeds them
in a Typst document and compiles it to PDF.

The document layout lives in ``report_template.typ``; the generated
``report_<expname>.typ`` only passes the run's data to it.
"""

import logging
from importlib import resources
from pathlib import Path
from typing import Any

import typst

from seiche.utils_enum import OutputFiles
from seiche.utils_state import (
    read_dmgfuncs_from_state,
    read_expname_from_state,
    read_hazards_from_state,
    read_landcovers_from_state,
    read_pop_conditions_from_state,
    read_pop_datasets_from_state,
)

logger = logging.getLogger(__name__)

_TEMPLATE_NAME = "report_template.typ"

# fixed PDF metadata date so report hashes stay reproducible across runs
_PDF_TIMESTAMP = 1704067200  # 2024-01-01 UTC

_GROUP_NAMES: dict[OutputFiles, str] = {
    OutputFiles.dem: "Digital Elevation Model",
    OutputFiles.lcv: "Landcover",
    OutputFiles.hzd: "Hazard",
    OutputFiles.duration: "Duration",
    OutputFiles.ghslpop: "Population - GHSL",
    OutputFiles.filosofi: "Population - Filosofi",
    OutputFiles.dmg: "Damage",
}


def _quote(text: str) -> str:
    """
    Quote a string as a Typst string literal.
    """
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _group_plots(plots: list[Path]) -> dict[OutputFiles | str, list[Path]]:
    """
    Group plots by output file type inferred from their filename prefix.
    """
    groups: dict[OutputFiles | str, list[Path]] = {f: [] for f in OutputFiles}
    groups["Other"] = []
    for plot in plots:
        for output in OutputFiles:
            if plot.name.startswith(output.value):
                groups[output].append(plot)
                break
        else:
            groups["Other"].append(plot)
    return groups


def _metadata(state: dict[str, Any]) -> list[tuple[str, str]]:
    """
    Return the configuration lines displayed at the top of the report.
    """
    return [
        ("Experiment", read_expname_from_state(state)),
        ("Hazard sources", ", ".join(map(str, read_hazards_from_state(state)))),
        ("Damage functions", ", ".join(map(str, read_dmgfuncs_from_state(state)))),
        ("Landcovers", ", ".join(map(str, read_landcovers_from_state(state)))),
        (
            "Population datasets",
            ", ".join(map(str, read_pop_datasets_from_state(state))),
        ),
        (
            "Pop conditions",
            ", ".join(read_pop_conditions_from_state(state)),
        ),
    ]


def _build_doc(
    experiment: str,
    metadata: list[tuple[str, str]],
    groups: dict[OutputFiles | str, list[Path]],
) -> str:
    """
    Build the Typst document calling the template with the run's data.
    """
    lines = [
        f'#import "{_TEMPLATE_NAME}": report',
        "#report(",
        f"  experiment: {_quote(experiment)},",
        "  metadata: (",
    ]
    lines.extend(f"    ({_quote(key)}, {_quote(value)})," for key, value in metadata)
    lines.append("  ),")
    lines.append("  sections: (")
    for group, plots in groups.items():
        if not plots:
            continue
        name = _GROUP_NAMES.get(group, str(group))
        lines.append(f"    {_quote(name)}: (")
        lines.extend(
            f"      (path: {_quote(plot.name)}, "
            f"caption: {_quote(plot.name.removesuffix('.png').replace('_', ' '))}),"
            for plot in plots
        )
        lines.append("    ),")
    lines.append("  ),")
    lines.append(")")
    return "\n".join(lines)


def _write_template(out: Path) -> None:
    """
    Copy the packaged Typst template next to the generated report.
    """
    template = (
        resources.files(__package__)
        .joinpath(_TEMPLATE_NAME)
        .read_text(encoding="utf-8")
    )
    (out / _TEMPLATE_NAME).write_text(template, encoding="utf-8")


def _compile(out: Path, typ_path: Path, pdf_path: Path) -> None:
    """
    Compile a Typst document to PDF with the typst package.
    """
    typst.compile(typ_path, root=out, output=pdf_path, timestamp=_PDF_TIMESTAMP)


def report(state: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a Typst report of the SEICHE outputs.

    The report consumes the same data as ``state.yml``, plus the plots found in
    the output directory. It is skipped when ``param.autoreport`` is disabled.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    dict
        The unchanged state.

    """
    if not state["config"]["param.autoreport"]:
        logger.info("Skipping automatic report generation")
        return state
    out = Path(state["config"]["path.out"]).resolve()
    expname = read_expname_from_state(state)
    typ_path = out / OutputFiles.report.filename(state, ext="typ")
    pdf_path = out / OutputFiles.report.filename(state, ext="pdf")
    _write_template(out)
    groups = _group_plots(sorted(out.glob("*.png")))
    typ_path.write_text(_build_doc(expname, _metadata(state), groups), encoding="utf-8")
    _compile(out, typ_path, pdf_path)
    logger.info("📄 %s", pdf_path.name)
    return state
