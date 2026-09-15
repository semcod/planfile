from pathlib import Path

import pytest
import yaml

from planfile.sync.state import (
    SYNC_STATE_SCHEMA,
    SyncState,
    SyncStateRepositoryMismatch,
    normalize_repository,
)


def test_repository_normalization_accepts_common_git_forms():
    assert normalize_repository("HTTPS://GITHUB.COM/Owner/Repo.git") == "owner/repo"
    assert normalize_repository("git@github.com:Owner/Repo.git") == "owner/repo"


def test_state_is_atomic_versioned_and_repository_bound(tmp_path: Path):
    state = SyncState(tmp_path / ".planfile", "github", repository="Owner/Repo")
    state.save_sync({"PLF-1": "42"})

    raw = yaml.safe_load(state.state_file.read_text())
    assert raw["schema"] == SYNC_STATE_SCHEMA
    assert raw["backend"] == "github"
    assert raw["repository"] == "owner/repo"
    assert raw["ticket_map"] == {"PLF-1": "42"}
    assert not any(path.name.endswith(".tmp") for path in state.state_file.parent.iterdir())

    state.save_sync({"PLF-2": "43"})
    assert state.get_last_sync()["ticket_map"] == {"PLF-1": "42", "PLF-2": "43"}

    with pytest.raises(SyncStateRepositoryMismatch):
        SyncState(tmp_path / ".planfile", "github", repository="other/repo").get_remote_id("PLF-1")


def test_legacy_state_migrates_without_storing_credentials(tmp_path: Path):
    state = SyncState(tmp_path / ".planfile", "github", repository="owner/repo")
    state.state_file.parent.mkdir(parents=True)
    state.state_file.write_text(
        yaml.safe_dump({"ticket_map": {"PLF-1": "42"}, "token": "must-not-be-copied"})
    )

    assert state.get_remote_id("PLF-1") == "42"
    state.save_sync({"PLF-2": "43"})
    raw = yaml.safe_load(state.state_file.read_text())
    assert raw["repository"] == "owner/repo"
    assert "token" not in raw


def test_ambiguous_reverse_mapping_fails_closed(tmp_path: Path):
    state = SyncState(tmp_path / ".planfile", "github")
    state.save_sync({"PLF-1": "42", "PLF-2": "42"})
    with pytest.raises(ValueError, match="ambiguous"):
        state.get_local_id("42")
