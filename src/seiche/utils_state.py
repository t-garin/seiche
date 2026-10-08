"""
Functions to read derived values from the SEICHE state.

These replace the previous "constants" pass: instead of precomputing everything once
and storing it in ``state["config"]``, each value is derived on demand from the
config and the state.
"""

import inspect
import json
import logging
import shutil
from collections.abc import Iterable
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any

import geopandas as gpd
import yaml

from seiche.utils_enum import (
    DamageFunc,
    DefendedMethod,
    HazardSource,
    Landcover,
    PopDataset,
)
from seiche.utils_qol import asinstance, require

logger = logging.getLogger(__name__)


def _parse_override(item: str) -> tuple[str, Any]:
    """
    Split a ``"key: value"`` override item into key and YAML-parsed value.
    """
    key, sep, value = item.partition(":")
    if not sep:
        msg = f'--override expects "key: value", got "{item}"'
        raise ValueError(msg)
    return key.strip(), yaml.safe_load(value)


def get_config(
    config_path: Path | str, overrides: Iterable[str] | None = None
) -> dict[str, Any]:
    """
    Parse and return the config dict from a YAML file.

    Parameters
    ----------
    config_path : Path | str
        Path to the config YAML file.
    overrides : Iterable[str] | None, default: None
        ``"key: value"`` items replacing the matching config values after
        loading, before validation. Values are parsed as YAML, so
        ``"param.EPSG: 2154"`` becomes the int ``2154``.

    Raises
    ------
    ValueError
        If an item is not of the form ``key: value``, or if the key is not a
        config key.

    """
    with Path(config_path).open() as configfile:
        config = yaml.safe_load(configfile)
    for item in overrides or []:
        key, value = _parse_override(item)
        if key not in config:
            msg = f'--override: unknown config key "{key}"'
            raise ValueError(msg)
        config[key] = value
    check_config(config)
    return config


def check_config(config: dict[str, Any]) -> bool:
    """
    Check if the config dict is well formated.

    Check that all required fields are present in the config dict.

    Returns True if the config is well formatted, raises ValueError otherwise.
    """
    yaml_path = resources.files(__package__).joinpath("config_template.yml")
    with yaml_path.open("r", encoding="utf-8") as templatefile:
        templateconfig = yaml.safe_load(templatefile)
    tmp_key_set = set(templateconfig.keys())
    cfg_key_set = set(config.keys())
    if tmp_key_set != cfg_key_set:
        logger.critical("Missing fields in config: %s", tmp_key_set - cfg_key_set)
        logger.critical("Unnecessary fields in config: %s", cfg_key_set - tmp_key_set)
        msg = "Config file is not well formatted."
        raise ValueError(msg)
    return True


def read_expname_from_state(state: dict[str, Any]) -> str:
    """
    Return the experiment name from the state.

    Falls back to the config file name (without extension) when ``param.expname``
    is not provided.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    str
        The experiment name.

    """
    config = state["config"]
    if isinstance(config["param.expname"], str):
        return config["param.expname"]
    return Path(state["config_path"]).stem


def read_poly_from_state(state: dict[str, Any]) -> gpd.GeoDataFrame:
    """
    Return the working polygon from the state, reprojected if an EPSG is given.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    gpd.GeoDataFrame
        The polygon covering the study area.

    """
    config = state["config"]
    poly = gpd.read_file(
        Path(config["path.inp"]) / config["path.inp.POLY"],
        engine="pyogrio",
    )
    if isinstance(config["param.EPSG"], int):
        poly = poly.to_crs(epsg=config["param.EPSG"])
    return asinstance(poly, gpd.GeoDataFrame)


def read_epsg_from_state(state: dict[str, Any]) -> int:
    """
    Return the EPSG code from the state.

    Uses ``param.EPSG`` when provided, otherwise extracts it from the POLY's CRS.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    int
        The EPSG code of the study area.

    """
    config = state["config"]
    if isinstance(config["param.EPSG"], int):
        return config["param.EPSG"]
    logger.warning("No valid EPSG code provided, using POLY's CRS.")
    return require(read_poly_from_state(state).crs.to_epsg())


def read_use_variables_from_state(
    state: dict[str, Any],
) -> tuple[bool, bool, bool]:
    """
    Return which hazard variables to use.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    tuple[bool, bool, bool]
        ``(use_max_depth, use_max_speed, use_duration)``.

    Raises
    ------
    ValueError
        If neither ``use.dmg.floodam`` nor ``use.dmg.jrc`` is enabled.

    """
    config = state["config"]
    if config["use.dmg.floodam"]:
        use_max_depth, use_max_speed, use_duration = True, True, True
        logger.info("Using `max_depth`, `max_speed` and `duration`")
    elif config["use.dmg.jrc"]:
        use_max_depth, use_max_speed, use_duration = True, False, False
        logger.info("Using only `max_depth`")
    else:
        error_msg = "At least one of jrc, floodam, ghslpop, or filosofi must be used."
        logger.critical(error_msg)
        raise ValueError(error_msg)
    return use_max_depth, use_max_speed, use_duration


