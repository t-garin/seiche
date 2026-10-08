#!/usr/bin/env python
"""
SEICHE - Socio Economic Impacts of Catastrophic Hydrological Events.

The pipeline is orchestrated as a functional chain of parts. Each part is a
``(state: dict) -> dict`` function that receives the whole state, does its
computation, and returns an updated state. The chain is a list of
``(name, part)`` pairs run in order by :func:`run_pipeline`. After each part,
the whole state is dumped to ``state.yml`` in the output directory so a crash can
be resumed from the last completed part.
"""

import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from seiche.format_dem import generate_or_load_dem
from seiche.main_hazards import generate_hazard
from seiche.main_impact_eco import impact_eco
from seiche.main_impact_pop import impact_pop
from seiche.main_plot import plot
from seiche.main_report import report
from seiche.utils_qol import parse_args, setup_logging
from seiche.utils_state import dump_state, initialize_state

logger = logging.getLogger(__name__)


PIPELINE: tuple[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]], ...] = (
    ("dem", generate_or_load_dem),
    ("hazard", generate_hazard),
    ("impact_eco", impact_eco),
    ("impact_pop", impact_pop),
    ("plot", plot),
    ("report", report),
)


def run_pipeline(state: dict[str, Any]) -> dict[str, Any]:
    """
    Run each part of the pipeline, skipping already completed parts.

    After each part, the whole state is dumped to ``state.yml``.
    """
    for name, part in PIPELINE:
        if state["done"].get(name):
            logger.info("Skipping %s, already done", name)
            continue
        logger.info("Running part | %s", name)
        state = part(state)
        state["done"][name] = True
        dump_state(state)
    return state


def main(
    config_path: str | Path,
    *,
    verbose: bool = False,
    overrides: Iterable[str] | None = None,
) -> None:
    """
    Run the SEICHE pipeline.

    Parameters
    ----------
    config_path: str
        Path pointing to the .yml config file.

    verbose : bool
        If true, logging is displayed at level DEBUG, otherwise INFO.

    overrides : Iterable[str] | None, default: None
        ``"key: value"`` items overriding config values, see
        :func:`seiche.utils_state.get_config`.

    """
    setup_logging(level=logging.DEBUG if verbose else logging.INFO)
    logger.info("New run of seiche")
    state = initialize_state(config_path, overrides=overrides)
    run_pipeline(state)
    logger.info("SEICHE is done, bye bye")


def cli() -> None:
    """
    Entrypoint for the command-line interface.
    """
    args = parse_args()
    main(
        Path(args.configfile),
        verbose=args.verbose,
        overrides=args.override,
    )


if __name__ == "__main__":  # pragma: no cover
    cli()
