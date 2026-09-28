"""
Dead code moved out of ``src/seiche/dmgfunc_jrc.py``.

These were methods of the :class:`seiche.dmgfunc_jrc.JRC` class that were never
called by the pipeline and were only exercised by unit tests. They are kept
here as reference and can be re-integrated if needed. The ``self`` methods are
rewritten as plain functions taking a ``JRC`` instance as first argument.
"""

import logging

import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def info(jrc: object) -> None:
    """
    Print information about the JRC class and the data it uses.

    Former ``JRC.info``.
    """
    with jrc.INFOPATH.open() as f:
        logger.info(f.read())


def plot_dmgfac(
    jrc: object,
    classe: str,
    region: object,
    xmin: float = 0,
    xmax: float = 6,
) -> None:
    """
    Plot the damage factor and standard deviation for a given class and region.

    Former ``JRC.plot_dmgfac``.
    """
    x = np.linspace(xmin, xmax, 50)
    dmg, std = jrc._get_dmgfac_classe_interpolators(classe=classe, region=region)
    fig, (dax, sax) = plt.subplots(1, 2, figsize=(10, 4))
    dax.plot(x, dmg(x))
    sax.plot(x, std(x))
    for ax in [dax, sax]:
        ax.set_xlabel("depth (m)")
        ax.grid(visible=True)
    fig.suptitle(f"classe:{classe} - region:{region}")
    dax.set_title("Damage factor value")
    sax.set_title("Damage factor standard deviation")


def get_max_dmg_vector_lc() -> None:
    """
    Former ``JRC.get_max_dmg_vector_lc``, a placeholder (returns None).

    Todo.
    """
