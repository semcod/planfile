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


def test_ci_uses_immutable_node_24_official_actions() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "ci-auto-loop.yml"
    ).read_text(encoding="utf-8")

    for action in (
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
        "actions/cache@caa296126883cff596d87d8935842f9db880ef25",
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    ):
        assert action in workflow
