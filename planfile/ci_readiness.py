"""Predict, before a pull request is opened, which required checks will fail and why.

Read-only. Each check answers one question the hosted and protected pipelines ask later:

``release-metadata``      does ``planfile/release-metadata.json`` agree with ``pyproject.toml``?
``dependency-freshness``  are the internal dependencies in ``uv.lock`` the published stable targets?
``verifier-pins``         do ``pyproject.toml`` and ``uv.lock`` still match the digests a protected
                          verifier pinned (``--verifier path/to/check-planfile.py``)?
``governance``            does ``./project/governance-check.sh`` pass?

Failing checks are then grouped by the owner of the path that fixes them. When two or more checks
fail and their fixes belong to different workstreams (or to a repository outside this one), the
fixes cannot be delivered as independent green pull requests: every required check must pass on
each of them. That is reported as a *deadlock* that needs an owner decision, instead of being
rediscovered by trial and error.

    python -m planfile.ci_readiness [--root .] [--verifier check-planfile.py] [--format json]

Exit code: 0 all checks pass, 1 a check fails or a deadlock exists, 2 unusable input.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

PASS, FAIL, UNAVAILABLE = "pass", "fail", "unavailable"
EXTERNAL = "external"

# (argv, timeout seconds) -> (returncode, stdout). Injected in tests; real subprocess otherwise.
Runner = Callable[[Sequence[str], float], "tuple[int, str]"]


@dataclass(frozen=True)
class Result:
    id: str
    status: str
    detail: str
    fix_paths: tuple[str, ...] = ()
    hint: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status, "detail": self.detail, "fixPaths": list(self.fix_paths), "hint": self.hint}


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)
    owners: dict[str, list[str]] = field(default_factory=dict)  # check id -> owning workstreams

    @property
    def failing(self) -> list[Result]:
        return [r for r in self.results if r.status == FAIL]

    @property
    def deadlock(self) -> bool:
        groups = {tuple(sorted(self.owners.get(r.id, []))) for r in self.failing if r.fix_paths}
        return len(self.failing) >= 2 and len(groups) >= 2

    @property
    def ok(self) -> bool:
        return not self.failing

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "planfile.ci-readiness/v1",
            "ok": self.ok,
            "deadlock": self.deadlock,
            "checks": [r.as_dict() | {"owners": self.owners.get(r.id, [])} for r in self.results],
        }


def _run(argv: Sequence[str], timeout: float) -> tuple[int, str]:
    try:
        proc = subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return proc.returncode, proc.stdout + proc.stderr


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_release_metadata(root: Path, runner: Runner = _run) -> Result:
    fix = ("planfile/release-metadata.json",)
    try:
        checker = _load_module(root / "planfile/release_availability.py", "_pf_release_availability")
        outcome = checker.check(root, offline=True)
    except (OSError, ImportError, KeyError, ValueError) as exc:
        return Result("release-metadata", UNAVAILABLE, f"{type(exc).__name__}: {exc}", fix)
    if outcome.get("ok"):
        return Result("release-metadata", PASS, f"source {outcome['source_version']} matches release metadata", fix)
    return Result(
        "release-metadata", FAIL, "; ".join(outcome.get("errors", [])) or "release metadata mismatch", fix,
        "bring planfile/release-metadata.json to the version in pyproject.toml once it is published",
    )


def check_dependency_freshness(root: Path, runner: Runner = _run) -> Result:
    fix = ("uv.lock",)
    catalog = root / ".github/internal-dependencies.json"
    if not catalog.is_file():
        return Result("dependency-freshness", UNAVAILABLE, "no .github/internal-dependencies.json", fix)
    code, out = runner(["goal", "dependencies", "--catalog", str(catalog), "--check"], 120)
    start = out.find("{")
    try:
        data = json.loads(out[start:]) if start >= 0 else None
    except ValueError:
        data = None
    if not isinstance(data, dict) or "fresh" not in data:
        return Result("dependency-freshness", UNAVAILABLE, f"goal did not return a freshness report (exit {code})", fix)
    if data["fresh"]:
        return Result("dependency-freshness", PASS, "internal dependencies are current", fix)
    stale = [f"{p['name']} {','.join(p.get('locked', []))} -> {p.get('target')}" for p in data.get("packages", []) if p.get("status") != "current"]
    return Result("dependency-freshness", FAIL, "outdated: " + "; ".join(stale), fix, " ".join(data.get("update_command", [])))


def check_verifier_pins(root: Path, verifier: Path | None, runner: Runner = _run) -> Result:
    external = (f"{EXTERNAL}:verifier",)
    if verifier is None:
        return Result("verifier-pins", UNAVAILABLE, "no --verifier given", external)
    try:
        tree = ast.parse(verifier.read_text(encoding="utf-8"))
        pins = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "INPUTS" for t in node.targets)
        )
    except (OSError, SyntaxError, StopIteration, ValueError) as exc:
        return Result("verifier-pins", UNAVAILABLE, f"cannot read INPUTS from {verifier}: {type(exc).__name__}", external)
    drift = []
    for name, digest in sorted(pins.items()):
        path = root / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() and not path.is_symlink() else "missing"
        if actual != digest:
            drift.append(f"{name} {actual[:8]} != pinned {str(digest)[:8]}")
    if not drift:
        return Result("verifier-pins", PASS, "pinned inputs match", external)
    return Result(
        "verifier-pins", FAIL, "; ".join(drift), external,
        "the protected verifier needs new digests and a rebuilt runtime image; do not edit it from this repository",
    )


def check_governance(root: Path, runner: Runner = _run) -> Result:
    script = root / "project/governance-check.sh"
    if not script.is_file():
        return Result("governance", UNAVAILABLE, "no project/governance-check.sh")
    code, out = runner([str(script)], 600)
    last = [line for line in out.strip().splitlines() if line.strip()][-1:] or [""]
    return Result("governance", PASS if code == 0 else FAIL, last[0][:300])


def owners_of(root: Path, paths: Sequence[str]) -> list[str]:
    """Workstreams owning ``paths`` according to ``.governance/manifest.json``; external paths stay external."""
    try:
        manifest = json.loads((root / ".governance/manifest.json").read_text(encoding="utf-8"))
        workstreams = manifest["coordination"]["workstreams"]
    except (OSError, KeyError, ValueError):
        workstreams = {}
    found: set[str] = set()
    for path in paths:
        if path.startswith(EXTERNAL + ":"):
            found.add(path.split(":", 1)[0])
            continue
        for name, spec in workstreams.items():
            if any(fnmatch.fnmatchcase(path, pattern) for pattern in spec.get("ownedPaths", [])):
                found.add(name)
    return sorted(found)


def evaluate(root: Path, verifier: Path | None = None, runner: Runner = _run, skip: Sequence[str] = ()) -> Report:
    root = root.resolve()
    checks: list[tuple[str, Callable[[], Result]]] = [
        ("release-metadata", lambda: check_release_metadata(root, runner)),
        ("dependency-freshness", lambda: check_dependency_freshness(root, runner)),
        ("verifier-pins", lambda: check_verifier_pins(root, verifier, runner)),
        ("governance", lambda: check_governance(root, runner)),
    ]
    report = Report()
    for check_id, run in checks:
        if check_id in skip:
            continue
        result = run()
        report.results.append(result)
        report.owners[result.id] = owners_of(root, result.fix_paths)
    return report


def render_text(report: Report) -> str:
    lines = []
    for r in report.results:
        owners = ",".join(report.owners.get(r.id, [])) or "-"
        lines.append(f"{r.status.upper():11} {r.id}: {r.detail}" + (f"  [fix owner: {owners}]" if r.status == FAIL else ""))
        if r.status == FAIL and r.hint:
            lines.append(f"{'':11} hint: {r.hint}")
    if report.deadlock:
        who = sorted({o for r in report.failing for o in report.owners.get(r.id, [])})
        lines.append(
            "DEADLOCK: failing checks need fixes from different owners (" + ", ".join(who) + "). Each required check must "
            "pass on every pull request, so the fixes cannot merge independently; an owner decision is needed."
        )
    lines.append("CI-READY" if report.ok and not report.deadlock else "CI-NOT-READY")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, runner: Runner = _run) -> int:
    parser = argparse.ArgumentParser(prog="planfile.ci_readiness", description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--verifier", type=Path, default=None, help="protected check-planfile.py whose INPUTS pins are compared")
    parser.add_argument("--skip", action="append", default=[], help="check id to skip (repeatable)")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    if not (args.root / "pyproject.toml").is_file():
        print(f"CI-READINESS-INPUT: {args.root} has no pyproject.toml", file=sys.stderr)
        return 2
    report = evaluate(args.root, args.verifier, runner, skip=args.skip)
    print(json.dumps(report.as_dict(), indent=2) if args.format == "json" else render_text(report))
    return 0 if report.ok and not report.deadlock else 1


if __name__ == "__main__":
    raise SystemExit(main())
