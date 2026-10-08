"""
Tests for the SEICHE pipeline orchestration.
"""

import argparse
import logging
from pathlib import Path
from typing import override

import pytest
import yaml

from generate_synthetic_data import load_test_data

import seiche.main as mp
import seiche.utils_state as us

DUMP_LOAD_CASES = load_test_data("test_main_data.yml", "dump_load")
RUN_PIPELINE_CASES = load_test_data("test_main_data.yml", "run_pipeline")
INIT_CASES = load_test_data("test_main_data.yml", "initialize_state")
MAIN_CASES = load_test_data("test_main_data.yml", "main")
CLI_CASES = load_test_data("test_main_data.yml", "cli")


@pytest.mark.parametrize("case", DUMP_LOAD_CASES)
def test_dump_load_roundtrip(tmp_path: Path, case: dict) -> None:
    """A dumped state reloads with the same content."""
    config = {**case["config"], "path.out": str(tmp_path)}
    assert us.load_done(config) == {}
    state = {
        "config_path": "/some/config.yml",
        "config": config,
        "done": case["done"],
        "dem": {"path": tmp_path / case["dem"]},
        "hazard": {"slf1": tmp_path / case["hazard"]["slf1"]},
    }
    us.dump_state(state)
    dumped = yaml.safe_load((tmp_path / "state.yml").read_text(encoding="utf-8"))
    assert dumped["config_path"] == state["config_path"]
    assert dumped["config"] == config
    assert dumped["done"] == case["done"]
    assert dumped["dem"] == {"path": str(tmp_path / case["dem"])}
    assert us.load_done(config) == case["expected_done"]


def test_dump_state_fallbacks(tmp_path: Path) -> None:
    """Non-serializable values are converted to strings in the snapshot."""

    class Custom:
        @override
        def __str__(self) -> str:
            return "custom"

    state = {
        "config_path": "x.yml",
        "config": {"path.out": str(tmp_path)},
        "done": {},
        "builtin": len,
        "custom": Custom(),
    }
    us.dump_state(state)
    dumped = yaml.safe_load((tmp_path / "state.yml").read_text(encoding="utf-8"))
    assert dumped["builtin"] == "len"
    assert dumped["custom"] == "custom"


@pytest.mark.parametrize("case", RUN_PIPELINE_CASES)
def test_run_pipeline_skips_done_parts(tmp_path: Path, monkeypatch, case: dict) -> None:
    """Already-done pipeline parts are skipped."""
    calls: list[str] = []
    state = {
        "config_path": "x.yml",
        "config": {"path.out": str(tmp_path)},
        "done": case["done"],
    }

    def make_step(name: str) -> object:
        """Return a pipeline step recording its name in ``calls``."""
        return lambda st: (calls.append(name), st)[1]

    monkeypatch.setattr(
        mp,
        "PIPELINE",
        tuple((s, make_step(s)) for s in case["steps"]),
    )
    mp.run_pipeline(state)
    assert calls == case["expected_calls"]


@pytest.mark.parametrize("case", INIT_CASES)
def test_initialize_state(tmp_path: Path, monkeypatch, case: dict) -> None:
    """The initial state follows the cold/hot run policy."""
    if case.get("write_old_file"):
        (tmp_path / "old_file.tif").write_text("x", encoding="utf-8")
    config = {**case["config"], "path.out": str(tmp_path)}
    monkeypatch.setattr(us, "get_config", lambda path, overrides=None: config)
    if "load_done" in case:
        monkeypatch.setattr(
            "seiche.utils_state.load_done", lambda config: case["load_done"]
        )

    out = us.initialize_state(str(tmp_path / "x.yml"))

    assert out["config"] == config
    assert out["config_path"] == str(tmp_path / "x.yml")
    assert out["done"] == case["expected_done"]
    if case.get("write_old_file"):
        assert (tmp_path / "old_file.tif").exists() == (not case["cold_run"])


@pytest.mark.parametrize("case", MAIN_CASES)
def test_main(monkeypatch, tmp_path: Path, case: dict) -> None:
    """main() sets up logging and runs the pipeline on the state."""
    config_path = tmp_path / "x.yml"
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        mp, "setup_logging", lambda level: calls.setdefault("level", level)
    )

    def fake_initialize_state(path: str, overrides: object = None) -> dict:
        """Return a minimal state, recording the overrides passed through."""
        calls["overrides"] = overrides
        return {
            "config": {"cfg": str(path)},
            "config_path": str(path),
            "done": {},
        }

    monkeypatch.setattr(mp, "initialize_state", fake_initialize_state)
    monkeypatch.setattr(
        mp, "run_pipeline", lambda state: calls.setdefault("state", state)
    )

    mp.main(str(config_path), verbose=case["verbose"], overrides=case.get("override"))

    assert calls["level"] == (logging.DEBUG if case["verbose"] else logging.INFO)
    assert calls["overrides"] == case.get("override")
    state = calls["state"]
    assert isinstance(state, dict)
    assert state["config"] == {"cfg": str(config_path)}
    assert state["config_path"] == str(config_path)
    assert state["done"] == {}


@pytest.mark.parametrize("case", CLI_CASES)
def test_cli(monkeypatch, tmp_path: Path, case: dict) -> None:
    """cli() parses args and calls main() with them."""
    calls: dict[str, object] = {}
    args = argparse.Namespace(
        configfile=str(tmp_path / "x.yml"),
        verbose=case["verbose"],
        override=case.get("override", []),
    )
    monkeypatch.setattr(mp, "parse_args", lambda: args)
    monkeypatch.setattr(
        mp,
        "main",
        lambda config_path, verbose, overrides=None: calls.update(
            config_path=config_path, verbose=verbose, overrides=overrides
        ),
    )

    mp.cli()

    assert calls == {
        "config_path": Path(args.configfile),
        "verbose": case["verbose"],
        "overrides": case.get("override", []),
    }
