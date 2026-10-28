from __future__ import annotations

import hashlib
import sqlite3

import pytest

from planfile.sync.github import GitHubReadCache


def make(tmp_path, token="placeholder_a", **kwargs):
    return GitHubReadCache("owner/private", {"cache_dir": tmp_path, "token": token, **kwargs})


def test_metadata_is_reused_by_matching_accounts(tmp_path):
    first, second = make(tmp_path), make(tmp_path)
    first.put("labels", "all", ["label"])
    assert second.get("labels", "all") == (True, ["label"])


def test_other_account_cannot_read_private_metadata(tmp_path):
    first, other = make(tmp_path), make(tmp_path, token="placeholder_b")
    first.put("issue-identities", "1", {"id": "private-node"})
    assert first.path != other.path
    assert other.get("issue-identities", "1") == (False, None)


@pytest.mark.parametrize("field", ["base_url", "api_url"])
def test_other_provider_origin_cannot_read_metadata(tmp_path, field):
    cloud, enterprise = make(tmp_path), make(tmp_path, **{field: "https://enterprise.test/api/v3"})
    cloud.put("labels", "all", ["cloud-label"])
    assert enterprise.get("labels", "all") == (False, None)


def test_clearing_one_account_preserves_other_accounts(tmp_path):
    first, other = make(tmp_path), make(tmp_path, token="placeholder_b")
    first.put("labels", "all", ["first"])
    other.put("labels", "all", ["other"])
    first.clear()
    assert first.get("labels", "all") == (False, None)
    assert other.get("labels", "all") == (True, ["other"])


def test_old_unscoped_cache_file_is_never_reused(tmp_path):
    legacy = tmp_path / (hashlib.sha256(b"owner/private").hexdigest()[:24] + ".sqlite3")
    legacy.write_bytes(b"unscoped legacy cache")
    current = make(tmp_path)
    assert current.path != legacy
    assert current.get("labels", "all") == (False, None)
    assert legacy.read_bytes() == b"unscoped legacy cache"


def test_environment_credential_rotation_uses_new_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "placeholder_a")
    first = GitHubReadCache("owner/private", {"cache_dir": tmp_path})
    first.put("labels", "all", ["first"])
    monkeypatch.setenv("GITHUB_TOKEN", "placeholder_b")
    other = GitHubReadCache("owner/private", {"cache_dir": tmp_path})
    assert other.get("labels", "all") == (False, None)


def test_credentials_are_not_persisted_as_file_names_or_records(tmp_path):
    cache = make(tmp_path)
    cache.put("labels", "all", ["label"])
    assert "placeholder_a" not in str(cache.path)
    with sqlite3.connect(cache.path) as db:
        assert "placeholder_a" not in repr(db.execute("SELECT * FROM github_read_cache").fetchall())
