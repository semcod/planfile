"""Regressions for unified version identity and strict autonomy payload validation (#384)."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from typer.testing import CliRunner

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 uses the locked tomli dependency.
    import tomli as tomllib

import planfile
from planfile import (
    AUTODO_PLANFILE_IMPORT_SCHEMA,
    AutodoPlanfileImportMetadataV1,
    DeliveryPlanError,
    Planfile,
    admit_comparative_findings,
    get_runtime_identity,
)
from planfile.api import server
from planfile.cli.commands import app as cli_app
from planfile.core.schema import validate_yaml_file
from planfile.loaders.yaml_loader import load_strategy_yaml
from planfile.version_identity import (
    RUNTIME_VERSION_CONSTANT,
    SUPPORTED_AUTONOMY_SCHEMAS,
    resolve_runtime_version,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_HASH = "sha256:" + "a" * 64
BASE_SHA = "b" * 40


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _valid_candidate(key: str = "runtime-core", order: int = 0) -> dict:
    core = {
        "schema": "subactor.ticket-candidate/v1",
        "plan_hash": PLAN_HASH,
        "candidate_key": key,
        "order": order,
        "title": f"Deliver {key}",
        "workstream": "application",
        "depends_on": [],
        "allowed_paths": [f"planfile/{key}.py"],
        "placement": {
            "home": "semcod",
            "shape": "runtime_service",
            "runtime_owner": "semcod",
            "adopt": ["wellmanifest/new-project"],
        },
        "delivery": {
            "complexity": "S",
            "estimated_minutes": 20,
            "max_implementation_files": 2,
            "max_affected_components": 1,
            "max_public_interface_changes": 0,
            "max_runtime_dependencies": 0,
        },
        "components": ["delivery-plan"],
        "public_interfaces": [],
        "runtime_dependencies": [],
        "acceptance": [
            {
                "id": "AC-01",
                "statement": "Bounded acceptance statement.",
                "test_ids": ["python-suite"],
            }
        ],
        "tests": [
            {"id": "python-suite", "kind": "python-test", "target": "tests/test_delivery_plan.py"}
        ],
        "execution": "inert",
    }
    digest = _digest(core)
    return {
        **core,
        "candidate_digest": digest,
        "idempotency_key": _digest(
            {"plan_hash": PLAN_HASH, "candidate_key": key, "candidate_digest": digest}
        ),
        "state": "pending",
        "split_reasons": [],
        "terminal_receipt_ref": None,
    }


def _valid_native_plan() -> dict:
    candidate = _valid_candidate()
    return {
        "schema": "subactor.compiled-work-plan/v1",
        "status": "ready",
        "execution": "inert",
        "authority": "none",
        "plan_id": "strict-plan-v1",
        "plan_ref": "artifact://semcod/planfile/strict-plan-v1",
        "plan_hash": PLAN_HASH,
        "repository": "semcod/planfile",
        "accepted_base_sha": BASE_SHA,
        "target_branch": "main",
        "placement": {
            "home": "semcod",
            "shape": "runtime_service",
            "runtime_owner": "semcod",
            "adopt": ["wellmanifest/new-project"],
        },
        "candidate_count": 1,
        "pending_count": 1,
        "split_required": [],
        "terminal_candidates": [],
        "candidates": [candidate],
    }


def _sample_comparative_finding(**overrides) -> dict:
    base = {
        "schema": "planfile.comparative-finding/v1",
        "finding_id": "FND-STRICT-001",
        "target_repository": "semcod/planfile",
        "capability": "strict-payload-contract",
        "intent": "Reject malformed or extra payload fields before mutation",
        "policy_version": "v1",
        "verdict": "actionable_gap",
        "classification": "BUGFIX",
        "classification_reason": "Tightens validation on autonomy interfaces",
        "target_scope": ["planfile/api/server.py"],
        "prerequisites": [],
        "acceptance_test": ["pytest -q tests/test_autonomy_version_and_payloads.py"],
        "evidence_hash": "sha256:" + "1" * 64,
        "target_head_sha": "c" * 40,
        "evidence_fresh": True,
        "rollback": "Revert strict payload validation changes",
        "executor_ownership": {
            "kind": "llm",
            "mode": "automatic",
            "handler": "subactor/coding-agent",
            "workstream": "application",
            "queue": "default",
            "allocate_governance_ticket_after_admission": True,
        },
    }
    base.update(overrides)
    return base


def test_unified_version_identity_across_checkout_cli_health_and_openapi(
    tmp_path, monkeypatch
) -> None:
    pyproject_version = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["project"][
        "version"
    ]
    release_meta = json.loads((REPO_ROOT / "planfile/release-metadata.json").read_text())
    assert RUNTIME_VERSION_CONSTANT == pyproject_version
    assert planfile.__version__ == pyproject_version
    assert release_meta["source"]["version"] == pyproject_version
    assert release_meta["runtime"]["version"] == pyproject_version

    cli_result = CliRunner().invoke(cli_app, ["--version"])
    assert cli_result.exit_code == 0, cli_result.output
    assert pyproject_version in cli_result.stdout

    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health = health_resp.json()
    assert health["version"] == pyproject_version
    assert "autonomy.payload_validation.strict_v1" in health["capabilities"]
    assert "delivery_plan.preflight.import_namespace_separation" in health["capabilities"]
    assert health["source_identity"]["install_mode"] == "checkout"
    assert health["source_identity"]["package_version"] == pyproject_version
    assert health["source_identity"]["version_identifies_active_deployment"] is False
    assert len(health["source_identity"]["source_sha"]) == 40
    assert health["schema_versions"] == SUPPORTED_AUTONOMY_SCHEMAS

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    info = openapi_resp.json()["info"]
    assert info["version"] == pyproject_version
    assert info["x-planfile-source-identity"] == health["source_identity"]
    assert info["x-planfile-schema-versions"] == SUPPORTED_AUTONOMY_SCHEMAS


def test_wheel_distribution_version_resolution_uses_matched_dist_info(
    tmp_path, monkeypatch
) -> None:
    site_packages = tmp_path / "site-packages"
    pkg_dir = site_packages / "planfile"
    pkg_dir.mkdir(parents=True)
    init_file = pkg_dir / "__init__.py"
    init_file.write_text("# synthetic installed wheel package\n", encoding="utf-8")
    dist_info = site_packages / "planfile-0.1.127.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: planfile\nVersion: 0.1.127\n",
        encoding="utf-8",
    )
    (dist_info / "RECORD").write_text("planfile/__init__.py,,\n", encoding="utf-8")

    monkeypatch.syspath_prepend(str(site_packages))
    monkeypatch.setenv("PLANFILE_BUILD_SHA", "d" * 40)
    resolved = resolve_runtime_version("0.1.126", package_file=init_file)
    assert resolved == "0.1.127"

    identity = get_runtime_identity(package_file=init_file, runtime_version=resolved)
    assert identity["install_mode"] == "distribution"
    assert identity["version"] == "0.1.127"
    assert identity["distribution_version"] == "0.1.127"
    assert identity["pyproject_version"] is None
    assert identity["source_sha"] == "d" * 40
    assert identity["version_identifies_active_deployment"] is False


@pytest.mark.parametrize(
    ("payload", "expected_field"),
    [
        ({"name": "Valid", "unknown_extra": True}, "unknown_extra"),
        ({"name": "Typo", "bloked_by": ["PLF-001"]}, "bloked_by"),
        ({"name": "Bad dep string", "blocked_by": "PLF-001"}, "blocked_by"),
        ({"name": "Bad dep bool", "blocked_by": True}, "blocked_by"),
        ({"name": "Bad dep item int", "blocked_by": [123]}, "blocked_by.0"),
        ({"name": "Bad dep item empty", "blocked_by": [""]}, "blocked_by.0"),
        ({"name": "Bad schema", "schema": "planfile.ticket-create/v0"}, "schema"),
        (
            {"name": "Import envelope misuse", "schema": AUTODO_PLANFILE_IMPORT_SCHEMA},
            "schema",
        ),
        ({"name": "Nested unknown", "inputs": {"unexpected_input_flag": True}}, "inputs"),
    ],
)
def test_ticket_create_rejects_malformed_and_unknown_payloads_before_write(
    tmp_path, monkeypatch, payload: dict, expected_field: str
) -> None:
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.post("/tickets", json=payload)

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "payload_validation_failed"
    assert any(err["field_path"] == expected_field for err in body["errors"]), body
    assert pf.list_tickets(sprint="all") == []


@pytest.mark.parametrize(
    ("payload", "expected_field"),
    [
        ({"actor": "agent:test", "reason": "test", "unexpected": 1}, "unexpected"),
        ({"actor": "agent:test", "reason": "test", "bloked_by": ["PLF-002"]}, "bloked_by"),
        ({"actor": "agent:test", "reason": "test", "blocked_by": "PLF-002"}, "blocked_by"),
        ({"actor": "agent:test", "reason": "test", "blocked_by": [True]}, "blocked_by.0"),
        ({"actor": "agent:test", "reason": "test", "blocks": [123]}, "blocks.0"),
        ({"actor": "agent:test", "reason": "test", "schema": "planfile.ticket-update/v0"}, "schema"),
        ({"actor": "agent:test", "reason": "test", "execution": {"bogus_key": 1}}, "execution"),
    ],
)
def test_ticket_update_rejects_malformed_and_unknown_payloads_before_write(
    tmp_path, monkeypatch, payload: dict, expected_field: str
) -> None:
    pf = Planfile(str(tmp_path))
    created = pf.create_ticket(name="Target ticket")
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.patch(f"/tickets/{created.id}", json=payload)

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "payload_validation_failed"
    assert any(err["field_path"] == expected_field for err in body["errors"]), body
    reloaded = pf.get_ticket(created.id, repair_index=False)
    assert reloaded is not None
    assert reloaded.updated_at == created.updated_at
    assert reloaded.blocked_by == []


@pytest.mark.parametrize(
    ("request_body", "expected_field"),
    [
        (
            {"findings": [_sample_comparative_finding()], "unknown_top": True},
            "unknown_top",
        ),
        (
            {"findings": [_sample_comparative_finding()], "schema": "autodo.planfile-import/v1"},
            "schema",
        ),
        (
            {"findings": [_sample_comparative_finding(unexpected_finding_key=1)]},
            "findings.0.unexpected_finding_key",
        ),
        (
            {"findings": [_sample_comparative_finding(prerequisites="FND-0")]},
            "findings.0.prerequisites",
        ),
        (
            {"findings": [_sample_comparative_finding(prerequisites=True)]},
            "findings.0.prerequisites",
        ),
        (
            {"findings": [_sample_comparative_finding(prerequisites=[123])]},
            "findings.0.prerequisites",
        ),
        (
            {"findings": [_sample_comparative_finding(evidence_fresh="yes")]},
            "findings.0.evidence_fresh",
        ),
        (
            {"findings": [_sample_comparative_finding(schema="planfile.comparative-finding/v0")]},
            "findings.0.schema",
        ),
        (
            {
                "findings": [
                    _sample_comparative_finding(
                        executor_ownership={"handler": "bot:a", "bogus_owner_field": True}
                    )
                ]
            },
            "findings.0.executor_ownership.bogus_owner_field",
        ),
    ],
)
def test_comparative_admit_endpoint_rejects_invalid_payloads_with_field_path(
    tmp_path, monkeypatch, request_body: dict, expected_field: str
) -> None:
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.post("/findings/comparative/admit", json=request_body)

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "payload_validation_failed"
    assert any(err["field_path"] == expected_field for err in body["errors"]), body
    assert pf.list_tickets(sprint="all") == []


def test_direct_comparative_admission_also_rejects_extra_fields(tmp_path) -> None:
    pf = Planfile(str(tmp_path))
    with pytest.raises(ValidationError):
        admit_comparative_findings(
            pf,
            [_sample_comparative_finding(typo_field="should-fail")],
        )
    assert pf.list_tickets(sprint="all") == []


def test_legacy_strategy_yaml_compatibility_boundary_preserved_without_downgrade(
    tmp_path, monkeypatch
) -> None:
    legacy_payload = {
        "name": "Legacy Onboarding Strategy",
        "project_type": "library",
        "domain": "dev",
        "goal": "Legacy fixture",
        "sprints": [
            {
                "id": 1,
                "name": "Sprint 1",
                "tasks": [{"title": "Legacy task", "description": "x"}],
            }
        ],
    }
    legacy_path = tmp_path / "strategy.yaml"
    import yaml

    legacy_path.write_text(yaml.safe_dump(legacy_payload, sort_keys=False), encoding="utf-8")
    assert validate_yaml_file(legacy_path, "strategy") == (True, [])
    strategy = load_strategy_yaml(legacy_path)
    assert strategy.name == "Legacy Onboarding Strategy"
    assert strategy.sprints[0].tasks[0].name == "Legacy task"

    # Legacy strategy documents still work via explicit loader/validator above, while
    # modern autonomy mutation and native plan entrypoints refuse them without downgrade.
    pf = Planfile(str(tmp_path))
    assert pf.preflight_delivery_plan(legacy_payload)["ok"] is False
    assert pf.preflight_delivery_plan(legacy_payload)["code"] == "delivery_plan_schema_unsupported"
    with pytest.raises(ValidationError):
        pf.materialize_delivery_plan(legacy_payload)

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    resp = client.post("/findings/comparative/admit", json={"findings": [legacy_payload]})
    assert resp.status_code == 422
    assert pf.list_tickets(sprint="all") == []
    assert not (tmp_path / ".planfile" / "delivery-plans").exists()


def test_delivery_plan_preflight_and_materialize_separate_import_envelope_from_native(
    tmp_path, monkeypatch
) -> None:
    pf = Planfile(str(tmp_path))
    native = _valid_native_plan()
    assert pf.preflight_delivery_plan(native)["ok"] is True
    assert pf.preflight_delivery_plan(native)["materialize_allowed"] is True

    import_envelope = {
        "schema": AUTODO_PLANFILE_IMPORT_SCHEMA,
        "campaign_id": "autodo-2026-11-18",
        "importer": "autodo.planfile_importer",
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source_digest": "sha256:" + "e" * 64,
        "proposal_keys": ["PLAN-006"],
        "compiled_plan": native,
    }
    # Valid import envelope is typed cleanly via its own schema, never native compiled-work-plan/v1.
    parsed = AutodoPlanfileImportMetadataV1.model_validate(import_envelope)
    assert parsed.schema_id == AUTODO_PLANFILE_IMPORT_SCHEMA

    preflight = pf.preflight_delivery_plan(import_envelope)
    assert preflight["ok"] is False
    assert preflight["kind"] == "external_import_envelope"
    assert preflight["materialize_allowed"] is False
    assert preflight["code"] == "delivery_plan_import_envelope_not_native"

    with pytest.raises(DeliveryPlanError, match="delivery_plan_import_envelope_not_native"):
        pf.materialize_delivery_plan(import_envelope)
    assert pf.list_tickets(sprint="all") == []
    assert not (tmp_path / ".planfile" / "delivery-plans").exists()

    # Unknown keys in import envelope or importer keys in native plan fail closed with extra=forbid.
    invalid_envelope = {**import_envelope, "unexpected_meta": "forbidden"}
    invalid_pre = pf.preflight_delivery_plan(invalid_envelope)
    assert invalid_pre["ok"] is False
    assert invalid_pre["code"] == "delivery_plan_import_envelope_invalid"
    assert any(err["field_path"] == "unexpected_meta" for err in invalid_pre["errors"])
    with pytest.raises(ValidationError):
        pf.materialize_delivery_plan(invalid_envelope)

    polluted_native = {**native, "campaign_id": "autodo-2026-11-18"}
    with pytest.raises(ValidationError):
        pf.materialize_delivery_plan(polluted_native)

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    http_import = client.post("/delivery-plans/preflight", json=import_envelope)
    assert http_import.status_code == 422
    assert http_import.json()["code"] == "delivery_plan_import_envelope_not_native"
    http_native = client.post("/delivery-plans/preflight", json=native)
    assert http_native.status_code == 200
    assert http_native.json()["materialize_allowed"] is True


def test_package_import_preserves_lazy_testql_loading() -> None:
    """Guarantee version identity resolution keeps lazy optional module loading intact."""
    import os
    import subprocess

    script = (
        "import json, sys, planfile; "
        "assert 'planfile.testql_integration' not in sys.modules; "
        "assert 'upsert_testql_tickets' in dir(planfile); "
        "assert 'planfile.testql_integration' not in sys.modules; "
        "print(json.dumps({'version': planfile.__version__}))"
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    proc = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["version"] == planfile.__version__
