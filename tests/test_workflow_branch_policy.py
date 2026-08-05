from pathlib import Path


def test_ci_does_not_create_a_gh_pages_branch() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "ci-auto-loop.yml"
    ).read_text(encoding="utf-8")

    assert "actions-gh-pages" not in workflow
    assert "gh-pages" not in workflow
