"""Regression tests for GitHubBackend label canonicalization."""
from __future__ import annotations

import pytest

from planfile.sync.github import GitHubBackend


def test_canonical_labels_splits_comma_separated_entries_and_deduplicates() -> None:
    result = GitHubBackend._canonical_labels(
        ["memory,auto", "safety, defaults", "safety", "dedupe:fixos:gh-227"],
        "high",
    )
    assert result == [
        "memory",
        "auto",
        "safety",
        "defaults",
        "priority-high",
        "planfile",
        "managed",
    ]


def test_canonical_labels_skips_dedupe_keys_even_with_commas() -> None:
    result = GitHubBackend._canonical_labels(
        ["dedupe:fixos:a,b", "priority: high", "tmp-cleanup,safety"],
        None,
    )
    assert result == ["tmp-cleanup", "safety", "planfile", "managed"]


@pytest.mark.parametrize(
    "bad_labels",
    [
        [""],
        [","],
        [" , , "],
        ["x" * (GitHubBackend.MAX_LABEL_LENGTH + 1)],
        ["ok," + ("x" * (GitHubBackend.MAX_LABEL_LENGTH + 1))],
        ["bad\nlabel"],
    ],
)
def test_canonical_labels_rejects_empty_oversized_and_control_labels(bad_labels: list[str]) -> None:
    with pytest.raises(ValueError, match="Invalid GitHub label"):
        GitHubBackend._canonical_labels(bad_labels, None)
