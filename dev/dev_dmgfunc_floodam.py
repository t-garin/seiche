"""
Dead code moved out of ``src/seiche/dmgfunc_floodam.py``.

These were methods of the :class:`seiche.dmgfunc_floodam.Floodam` class that
were never called by the pipeline and were only exercised by unit tests. They
are kept here as reference and can be re-integrated if needed. The ``self``
methods are rewritten as plain functions taking a ``Floodam`` instance as
first argument.
"""

import logging

logger = logging.getLogger(__name__)


def info(floodam: object) -> None:
    """
    Print information about the Floodam class and its usage.

    Former ``Floodam.info``.
    """
    with (floodam.DATADIR / "floodam-info.txt").open() as f:
        logger.info(f.read())


def get_inputs(floodam: object, ds: object) -> list[str]:
    """
    Return damage function inputs.

    Former ``Floodam.get_inputs``.
    e.g.: get_inputs(floodam, floodam.a)
    """
    return [str(d) for d in ds.dims]


def get_dmg_waterwaste(*args: object, **kwargs: object) -> float:
    """
    Former ``Floodam._get_dmg_waterwaste``, not implemented yet.
    """
    msg = "have to implement _get_dmg_waterwaste"
    raise NotImplementedError(msg)
