"""Tests verifying integration of native Rust acceleration packages with graceful fallback."""

import json
from pathlib import Path
from planfile.core.fastio import HAS_RUST_IO, read_yaml_fast
from planfile.core.semantic import HAS_RUST_SEMANTIC, lexical_similarity, similarity_matrix
from planfile.core.decompose import HAS_RUST_GRAPH, build_tree, tree_progress
from planfile.dsl.parser import HAS_RUST_DSL, DSLParser
from planfile.core.jsonl_tail import HAS_RUST_JOURNAL, read_jsonl_tail


def test_fastio_acceleration():
    print(f"HAS_RUST_IO: {HAS_RUST_IO}")
    data = read_yaml_fast(Path("tests/test_fastio_native.py"))  # or any file
    # Ensure read_yaml_fast runs without error


def test_semantic_acceleration():
    print(f"HAS_RUST_SEMANTIC: {HAS_RUST_SEMANTIC}")
    score = lexical_similarity("Fix payment gateway authentication", "Fix login and payment auth")
    assert 0.0 <= score <= 1.0

    matrix, method = similarity_matrix(["Task A", "Task B", "Task C"])
    assert len(matrix) == 3
    assert len(matrix[0]) == 3
    assert method in ("lexical", "embed")


def test_dsl_acceleration():
    print(f"HAS_RUST_DSL: {HAS_RUST_DSL}")
    parser = DSLParser()
    cmd = parser.parse("dodaj zadanie 'Refactor native core' priority=critical")
    assert cmd.verb == "create"
    assert cmd.object_type == "ticket"
    assert cmd.target == "Refactor native core"
    assert cmd.params["priority"] == "critical"


def test_journal_acceleration(tmp_path):
    print(f"HAS_RUST_JOURNAL: {HAS_RUST_JOURNAL}")
    log_file = tmp_path / "test.jsonl"
    with open(log_file, "w", encoding="utf-8") as f:
        for i in range(20):
            f.write(json.dumps({"id": i, "msg": f"event {i}"}) + "\n")

    tail = read_jsonl_tail(log_file, limit=5)
    assert len(tail) == 5
    assert tail[0]["id"] == 19
    assert tail[4]["id"] == 15


def test_analyzer_acceleration(tmp_path):
    from planfile.analysis.file_analyzer import FileAnalyzer, HAS_RUST_ANALYZER
    print(f"HAS_RUST_ANALYZER: {HAS_RUST_ANALYZER}")
    sample = tmp_path / "sample.py"
    sample.write_text("# TODO: implement caching\n# FIXME: memory leak\ncoverage = 92.5%\n")
    analyzer = FileAnalyzer()
    issues, metrics, tasks = analyzer.analyze_file(sample)
    assert len(issues) == 2
    assert any("implement caching" in i.name for i in issues)
    assert any(m.name == "coverage" and m.value == 92.5 for m in metrics)


def test_graph_acceleration():
    print(f"HAS_RUST_GRAPH: {HAS_RUST_GRAPH}")
    nodes = {
        "root": {"id": "root", "name": "Epic", "status": "open", "children": ["c1", "c2"]},
        "c1": {"id": "c1", "name": "Subtask 1", "status": "done", "children": []},
        "c2": {"id": "c2", "name": "Subtask 2", "status": "open", "children": []},
    }
    tree = build_tree(nodes, "root")
    assert tree["id"] == "root"
    assert len(tree["children"]) == 2

    prog = tree_progress(nodes, "root")
    assert prog["subtasks"] == 2
    assert prog["done"] == 1
    assert prog["complete"] is False
