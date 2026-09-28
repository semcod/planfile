import tempfile
from pathlib import Path
from planfile.core.fastio import read_yaml_fast, write_mirror, HAS_RUST_IO


def test_fastio_native_flag():
    # HAS_RUST_IO should be a boolean (True when planfile_io is installed, False otherwise)
    assert isinstance(HAS_RUST_IO, bool)


def test_fastio_read_yaml_fast():
    with tempfile.TemporaryDirectory() as tmp_dir:
        p = Path(tmp_dir) / "test.yaml"
        p.write_text("sprint: current\nname: Test Sprint\ntickets:\n  - id: PLF-1\n    name: First\n", encoding="utf-8")

        data = read_yaml_fast(p)
        assert data is not None
        assert data.get("sprint") == "current"
        assert len(data.get("tickets", [])) == 1
        assert data["tickets"][0]["id"] == "PLF-1"


def test_fastio_missing_file():
    missing = Path("/nonexistent/path/to/missing.yaml")
    assert read_yaml_fast(missing) is None
