"""Foundation helpers stay dependency-free and keep their callers' behavior."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from planfile import project_paths
from planfile.sync import state
from planfile.utils.repository import normalize_repository
from planfile.utils.yaml_cache import _load_yaml_cached, read_yaml_file

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("raw", [
    "owner/repo", "Owner/Repo", "https://github.com/Owner/Repo.git", "HTTP://GITHUB.COM/owner/repo/",
    "git@github.com:Owner/Repo.git", "ssh://git@github.com/Owner/Repo", "  owner/repo  ",
])
def test_normalize_repository_accepts_github_forms(raw):
    assert normalize_repository(raw) == "owner/repo"


@pytest.mark.parametrize("raw", ["", "owner", "owner/repo/extra", "https://gitlab.com/o/r", "o w/r"])
def test_normalize_repository_rejects_non_identities(raw):
    with pytest.raises(ValueError):
        normalize_repository(raw)


def test_normalize_repository_passes_none_through():
    assert normalize_repository(None) is None


def test_callers_share_one_implementation():
    assert state.normalize_repository is normalize_repository
    assert project_paths.normalize_repository is normalize_repository
    assert state._read_yaml_file is read_yaml_file is project_paths._read_yaml_file


def test_read_yaml_file_caches_until_the_file_changes(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("a: 1\n")
    _load_yaml_cached.cache_clear()
    assert read_yaml_file(path) == {"a": 1}
    assert read_yaml_file(path) == {"a": 1}
    assert _load_yaml_cached.cache_info().hits == 1
    stat = path.stat()
    path.write_text("a: 2\n")
    import os
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert read_yaml_file(path) == {"a": 2}


def _planfile_imports(module: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("planfile"):
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names if alias.name.startswith("planfile"))
    return names


from planfile.utils.uri import (
    manage_uri_process,
    register_uri_process,
    render_uri_call_snippet,
    uri,
    uri_jsonl,
    uri_main,
)


@pytest.mark.parametrize("module", ["planfile/utils/repository.py", "planfile/utils/yaml_cache.py"])
def test_helpers_import_nothing_from_planfile(module):
    assert _planfile_imports(ROOT / module) == set()


def test_uri_helper_stays_within_foundation_layer():
    imports = _planfile_imports(ROOT / "planfile/utils/uri.py")
    assert imports <= {"planfile.utils.repository", "planfile.utils.yaml_cache"}


def test_project_paths_no_longer_reaches_into_sync():
    """Foundation must not depend on the sync layer, not even through a function-level import."""
    assert not any(name.startswith("planfile.sync") for name in _planfile_imports(ROOT / "planfile/project_paths.py"))


def test_uri_foundation_repo_normalize_single_and_jsonl(tmp_path: Path):
    res = uri("proc://planfile/repo/normalize/v1", {"repo": "https://github.com/SemCod/PlanFile.git"})
    assert isinstance(res, dict)
    assert res["status"] == "ok"
    assert res["repository"] == "semcod/planfile"

    batch = uri(
        "proc://planfile/repo/normalize/v1",
        '{"repo": "Owner/One"}\n{"repo": "git@github.com:Owner/Two.git"}\n',
    )
    assert isinstance(batch, list)
    assert [r["repository"] for r in batch] == ["owner/one", "owner/two"]

    jsonl_path = tmp_path / "repos.jsonl"
    jsonl_path.write_text('{"repo": "A/B"}\n{"repo": "C/D"}\n', encoding="utf-8")
    from_file = uri("proc://planfile/repo/normalize/v1", f"@{jsonl_path}")
    assert isinstance(from_file, list)
    assert [r["repository"] for r in from_file] == ["a/b", "c/d"]

    streamed = uri_jsonl("proc://planfile/repo/normalize/v1", ['{"repo": "X/Y"}', {"repo": "Z/W"}])
    assert [r["repository"] for r in streamed] == ["x/y", "z/w"]


def test_uri_foundation_yaml_read(tmp_path: Path):
    sample = tmp_path / "sample.yaml"
    sample.write_text("service: planfile\ncount: 3\n", encoding="utf-8")
    res = uri("proc://planfile/yaml/read/v1", {"path": str(sample)})
    assert res == {"status": "ok", "service": "proc://planfile/yaml/read/v1", "data": {"service": "planfile", "count": 3}}


def test_uri_custom_registration_and_query_coercion():
    register_uri_process(
        "proc://planfile/custom/check/v1",
        lambda params: {"status": "ok", "received": params},
    )
    res = uri("proc://planfile/custom/check/v1?dry_run=true&max_items=10", {"project": "demo"})
    assert isinstance(res, dict)
    assert res["received"] == {"dry_run": True, "max_items": 10, "project": "demo"}


def test_manage_uri_process_lifecycle_generate_modify_relocate(tmp_path: Path):
    manifest_a = tmp_path / "project_a" / "dockuri.yaml"
    manifest_b = tmp_path / "project_b" / "dockuri.yaml"

    gen = manage_uri_process(
        "generate",
        "proc://planfile/sprint/deduplicate/v1",
        manifest=str(manifest_a),
        run=["uri", "proc://system/sprint/deduplicate/v1"],
        description="Deduplicate sprint tickets via dockuri",
    )
    assert gen["status"] == "ok"
    assert gen["action"] == "generated"
    assert manifest_a.is_file()
    assert "proc://planfile/sprint/deduplicate/v1" in gen["call_snippets"]["python"]

    mod = manage_uri_process(
        "modify",
        "proc://planfile/sprint/deduplicate/v1",
        manifest=str(manifest_a),
        description="Updated description",
    )
    assert mod["status"] == "ok"
    assert mod["action"] == "modified"
    assert mod["process"]["description"] == "Updated description"

    reloc = manage_uri_process(
        "relocate",
        "proc://planfile/sprint/deduplicate/v1",
        new_uri="proc://system/sprint/deduplicate/v1",
        manifest=str(manifest_a),
        dest_manifest=str(manifest_b),
    )
    assert reloc["status"] == "ok"
    assert reloc["action"] == "relocated"
    assert manifest_b.is_file()


def test_render_uri_call_snippet_polyglot_languages():
    target = "proc://system/sprint/deduplicate/v1"
    for lang, expected in [
        ("python", "def invoke("),
        ("bash", "exec uri"),
        ("js", "execFileSync('uri'"),
        ("rust", 'Command::new("uri")'),
        ("go", 'exec.Command("uri"'),
        ("php", "function uri("),
    ]:
        snippet = render_uri_call_snippet(target, {"dry_run": True}, lang=lang)
        assert expected in snippet
        assert target in snippet


def test_uri_main_cli_execution(capsys):
    rc = uri_main(["proc://planfile/repo/normalize/v1", '{"repo": "SemCod/Planfile"}'])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert '"repository": "semcod/planfile"' in out

