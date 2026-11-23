"""Unit tests for --direction (from/to/both) support in planfile sync fleet."""

from __future__ import annotations

from pathlib import Path
import pytest

from planfile.cli.groups.sync import fleet as fleet_mod


def test_sync_fleet_forwards_bidirectional_and_outbound_directions(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "org" / "demo"
    repo.mkdir(parents=True)
    calls: list[tuple[str, str, dict]] = []

    monkeypatch.setattr(
        fleet_mod,
        "discover_fleet_repositories",
        lambda _root, max_depth=2: [(repo, "org/demo")],
    )
    monkeypatch.setattr(
        fleet_mod,
        "sync_integration",
        lambda integ, path, **kwargs: calls.append((integ, path, kwargs)),
    )

    stats_both = fleet_mod.sync_fleet(tmp_path, direction="both", dry_run=True)
    assert stats_both["direction"] == "both"
    assert stats_both["synced"] == 1
    assert calls[-1][2]["direction"] == "both"

    stats_to = fleet_mod.sync_fleet(tmp_path, direction="to", dry_run=True)
    assert stats_to["direction"] == "to"
    assert calls[-1][2]["direction"] == "to"


def test_sync_fleet_rejects_invalid_direction(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid fleet sync direction"):
        fleet_mod.sync_fleet(tmp_path, direction="sideways")
