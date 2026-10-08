"""Current report intake must reach persisted tickets without execution authority."""

import hashlib

import pytest

from planfile import Planfile
from planfile.importers.code2llm_importer import import_code2llm


def import_report(tmp_path, content, **kwargs):
    path = tmp_path / "analysis.toon.yaml"
    path.write_text(content, encoding="utf-8")
    return import_code2llm(str(path), **kwargs)


def test_current_health_has_concrete_modules_and_advisory_triage(tmp_path):
    content = """# CC average and a NEXT[9] mention are not sections
HEALTH[4]:
  🔴 DUP   30 duplicate class groups
  🔴 GOD   engine/pipeline.py = 760L, 5 classes, 18m, max CC=50
  🔴 GOD   engine/delta.rs = 520L, 4 classes, 14m, max CC=17
  🔴 CYCLE Circular dependency detected: pkg.policy -> pkg.Strategy.evaluate. This indicates high coupling.
REFACTOR[1]:
  🔴 GOD   ignored/summary.py = 999L
PIPELINES[1]:
  🔴 CC ignored = 99 (limit: 15)
"""
    tickets = import_report(tmp_path, content)
    assert len(tickets) == 4
    modules = [t for t in tickets if "god-module" in t["labels"]]
    assert [t["files"] for t in modules] == [["engine/pipeline.py"], ["engine/delta.rs"]]
    assert modules[0]["source"]["context"]["cc"] == 50
    assert tickets[0]["source"]["context"]["groups"] == 30
    assert tickets[-1]["source"]["context"]["chain"] == "pkg.policy -> pkg.Strategy.evaluate"
    for ticket in tickets:
        assert ticket["name"] == ticket["title"]
        assert "executor" not in ticket
        assert (
            ticket["source"]["context"]["analysis_sha256"]
            == hashlib.sha256(content.encode()).hexdigest()
        )
        assert ticket["source"]["context"]["analysis_path"] == str(tmp_path / "analysis.toon.yaml")
    assert all("files" not in t for t in tickets if "triage" in t["labels"])


def test_imported_health_records_persist_through_normal_bulk_api(tmp_path):
    data = import_report(
        tmp_path,
        """HEALTH[3]:
  🔴 GOD engine/core.py = 955L, max CC=49
  🔴 DUP 30 duplicate class groups
  🔴 CYCLE Circular dependency detected: pkg.a -> pkg.b. This indicates high coupling.
""",
    )
    pf = Planfile(str(tmp_path / "project"))
    created = pf.create_tickets_bulk(data, source="code2llm", sprint="backlog")
    assert len(created) == 3
    for item, original in zip(created, data, strict=True):
        stored = pf.get_ticket(item.id)
        assert stored.name == original["name"]
        assert stored.source.context == original["source"]["context"]
        assert stored.executor is None
        assert stored.execution is None
    assert pf.get_ticket(created[0].id).files == ["engine/core.py"]


def test_repeated_health_alerts_share_stable_identity_within_report(tmp_path):
    line = "  🔴 GOD engine/core.py = 955L, max CC=49\n"
    first = import_report(tmp_path, "HEALTH[2]:\n" + line * 2)
    second = import_report(tmp_path, "HEALTH[1]:\n" + line.replace("955L", "960L"))
    assert len(first) == len(second) == 1
    assert (
        first[0]["source"]["context"]["dedupe_key"] == second[0]["source"]["context"]["dedupe_key"]
    )


@pytest.mark.parametrize("metric", ["CC=25", "= 25"])
def test_legacy_cc_retains_numeric_fields_and_priority(tmp_path, metric):
    (ticket,) = import_report(tmp_path, f"HEALTH[1]:\n  🔴 CC pkg.function {metric} (limit: 15)\n")
    assert ticket["title"] == "Reduce CC: pkg.function (CC=25)"
    assert ticket["source"]["context"]["function"] == "pkg.function"
    assert ticket["source"]["context"]["cc"] == 25
    assert ticket["priority"] == "high"


@pytest.mark.parametrize(
    "alert",
    [
        "GOD engine/core.py = 955L",
        "DUP 30 duplicate class groups",
        "CYCLE Circular dependency detected: pkg.a -> pkg.b",
        "CC pkg.f CC=25 (limit:15)",
    ],
)
def test_disabled_auto_priority_is_respected(tmp_path, alert):
    (ticket,) = import_report(tmp_path, f"HEALTH[1]:\n  🔴 {alert}\n", auto_priority=False)
    assert ticket["priority"] == "normal"


def test_legacy_evolution_keeps_fields_and_gains_persistable_name(tmp_path):
    (ticket,) = import_report(
        tmp_path,
        """NEXT[1]:
  [1] ! SPLIT pkg.engine
    WHY: Isolate transport
    EFFORT: 2h
    IMPACT: 6000
""",
    )
    assert ticket["title"] == ticket["name"] == "SPLIT pkg.engine"
    assert ticket["priority"] == "critical"
    assert ticket["description"] == "Isolate transport"
    assert ticket["source"]["context"] == {"impact": 6000, "effort": "2h"}


def test_empty_and_unrecognized_reports_do_not_silently_lose_positive_health(tmp_path):
    assert import_report(tmp_path, "HEALTH[0]:\n  ✅ Healthy\n") == []
    assert import_report(tmp_path, "Not a code2llm report") == []
    with pytest.raises(ValueError, match="no supported alerts"):
        import_report(tmp_path, "HEALTH[1]:\n  🔴 UNKNOWN unsupported format\n")


@pytest.mark.parametrize("path", ["../outside.py", "/outside.py", "C:\\outside.py"])
def test_module_paths_cannot_escape_report_repository(tmp_path, path):
    with pytest.raises(ValueError, match="Unsafe.*path"):
        import_report(tmp_path, f"HEALTH[1]:\n  🔴 GOD {path} = 955L\n")
