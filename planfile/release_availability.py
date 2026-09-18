#!/usr/bin/env python3
"""Check that Planfile source and runtime release metadata are publishable."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def version_key(value: str) -> tuple[int, int, int]:
    match = VERSION.fullmatch(value)
    if not match:
        raise ValueError(f"unsupported version: {value}")
    return tuple(int(part) for part in match.groups())


def published_info(url: str) -> dict[str, str]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        info = json.load(response).get("info", {})
    return {"version": str(info.get("version", "")), "python_requires": str(info.get("requires_python", ""))}


def check(root: Path, *, offline: bool = False) -> dict[str, object]:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10 uses the locked tomli dependency.
        import tomli as tomllib

    project = tomllib.loads((root / "pyproject.toml").read_text())
    metadata = json.loads((root / "planfile/release-metadata.json").read_text())
    source_version = str(project["project"]["version"])
    runtime = metadata["runtime"]
    declared_published = metadata["published"]
    observed = (
        {"version": str(declared_published["version"]), "python_requires": str(declared_published["python_requires"])}
        if offline
        else published_info(str(declared_published["index"]))
    )
    errors: list[str] = []
    if source_version != str(metadata["source"]["version"]):
        errors.append("source metadata does not match pyproject")
    if str(runtime["version"]) != source_version:
        errors.append("runtime version does not match source version")
    if version_key(source_version) > version_key(observed["version"]):
        errors.append(f"source version {source_version} is newer than published {observed['version']}")
    if str(project["project"].get("requires-python")) != str(runtime["python_requires"]):
        errors.append("runtime python_requires does not match pyproject")
    if str(runtime["python_requires"]) != str(observed["python_requires"]):
        errors.append("published python_requires does not match runtime metadata")
    return {"package": metadata["package"], "source_version": source_version, "published_version": observed["version"], "python_requires": observed["python_requires"], "errors": errors, "ok": not errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        result = check(args.root, offline=args.offline)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "errors": [str(error)]}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
