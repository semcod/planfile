"""Differential tests: planfile_native must reproduce PyYAML/json byte for byte or refuse."""

from __future__ import annotations

import datetime as dt
import json
import os
import random
import stat
import string

import pytest
import yaml

native = pytest.importorskip("planfile_native")
if not native.AVAILABLE:  # pragma: no cover
    pytest.skip("compiled extension missing", allow_module_level=True)

try:
    Dumper = yaml.CSafeDumper
except AttributeError:  # pragma: no cover
    pytest.skip("PyYAML without libyaml: reference output differs", allow_module_level=True)


def reference(data, allow_unicode=False):
    return yaml.dump(data, default_flow_style=False, allow_unicode=allow_unicode, Dumper=Dumper)


CURATED = [
    {"a": 1},
    {},
    [],
    [1, 2, [3, [4, {"k": []}]], {}],
    {"s": ["", " ", "  x", "x ", " x ", "a  b", "a\tb", "tab\t", "multi\nline", "trail\n", "\nlead",
           "a\n b", "a \nb", "x\r\ny", "'q'", '"d"', "back\\slash", "#c", "a #c", "a: b", "a:b",
           "- x", "-x", "-", "?", "? x", ":x", "key: v", "[x]", "{x}", "x,y", "&a", "*a", "!t",
           "|", ">", "%", "@", "`", "---", "...", "--- x", "null", "Null", "~", "true", "Yes", "off",
           "1", "01", "0o7", "0x1f", "1_000", "1.5", "1e3", "1.0e+3", ".5", ".inf", "-.INF", ".nan",
           "2026-10-19", "2026-10-19 12:00:00", "12:30:45", "=", "<<", "!", "&", "*"]},
    {"unicode": ["zażółć gęślą jaźń", "naïve café", "日本語", "emoji 😀 x", "\u0085nel", "\u2028ls",
                 "\u00a0nbsp", "\ufeffbom", "\x00nul", "\x1b[0m", "\x7fdel", "\ud7ff\ue000\ufffd"]},
    {"long": "word " * 60, "longq": "it's " * 40, "longd": "tab\t" + "word " * 60, "x" * 200: 1,
     "nl\nkey": 2, "k" * 128: 3, "k" * 129: 4},
    {"nested": {"deep": {"deeper": {"list": [{"a": 1, "b": [1, 2]}, [[1], [2, [3]]]]}}}},
    {"num": [0, -1, 10**30, 1.0, -2.5, 1e-05, 1e16, 1.5e300, float("inf"), float("-inf"), True, False, None]},
    {"when": dt.datetime(2026, 10, 19, 16, 38, 31), "tz": dt.datetime(2026, 10, 19, 16, 38, 31, 123456,
                                                                     tzinfo=dt.timezone.utc),
     "day": dt.date(2026, 10, 19)},
    {"tuple": (1, "a", (2,))},
    {"z": 1, "a": {"y": 1, "b": 2}, "Z": 3, "_": 4, "é": 5},
]


@pytest.mark.parametrize("allow_unicode", [False, True])
@pytest.mark.parametrize("data", CURATED, ids=lambda d: repr(d)[:40])
def test_curated_yaml_matches_pyyaml(data, allow_unicode):
    assert native.dump_yaml(data, allow_unicode) == reference(data, allow_unicode)


ALPHABET = (
    string.ascii_letters + string.digits + " " * 6 + "\n\t'\"\\:#-?,[]{}&*!|>%@`~=<.\r"
    + "żółćéß日\u0085\u2028\u00a0\u2029"
)
WORDS = ["null", "true", "no", "1", "0", "-", "yes", "", "~", "<<", "2026-01-02", "1.5", "a b", "---", "..."]


def random_string(rng: random.Random) -> str:
    if rng.random() < 0.15:
        return rng.choice(WORDS)
    base = "".join(rng.choice(ALPHABET) for _ in range(rng.choice([1, 2, 3, 5, 12, 40, 90, 200])))
    if rng.random() < 0.2:
        base = " ".join(["word"] * rng.randint(10, 60))
    return base


