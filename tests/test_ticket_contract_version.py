from __future__ import annotations

import yaml
from fastapi.testclient import TestClient

from planfile import Planfile
from planfile.api import server
from planfile.core.models import TICKET_CONTRACT_VERSION


def test_new_ticket_is_stamped_without_rewriting_legacy_provenance(tmp_path):
    pf = Planfile(str(tmp_path))
    created = pf.create_ticket(name="Versioned ticket")

    assert created.contract_version == TICKET_CONTRACT_VERSION

    current_path = tmp_path / ".planfile" / "sprints" / "current.yaml"
    data = yaml.safe_load(current_path.read_text())
    legacy = dict(data["sprint"]["tickets"][created.id])
    legacy["id"] = "PLF-999"
    legacy["name"] = "Legacy ticket"
    legacy.pop("contract_version")
    data["sprint"]["tickets"]["PLF-999"] = legacy
    current_path.write_text(yaml.safe_dump(data, sort_keys=False))

    loaded = pf.get_ticket("PLF-999")
    assert loaded is not None
    assert loaded.contract_version is None


def test_api_preserves_producer_name_and_version(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.post(
        "/tickets",
        json={
            "name": "Produced by Subactor Control",
            "source": {
                "tool": "organization-control",
                "version": "1",
                "context": {"deployment": "control"},
            },
        },
    )

    assert response.status_code == 201
    ticket = response.json()
    assert ticket["contract_version"] == TICKET_CONTRACT_VERSION
    assert ticket["source"]["tool"] == "organization-control"
    assert ticket["source"]["version"] == "1"


def test_api_defaults_to_versioned_planfile_producer(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.post("/tickets", json={"name": "API default producer"})

    assert response.status_code == 201
    ticket = response.json()
    assert ticket["source"]["tool"] == "planfile-api"
    assert ticket["source"]["version"] == server.__version__
