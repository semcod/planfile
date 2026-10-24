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
    adoption = load(adoption_path)
    catalog = load(catalog_path)
    records = {
        record["id"]: record
        for record in adoption.get("adoptions") or []
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    profile_name = adoption.get("profile", "")
    profile = (catalog.get("profiles") or {}).get(profile_name) or {}
    for requirement in profile.get("requirements") or []:
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
        evidence_levels = {
            item.get("level") for item in record.get("evidence") or []
            if isinstance(item, dict) and isinstance(item.get("sha256"), str)
        }
        for index in range(LEVELS[level] + 1):
            if f"S{index}" not in evidence_levels:
                rows.append({"code": "ADOPTION-EVIDENCE", "pack": pack_id,
                             "detail": f"lacks S{index} evidence"})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
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