def random_value(rng: random.Random, depth: int):
    kind = rng.random()
    if depth > 4 or kind < 0.45:
        return rng.choice([
            lambda: random_string(rng), lambda: rng.randint(-10**12, 10**12),
            lambda: rng.uniform(-1e6, 1e6), lambda: rng.choice([True, False, None]),
            lambda: rng.choice([1e-7, 1e22, 0.1, 1 / 3]),
        ])()
    if kind < 0.7:
        return [random_value(rng, depth + 1) for _ in range(rng.randint(0, 5))]
    return {random_string(rng) if rng.random() < 0.8 else f"k{i}": random_value(rng, depth + 1)
            for i in range(rng.randint(0, 6))}


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("allow_unicode", [False, True])
def test_random_documents_match_pyyaml(seed, allow_unicode):
    rng = random.Random(seed)
    for _ in range(60):
        data = {"root": random_value(rng, 0)} if rng.random() < 0.5 else [random_value(rng, 0)]
        try:
            expected = reference(data, allow_unicode)
        except Exception:
            with pytest.raises(Exception):
                native.dump_yaml(data, allow_unicode)
            continue
        assert native.dump_yaml(data, allow_unicode) == expected, repr(data)
        assert yaml.safe_load(native.dump_yaml(data, allow_unicode)) == yaml.safe_load(expected)


class StrSub(str):
    pass


@pytest.mark.parametrize(
    "data",
    [
        {"a": StrSub("x")},
        {"a": {1, 2}},
        {1: "int key"},
        {"a": b"bytes"},
        {"a": datetime_time} if (datetime_time := dt.time(1, 2)) else None,
        "scalar root",
    ],
)
def test_unsupported_values_raise_unsupported(data):
    with pytest.raises(native.Unsupported):
        native.dump_yaml(data)


def test_shared_container_is_refused_because_pyyaml_emits_anchors():
    shared = [1]
    data = {"a": shared, "b": shared}
    assert "&id001" in reference(data)
    with pytest.raises(native.Unsupported):
        native.dump_yaml(data)


def test_cycle_is_refused():
    data: dict = {}
    data["self"] = data
    with pytest.raises(native.Unsupported):
        native.dump_yaml(data)


def test_lone_surrogate_is_refused():
    with pytest.raises(native.Unsupported):
        native.dump_yaml({"a": "\ud800"})


def _json_safe(value):
    if isinstance(value, dict):
        return {_json_safe(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    return value


JSON_CASES = [d for d in CURATED if not (isinstance(d, dict) and any(not isinstance(k, str) for k in d))]


@pytest.mark.parametrize("data", JSON_CASES, ids=lambda d: repr(d)[:40])
def test_json_matches_cpython_encoder(data):
    assert native.dump_json(data) == json.dumps(_json_safe(data), ensure_ascii=False)


@pytest.mark.parametrize("data", CURATED + [dt.time(3, 4)], ids=lambda d: repr(d)[:40])
def test_normalize_matches_json_safe(data):
    assert native.normalize(data) == _json_safe(data)
    assert type(native.normalize(data)) is type(_json_safe(data))


def test_write_sprint_writes_yaml_and_matching_mirror(tmp_path):
    path = tmp_path / "sub" / "current.yaml"
    data = {"tickets": {"PLF-1": {"name": "zażółć", "when": dt.datetime(2026, 1, 2, 3, 4, 5)}}}
    mtime, mirror_error = native.write_sprint(str(path), data, True, 1, ".fast.json", True)
    assert mirror_error is None
    assert path.read_text(encoding="utf-8") == reference(data, True)
    assert mtime == path.stat().st_mtime_ns
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    mirror = json.loads((tmp_path / "sub" / "current.yaml.fast.json").read_text(encoding="utf-8"))
    assert mirror == {"version": 1, "yaml_mtime_ns": mtime, "data": _json_safe(data)}
    assert [p.name for p in path.parent.iterdir() if p.name.endswith(".tmp")] == []


def test_write_sprint_unsupported_leaves_filesystem_untouched(tmp_path):
    path = tmp_path / "current.yaml"
    with pytest.raises(native.Unsupported):
        native.write_sprint(str(path), {"a": {1, 2}}, True, 1, ".fast.json", False)
    assert list(tmp_path.iterdir()) == []


def test_write_sprint_reports_mirror_failure_without_raising(tmp_path):
    path = tmp_path / "current.yaml"
    (tmp_path / "current.yaml.fast.json").mkdir()  # rename onto a directory fails
    mtime, mirror_error = native.write_sprint(str(path), {"a": 1}, True, 1, ".fast.json", False)
    assert mirror_error
    assert path.read_text() == "a: 1\n" and mtime == path.stat().st_mtime_ns


def test_write_sprint_raises_oserror_for_unwritable_target(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(OSError):
        native.write_sprint(str(blocker / "child.yaml"), {"a": 1}, True, 1, ".fast.json", False)


def test_atomic_write_text_replaces_content(tmp_path):
    target = tmp_path / "a.txt"
    native.atomic_write_text(str(target), "one")
    native.atomic_write_text(str(target), "dwa żółw", False)
    assert target.read_text(encoding="utf-8") == "dwa żółw"
    assert os.listdir(tmp_path) == ["a.txt"]
