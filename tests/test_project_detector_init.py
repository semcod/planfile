"""Regression: pyproject detection must not NameError (PLF-065).

The project_detector split left pyproject.py using eight helpers it never
imported (`planfile init` crashed with NameError on any pyproject with
dependencies)."""

from pathlib import Path

from planfile.cli.project_detector.main import detect_project


def test_detect_project_full_path_no_nameerror(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "x"\n'
        'version = "0.1.0"\n'
        'description = "demo"\n'
        'keywords = ["api"]\n'
        'dependencies = ["fastapi>=0.110"]\n',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# x\n\nDemo project.\n", encoding="utf-8")

    project = detect_project(tmp_path)

    assert project is not None
    assert project.name == "x"
