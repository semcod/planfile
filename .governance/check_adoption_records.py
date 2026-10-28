#!/usr/bin/env python3
"""Verify the recorded standard-pack adoptions stay honest (issue #307).

Executable governance check: every profile requirement must be recorded at or
above its minimum level, every artifact/evidence digest must match the managed
projection on disk, and the repository's own standard-pack checker must keep
reporting ``ok``. Exit code 0 means the adoption record is intact.

    python3 .governance/check_adoption_records.py --root .
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

LEVELS = {f"S{index}": index for index in range(6)}
SCHEMA = "wellmanifest.adoption-integrity/v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def findings(root: Path) -> list[dict]:
    adoption_path = root / ".governance" / "standard-adoption.json"
    catalog_path = root / ".governance" / "standard-packs.json"
    rows: list[dict] = []
    if not adoption_path.is_file() or not catalog_path.is_file():
        return [{"code": "ADOPTION-SOURCE-MISSING", "detail": "adoption or catalog file is absent"}]
    try:
        adoption = load(adoption_path)
        catalog = load(catalog_path)
    except (json.JSONDecodeError, OSError) as exc:
        return [{"code": "ADOPTION-SOURCE-MALFORMED", "detail": f"failed to load JSON: {exc}"}]

    profile_name = adoption.get("profile")
    if not isinstance(profile_name, str) or not profile_name:
        return [{"code": "ADOPTION-PROFILE-MISSING", "detail": "adoption record profile is missing or invalid"}]

    catalog_profiles = catalog.get("profiles")
    if not isinstance(catalog_profiles, dict) or profile_name not in catalog_profiles:
        return [{"code": "ADOPTION-PROFILE-UNKNOWN", "detail": f"unknown adoption profile {profile_name!r}"}]

    profile = catalog_profiles[profile_name]
    if not isinstance(profile, dict) or not isinstance(profile.get("requirements"), list):
        return [{"code": "ADOPTION-PROFILE-MALFORMED", "detail": f"profile {profile_name!r} requirements malformed"}]

    requirements = profile.get("requirements") or []
    if not requirements:
        return [{"code": "ADOPTION-PROFILE-EMPTY", "detail": f"profile {profile_name!r} declares no requirements"}]

    records = {
        record["id"]: record
        for record in adoption.get("adoptions") or []
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }

    for requirement in requirements:
        pack_id = requirement.get("id")
        minimum = requirement.get("minimumLevel")
        record = records.get(pack_id)
        if record is None:
            rows.append({"code": "ADOPTION-MISSING", "pack": pack_id,
                         "detail": f"no adoption record for {pack_id}"})
            continue
        level = record.get("level")
        if level not in LEVELS or minimum not in LEVELS:
            rows.append({"code": "ADOPTION-LEVEL", "pack": pack_id,
                         "detail": f"invalid level {level!r} or minimum {minimum!r}"})
            continue
        if LEVELS[level] < LEVELS[minimum]:
            rows.append({"code": "ADOPTION-BELOW-MINIMUM", "pack": pack_id,
                         "detail": f"{level} < {minimum}"})
        models = catalog.get("executionModels") or {}
        model = record.get("model")
        ceiling = LEVELS.get((models.get(model) or {}).get("maximumLevel", ""), -1)
        if model not in models or LEVELS[level] > ceiling:
            rows.append({"code": "ADOPTION-MODEL", "pack": pack_id,
                         "detail": f"{model} cannot claim {level}"})
        for artifact in record.get("artifacts") or []:
            target = artifact.get("target")
            expected = artifact.get("sha256")
            if not isinstance(target, str) or not isinstance(expected, str):
                rows.append({"code": "ADOPTION-ARTIFACT", "pack": pack_id,
                             "detail": "artifact entry is incomplete"})
                continue
            path = root / target
            if not path.is_file():
                rows.append({"code": "ADOPTION-ARTIFACT", "pack": pack_id,
                             "detail": f"target {target} is missing"})
            elif digest(path) != expected:
                rows.append({"code": "ADOPTION-DRIFT", "pack": pack_id,
                             "detail": f"target {target} digest changed"})

        # Evidence validation: each entry must have a valid level, existing uri, and matching content digest
        verified_evidence_levels: set[str] = set()
        for item in record.get("evidence") or []:
            if not isinstance(item, dict):
                rows.append({"code": "ADOPTION-EVIDENCE", "pack": pack_id,
                             "detail": "evidence entry is not a mapping"})
                continue
            item_level = item.get("level")
            item_uri = item.get("uri")
            expected_sha = item.get("sha256")
            if not isinstance(item_level, str) or not isinstance(item_uri, str) or not isinstance(expected_sha, str):
                rows.append({"code": "ADOPTION-EVIDENCE", "pack": pack_id,
                             "detail": "evidence entry is incomplete (missing level, uri, or sha256)"})
                continue
            ev_path = root / item_uri
            if not ev_path.is_file():
                rows.append({"code": "ADOPTION-EVIDENCE-MISSING", "pack": pack_id,
                             "detail": f"evidence uri {item_uri} for {item_level} is missing"})
            elif digest(ev_path) != expected_sha:
                rows.append({"code": "ADOPTION-EVIDENCE-DRIFT", "pack": pack_id,
                             "detail": f"evidence uri {item_uri} for {item_level} digest changed"})
            else:
                verified_evidence_levels.add(item_level)

        for index in range(LEVELS[level] + 1):
            if f"S{index}" not in verified_evidence_levels:
                rows.append({"code": "ADOPTION-EVIDENCE", "pack": pack_id,
                             "detail": f"lacks verified S{index} evidence"})
    return rows


def run_self_tests(root: Path) -> int:
    """Execute built-in self-tests verifying fail-closed integrity checks."""
    current = findings(root)
    if current:
        print(f"SELF-TEST-FAIL: current repository adoption check failed: {current}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        gov = tmp / ".governance"
        gov.mkdir(parents=True)

        catalog_src = root / ".governance" / "standard-packs.json"
        adoption_src = root / ".governance" / "standard-adoption.json"
        manifest_src = root / ".governance" / "manifest.json"

        gov.joinpath("standard-packs.json").write_bytes(catalog_src.read_bytes())
        gov.joinpath("standard-adoption.json").write_bytes(adoption_src.read_bytes())
        gov.joinpath("manifest.json").write_bytes(manifest_src.read_bytes())

        # 1. Baseline must pass
        if findings(tmp) != []:
            print("SELF-TEST-FAIL: valid copy did not pass", file=sys.stderr)
            return 1

        # 2. Unknown profile must fail
        data = load(gov / "standard-adoption.json")
        data["profile"] = "nonexistent-profile"
        gov.joinpath("standard-adoption.json").write_text(json.dumps(data), encoding="utf-8")
        res = findings(tmp)
        if not any(r.get("code") == "ADOPTION-PROFILE-UNKNOWN" for r in res):
            print("SELF-TEST-FAIL: unknown profile was not detected", file=sys.stderr)
            return 1

        # 3. Missing profile must fail
        del data["profile"]
        gov.joinpath("standard-adoption.json").write_text(json.dumps(data), encoding="utf-8")
        res = findings(tmp)
        if not any(r.get("code") == "ADOPTION-PROFILE-MISSING" for r in res):
            print("SELF-TEST-FAIL: missing profile was not detected", file=sys.stderr)
            return 1

        # 4. Missing evidence file must fail
        gov.joinpath("standard-adoption.json").write_bytes(adoption_src.read_bytes())
        data = load(gov / "standard-adoption.json")
        data["adoptions"][0]["evidence"][0]["uri"] = ".governance/nonexistent-file.json"
        gov.joinpath("standard-adoption.json").write_text(json.dumps(data), encoding="utf-8")
        res = findings(tmp)
        if not any(r.get("code") == "ADOPTION-EVIDENCE-MISSING" for r in res):
            print("SELF-TEST-FAIL: missing evidence URI was not detected", file=sys.stderr)
            return 1

        # 5. Tampered evidence digest must fail
        gov.joinpath("standard-adoption.json").write_bytes(adoption_src.read_bytes())
        data = load(gov / "standard-adoption.json")
        data["adoptions"][0]["evidence"][0]["sha256"] = "0" * 64
        gov.joinpath("standard-adoption.json").write_text(json.dumps(data), encoding="utf-8")
        res = findings(tmp)
        if not any(r.get("code") == "ADOPTION-EVIDENCE-DRIFT" for r in res):
            print("SELF-TEST-FAIL: tampered evidence digest was not detected", file=sys.stderr)
            return 1

    print("check_adoption_records: self-test PASS (5 cases verified)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--self-test", action="store_true", help="Run internal integrity self-tests")
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_tests(args.root.resolve())
    rows = findings(args.root.resolve())
    if args.format == "json":
        print(json.dumps({"schema": SCHEMA, "ok": not rows, "findings": rows}, indent=2))
    else:
        for row in rows:
            print(f"{row['code']}: {row.get('pack', '')} {row.get('detail', '')}".strip())
        print("adoption-integrity: " + ("PASS" if not rows else f"{len(rows)} finding(s)"))
    return 0 if not rows else 1


if __name__ == "__main__":
    sys.exit(main())
