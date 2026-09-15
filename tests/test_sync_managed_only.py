from __future__ import annotations

from planfile.cli.groups.sync.core import _apply_github_overrides
from planfile.integrations.config import IntegrationConfig
from planfile.sync.operations import _fetch_external_tickets


def test_repository_override_can_bootstrap_github_config(tmp_path):
    config = IntegrationConfig(str(tmp_path))
    config.load_configs()

    _apply_github_overrides(config, "SemCod/Example")

    assert config.get_integration_config("github") == {"repo": "SemCod/Example"}
    assert config.validate_integration("github")


def test_managed_only_passes_labels_to_inbound_backend():
    calls = []

    class FakeBackend:
        def list_tickets(self, **kwargs):
            calls.append(kwargs)
            return [{"id": "7"}]

    tickets = _fetch_external_tickets(FakeBackend(), "github", ["planfile", "managed"])

    assert tickets == [{"id": "7"}]
    assert calls == [{"labels": ["planfile", "managed"]}]


def test_default_inbound_sync_does_not_add_a_filter():
    calls = []

    class FakeBackend:
        def list_tickets(self, **kwargs):
            calls.append(kwargs)
            return []

    assert _fetch_external_tickets(FakeBackend(), "github") == []
    assert calls == [{}]
