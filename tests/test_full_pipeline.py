"""
Test full SEICHE pipeline.
"""

import glob
import shutil

import yaml

from seiche.main import main
from seiche.utils_qol import (
    compute_file_sha256,
    compute_gpkg_sha256,
    is_file_ok,
    is_gpkg_ok,
)

with open("tests/test_full_pipeline_data.yml") as f:
    HASHES = yaml.safe_load(f)


def _test_full_pipeline(
    input_root: str,
    relative_config_path: str,
    output_root: str,
    input_hashes: dict[str, str],
    output_hashes: dict[str, str],
) -> None:
    errors = {}
    shutil.rmtree(output_root, ignore_errors=True)
    input_files = glob.glob(f"{input_root}/**/*.*", recursive=True)
    for file in input_files:
        relative_path = file.replace(f"{input_root}/", "")
        expected_hash = input_hashes.get(relative_path)
        if expected_hash is None:
            errors[relative_path] = "No reference hash supplied."
        elif not is_file_ok(file, expected_hash):
            errors[relative_path] = (
                f"Wrong hash, got {compute_file_sha256(file)}"
            )
            errors[relative_path] = (
                f"Wrong hash, got {compute_file_sha256(file)}"
            )

    main(f"{input_root}/{relative_config_path}")

    output_files = glob.glob(f"{output_root}/**/*.*", recursive=True)
    for file in output_files:
        relative_path = file.replace(f"{output_root}/", "")
        expected_hash = output_hashes.get(relative_path)
        if expected_hash is None:
            errors[relative_path] = "No reference hash supplied."

        # WARNING: for .gpkg, it is not the signature of the file,
        # but rather the signature of the data turned into CSV and then encoded into utf8
        # for more details see utils_qol.is_gpkg_ok
        elif file.endswith(".gpkg"):
            if not is_gpkg_ok(file, expected_hash):
                errors[relative_path] = (
                    f"Wrong hash, got {compute_gpkg_sha256(file)}"
                )
        elif not is_file_ok(file, expected_hash):
            errors[relative_path] = (
                f"Wrong hash, got {compute_file_sha256(file)}"
            )
    if errors:
        message = "\nHash mismatches detected:\n\n"
        for path, msg in errors.items():
            message += f"{path}: {msg}\n"
        raise AssertionError(message)


def test_marmande():
    """
    See documentation.

    ETA: 10 min or so.
    """
    _test_full_pipeline(
        input_root="./tests/marmande_light",
        relative_config_path="marmande_light.yml",
        output_root="./tests/marmande_light/out",
        input_hashes=HASHES["marmande"]["input"],
        output_hashes=HASHES["marmande"]["output"],
    )


def test_st_omer():
    """
    See documentation.

    ETA 2 min or so.
    """
    _test_full_pipeline(
        input_root="./tests/stomer_light",
        relative_config_path="stomer_light.yml",
        output_root="./tests/stomer_light/out",
        input_hashes=HASHES["stomer"]["input"],
        output_hashes=HASHES["stomer"]["output"],
    )
