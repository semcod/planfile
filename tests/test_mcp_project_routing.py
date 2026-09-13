"""MCP plan operations must use the requested project, not a cached neighbor."""

from types import SimpleNamespace

import pytest
import yaml

from planfile.mcp import server


@pytest.fixture
def projects(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    for directory in (first, second):
        directory.mkdir()
        (directory / "planfile.yaml").write_text(
            yaml.safe_dump({"project": directory.name, "sprints": [directory.name]})
        )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLANFILE_MCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("PLANFILE_MCP_ALLOW_MUTATION", "1")
    cached = SimpleNamespace(store=SimpleNamespace(project_dir=first))
    monkeypatch.setattr(server, "get_planfile", lambda: cached)
    return first, second


def test_explicit_read_and_sprints_ignore_cached_project(projects):
    first, second = projects
    assert server.handle_tool_call("planfile_yaml_get", {})["project"] == first.name
    for directory in (second, first, second):
        args = {"project_path": str(directory)}
        assert server.handle_tool_call("planfile_yaml_get", args)["project"] == directory.name
        assert server.handle_tool_call("planfile_list_sprints", args) == [directory.name]


def test_explicit_patch_changes_only_selected_project(projects):
    first, second = projects
    before = (first / "planfile.yaml").read_bytes()
    result = server.handle_tool_call(
        "planfile_yaml_patch",
        {"project_path": str(second), "path": "metadata.owner", "value": "second"},
    )
    assert result == {"patched": "metadata.owner", "value": "second"}
    assert (first / "planfile.yaml").read_bytes() == before
    assert yaml.safe_load((second / "planfile.yaml").read_text())["metadata"]["owner"] == "second"


def test_relative_project_path(projects):
    _, second = projects
    assert server.handle_tool_call(
        "planfile_yaml_get", {"project_path": second.name}
    )["project"] == second.name


@pytest.mark.parametrize("tool", ["planfile_yaml_get", "planfile_yaml_patch", "planfile_list_sprints"])
def test_missing_explicit_plan_never_uses_default(projects, tool):
    first, second = projects
    before = (first / "planfile.yaml").read_bytes()
    (second / "planfile.yaml").unlink()
    result = server.handle_tool_call(
        tool, {"project_path": str(second), "path": "project", "value": "wrong"}
    )
    assert result == ([] if tool == "planfile_list_sprints" else {"error": "planfile.yaml not found"})
    assert (first / "planfile.yaml").read_bytes() == before
    assert not (second / "planfile.yaml").exists()


@pytest.mark.parametrize("tool", ["planfile_yaml_get", "planfile_yaml_patch", "planfile_list_sprints"])
def test_outside_root_and_symlink_directory_rejected(projects, monkeypatch, tool):
    first, second = projects
    monkeypatch.setenv("PLANFILE_MCP_PROJECT_ROOT", str(first))
    link = first / "neighbor"
    link.symlink_to(second, target_is_directory=True)
    for directory in (second, link):
        with pytest.raises(PermissionError, match="PLANFILE_MCP_PROJECT_ROOT"):
            server.handle_tool_call(
                tool, {"project_path": str(directory), "path": "project", "value": "wrong"}
            )


def test_patch_still_requires_mutation_capability(projects, monkeypatch):
    first, second = projects
    before = [(p / "planfile.yaml").read_bytes() for p in projects]
    monkeypatch.delenv("PLANFILE_MCP_ALLOW_MUTATION")
    with pytest.raises(PermissionError, match="PLANFILE_MCP_ALLOW_MUTATION"):
        server.handle_tool_call(
            "planfile_yaml_patch",
            {"project_path": str(second), "path": "project", "value": "wrong"},
        )
    assert [(p / "planfile.yaml").read_bytes() for p in (first, second)] == before


def test_omitted_path_preserves_default_store(projects):
    first, second = projects
    before = (second / "planfile.yaml").read_bytes()
    assert server.handle_tool_call("planfile_list_sprints", {}) == [first.name]
    server.handle_tool_call("planfile_yaml_patch", {"path": "project", "value": "default"})
    assert server.handle_tool_call("planfile_yaml_get", {})["project"] == "default"
    assert (second / "planfile.yaml").read_bytes() == before


@pytest.mark.parametrize("path", [None, "", " ", 42])
def test_invalid_explicit_path_rejected(projects, path):
    with pytest.raises(ValueError, match="project_path"):
        server.handle_tool_call("planfile_yaml_get", {"project_path": path})
