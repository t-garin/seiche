"""
Quality of life stuff.
"""

import argparse
import hashlib
import logging
import sys
from pathlib import Path
from typing import override

import geopandas as gpd


def asinstance[T](obj: object, cls: type[T]) -> T:
    """
    Return ``obj`` if it is an instance of ``cls``, raising otherwise.

    Used to narrow values whose static type is a union but whose runtime
    type is known (e.g. ``Dataset | DataArray``).
    """
    if not isinstance(obj, cls):
        msg = f"expected an instance of {cls.__name__}, got {type(obj).__name__}"
        raise TypeError(msg)
    return obj


def require[T](x: T | None) -> T:
    """
    Return ``x``, raising if it is ``None``.

    Used to narrow optional values that are known to be present at this point.
    """
    if x is None:
        msg = "expected a value, got None"
        raise TypeError(msg)
    return x


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure the logging.
    """
    logging.basicConfig(
        level=level,
        format=(
            "[%(asctime)s] %(message)-60s "
            "(%(levelname)s - %(filename)s:%(lineno)d in %(funcName)s)"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler()],
        force=True,
    )

    # Allow only messages comming from the "seiche" (or root) provider
    # Otherwise having level=DEBUG becomes a bit overwhelming
    class RootOnlyFilter(logging.Filter):
        @override
        def filter(self, record: logging.LogRecord) -> bool:
            return record.name == "root" or record.name.startswith("seiche")

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(RootOnlyFilter())


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Socio Economic Impacts of Catastrophic Hydrological Events",
    )
    parser.add_argument(
        "configfile",
        nargs="?",
        default=None,
        type=str,
        help="Config file containing all the workflow options, see example here: ???",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=(
            "More verbose output, displaying at level logging.DEBUG. "
            "If ommited, will display at level logging.INFO."
        ),
    )

    args = parser.parse_args()

    if args.configfile is None:
        parser.print_help()
        sys.exit(0)

    return args


def compute_file_sha256(filepath: str | Path) -> str:
    """
    Return the SHA-256 hexdigest of a file on disk.

    Parameters
    ----------
    filepath : str
        Path to the file whose checksum should be calculated.

    Returns
    -------
    str
        Hexadecimal SHA-256 digest of the file's binary content.

    """
    with Path(filepath).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def compute_gpkg_sha256(
    filepath: str,
    layer: str | None = None,
) -> str:
    """
    Return a reproducible SHA-256 hash for a GeoPackage.

    GeoPackage files contain internal timestamps / UUIDs that change on
    every write, which would break a naïve file_digest approach.
    The function therefore reads the vector data (optionally a specific
    layer), converts it to CSV text and hashes that deterministic
    representation.

    Parameters
    ----------
    filepath : str
        Path to the .gpkg file.
    layer : str | None, default: None
        Name of the layer to hash.  If None the default layer is used.

    Returns
    -------
    str
        Hexadecimal SHA-256 digest of the CSV representation of the
        geopackage contents.

    """
    if Path(filepath).suffix != ".gpkg":
        msg = "compute_gpkg_sha256 expects a .gpkg file"
        raise ValueError(msg)
    csv_bytes = gpd.read_file(filepath, layer=layer).to_csv().encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def is_file_ok(filepath: str, expected_sha256: str) -> bool:
    """
    Quick boolean test to check if filepath matches the supplied SHA-256 hash.
    """
    return compute_file_sha256(filepath) == expected_sha256


def is_gpkg_ok(
    filepath: str,
    expected_sha256: str,
    layer: str | None = None,
) -> bool:
    """
    Quick boolean test for a GeoPackage, using the deterministic CSV-based hash.
    """
    return compute_gpkg_sha256(filepath, layer=layer) == expected_sha256