def _get_used_methods[M: StrEnum](
    state: dict[str, Any],
    key: str,
    available_methods: list[M],
) -> list[M]:
    """
    Return the enabled methods of a given config group.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.
    key : str
        Config group name, e.g. ``"dmg"``.
    available_methods : list[M]
        Methods to filter on.

    Returns
    -------
    list[M]
        The enabled methods.

    """
    return [
        method for method in available_methods if state["config"][f"use.{key}.{method}"]
    ]


def read_hazards_from_state(state: dict[str, Any]) -> list[HazardSource]:
    """
    Return the hazard sources to be used.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    list[HazardSource]
        The hazards, among ``HazardSource.slf``, ``HazardSource.bfm`` and
        ``HazardSource.hvt``.

    """
    config = state["config"]
    hazards = []
    if config["path.inp.slf"] is not None:
        hazards.append(HazardSource.slf)
    if config["path.inp.bfm.root"] is not None:
        hazards.append(HazardSource.bfm)
    if config["path.inp.hvt"] is not None:
        hazards.append(HazardSource.hvt)
    return hazards


def read_defended_methods_from_state(state: dict[str, Any]) -> list[DefendedMethod]:
    """
    Return the defended methods to be used.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    list[DefendedMethod]
        The enabled defended methods.

    """
    return _get_used_methods(state, "defended", list(DefendedMethod))


def read_landcovers_from_state(state: dict[str, Any]) -> list[Landcover]:
    """
    Return the landcovers to be used.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    list[Landcover]
        The landcovers with input data.

    """
    return [
        lcv for lcv in Landcover if state["config"][f"path.inp.lcv.{lcv}"] is not None
    ]


def read_dmgfuncs_from_state(state: dict[str, Any]) -> list[DamageFunc]:
    """
    Return the damage functions to be used.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    list[DamageFunc]
        The enabled damage functions.

    """
    return _get_used_methods(state, "dmg", list(DamageFunc))


def read_pop_datasets_from_state(state: dict[str, Any]) -> list[PopDataset]:
    """
    Return the population datasets to be used.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    list[PopDataset]
        The population datasets with input data.

    """
    return [
        pop for pop in PopDataset if state["config"][f"path.inp.pop.{pop}"] is not None
    ]


def read_pop_conditions_from_state(state: dict[str, Any]) -> dict[str, Any]:
    """
    Return the population conditions from the state.

    Parameters
    ----------
    state : dict
        The whole SEICHE state.

    Returns
    -------
    dict
        Mapping of a condition name to a boolean expression on ``h``, ``v`` and
        ``t``.

    Raises
    ------
    ValueError
        If ``param.pop.conditions`` is not a non-empty dict.

    """
    pop_conditions = state["config"].get("param.pop.conditions", {})
    if not isinstance(pop_conditions, dict) or not pop_conditions:
        error_msg = (
            "`param.pop.conditions` must be a non-empty dict mapping a name to a "
            'boolean expression on h, v and t, e.g. `is_above_30cm: "h > 0.3"`.'
        )
        logger.critical(error_msg)
        raise ValueError(error_msg)
    return pop_conditions


def _state_default(obj: object) -> str:
    """
    Convert a non-YAML-serializable object to a string for the state snapshot.
    """
    if isinstance(obj, Path):
        return str(obj)
    if callable(obj):
        try:
            return inspect.getsource(obj).strip()
        except (OSError, TypeError):
            return str(getattr(obj, "__qualname__", None))
    return str(obj)


def _state_path(config: dict[str, Any]) -> Path:
    """Return the path to the state file for an experiment."""
    return Path(config["path.out"]) / "state.yml"


def load_done(config: dict[str, Any]) -> dict[str, Any]:
    """
    Return the already-completed parts of a previous run, if any.
    """
    state_path = _state_path(config)
    if not state_path.exists():
        return {}
    progress = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    return progress.get("done", {})


def initialize_state(
    config_path: str | Path, overrides: Iterable[str] | None = None
) -> dict[str, Any]:
    """
    Build the initial SEICHE state from a config file.

    Loads the config, handles cold/hot runs (a cold run wipes the output
    directory), and loads the resume state for hot runs.

    Parameters
    ----------
    config_path : str
        Path pointing to the .yml config file.
    overrides : Iterable[str] | None, default: None
        ``"key: value"`` items overriding config values, see :func:`get_config`.

    Returns
    -------
    dict
        The initial state, with ``config``, ``config_path`` and ``done``.

    """
    logger.info("📜 %s", config_path)
    state = {
        "config": get_config(config_path, overrides=overrides),
        "config_path": str(config_path),
        "done": {},
    }
    config = state["config"]
    if config["param.cold_run"]:
        logger.info("❄️ Cold Run")
        shutil.rmtree(config["path.out"], ignore_errors=True)
        logger.info("🧹 Removed old OUT files")
    else:
        logger.info("🔥 Hot run")
    Path(config["path.out"]).mkdir(parents=True, exist_ok=True)
    done = {} if config["param.cold_run"] else load_done(config)
    return {**state, "done": done}


def dump_state(state: dict[str, Any]) -> None:
    """
    Persist the whole state so a crash can be resumed from the last part.

    Non-YAML-serializable values (paths, dataframes, lambdas, ...) are
    converted to strings for the snapshot.
    """
    serializable = json.loads(json.dumps(state, default=_state_default))
    _state_path(state["config"]).write_text(
        yaml.safe_dump(serializable, sort_keys=False),
        encoding="utf-8",
    )
