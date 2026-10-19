"""Standard polyglot URI process invocation bridge (`uri('')` & `uri <address> + jsonl`).

Implements `wellmanifest/dockuri` `DOCK-URI-001` and `DOCK-LFC-001` inside `planfile.utils`
(foundation layer) so scripts and modules across languages can invoke, generate, modify,
and relocate `dockuri` URI processes without duplicating helper logic.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import yaml

from planfile.utils.repository import normalize_repository
from planfile.utils.yaml_cache import read_yaml_file

_CUSTOM_URI_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def _coerce_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none"):
        return None
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)
    if (value.startswith("{") and value.endswith("}")) or (value.startswith("[") and value.endswith("]")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _split_uri_and_query(address: str) -> tuple[str, dict[str, Any]]:
    raw = (address or "").strip()
    if not raw:
        raise ValueError("URI address must not be empty")
    parts = urlsplit(raw)
    if not parts.scheme:
        raise ValueError(f"Invalid URI (missing scheme): {raw}")
    query_params: dict[str, Any] = {}
    if parts.query:
        for k, v in parse_qsl(parts.query, keep_blank_values=True):
            coerced = _coerce_scalar(v)
            if k in query_params:
                existing = query_params[k]
                query_params[k] = existing + [coerced] if isinstance(existing, list) else [existing, coerced]
            else:
                query_params[k] = coerced
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")), query_params


def register_uri_process(uri_str: str, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    """Register an in-process callable under a canonical URI (`DOCK-URI-001`)."""
    base_uri, _ = _split_uri_and_query(uri_str)
    _CUSTOM_URI_HANDLERS[base_uri] = handler


def parse_jsonl_payload(payload: Any) -> tuple[list[dict[str, Any]], bool]:
    """Parse payload into a list of parameter dicts and a flag indicating batch/JSONL mode."""
    if payload is None:
        return [{}], False
    if isinstance(payload, dict):
        return [dict(payload)], False
    if isinstance(payload, Path):
        return parse_jsonl_payload(payload.read_text(encoding="utf-8") if payload.exists() else "")
    if isinstance(payload, (list, tuple)):
        items: list[dict[str, Any]] = []
        for elem in payload:
            if isinstance(elem, dict):
                items.append(dict(elem))
            elif isinstance(elem, str) and elem.strip():
                parsed = json.loads(elem)
                items.append(parsed if isinstance(parsed, dict) else {"value": parsed})
        return (items or [{}]), True
    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return [{}], False
        if stripped.startswith("@") and len(stripped) > 1:
            file_path = Path(stripped[1:]).expanduser()
            if file_path.is_file():
                return parse_jsonl_payload(file_path.read_text(encoding="utf-8"))
        lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
        if len(lines) == 1:
            parsed = json.loads(lines[0])
            if isinstance(parsed, dict):
                return [parsed], False
            if isinstance(parsed, list):
                return [x if isinstance(x, dict) else {"value": x} for x in parsed], True
            return [{"value": parsed}], False
        return [(p if isinstance(p, dict) else {"value": p}) for p in (json.loads(ln) for ln in lines)], True
    raise TypeError(f"Unsupported URI payload type: {type(payload)!r}")


def render_uri_call_snippet(
    target_uri: str,
    default_params: dict[str, Any] | None = None,
    lang: str = "python",
) -> str:
    """Render a minimal cross-language wrapper snippet calling `uri('<uri>', ...)` (`DOCK-URI-001`)."""
    sample = json.dumps(default_params or {}, ensure_ascii=False)
    norm_lang = lang.strip().lower()
    if norm_lang in ("sh", "bash", "shell"):
        return f"#!/usr/bin/env bash\nset -euo pipefail\nexec uri {json.dumps(target_uri)} \"${{1:-{sample}}}\"\n"
    if norm_lang in ("js", "javascript", "node", "ts", "typescript"):
        return (
            "import { execFileSync } from 'node:child_process';\n"
            f"export const callUri = (payload = {sample}) =>\n"
            f"  JSON.parse(execFileSync('uri', [{json.dumps(target_uri)}, JSON.stringify(payload)], {{ encoding: 'utf8' }}));\n"
        )
    if norm_lang in ("rs", "rust"):
        return (
            "use std::process::Command;\n"
            "pub fn uri(address: &str, jsonl_payload: &str) -> Result<String, String> {\n"
            "    let out = Command::new(\"uri\").arg(address).arg(jsonl_payload).output().map_err(|e| e.to_string())?;\n"
            "    String::from_utf8(out.stdout).map_err(|e| e.to_string())\n"
            "}\n"
            f"// Example: uri({json.dumps(target_uri)}, {json.dumps(sample)})\n"
        )
    if norm_lang in ("go", "golang"):
        return (
            "package uribridge\n\nimport \"os/exec\"\n\n"
            "func Uri(address string, jsonl string) ([]byte, error) {\n"
            "    return exec.Command(\"uri\", address, jsonl).Output()\n"
            "}\n"
            f"// Example: Uri({json.dumps(target_uri)}, {json.dumps(sample)})\n"
        )
    if norm_lang == "php":
        return (
            "<?php\n"
            f"function uri(string $address = {json.dumps(target_uri)}, array $payload = []): array {{\n"
            "    $cmd = sprintf('uri %s %s', escapeshellarg($address), escapeshellarg(json_encode($payload)));\n"
            "    return json_decode((string) shell_exec($cmd), true) ?? [];\n"
            "}\n"
        )
    return (
        "from planfile.utils.uri import uri\n\n"
        f"def invoke(payload: dict | str | None = None):\n"
        f"    return uri({target_uri!r}, payload or {sample})\n"
    )


def _handle_repo_normalize(params: dict[str, Any]) -> dict[str, Any]:
    raw = params.get("repository") or params.get("repo") or params.get("value")
    try:
        normalized = normalize_repository(str(raw) if raw is not None else None)
        return {"status": "ok", "service": "proc://planfile/repo/normalize/v1", "repository": normalized}
    except ValueError as exc:
        return {"status": "error", "service": "proc://planfile/repo/normalize/v1", "error": str(exc)}


def _handle_yaml_read(params: dict[str, Any]) -> dict[str, Any]:
    raw_path = params.get("path") or params.get("value")
    if not raw_path:
        return {"status": "error", "service": "proc://planfile/yaml/read/v1", "error": "path is required"}
    data = read_yaml_file(Path(str(raw_path)).expanduser())
    return {"status": "ok", "service": "proc://planfile/yaml/read/v1", "data": data}


def _load_proc_manifest(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {"version": "dockuri/proc-v2", "processes": []}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
            if not isinstance(data.get("processes"), list):
                data["processes"] = []
    return data


def _handle_process_manage(params: dict[str, Any]) -> dict[str, Any]:
    """Fallback handler for `proc://system/process/manage/v1` (`DOCK-LFC-001`)."""
    action = str(params.get("action") or "generate").strip().lower()
    target_uri = str(params.get("target_uri") or params.get("uri") or "").strip()
    manifest_path = Path(str(params.get("manifest") or "dockuri.yaml")).expanduser()

    if action == "snippet":
        if not target_uri:
            return {"status": "error", "error": "target_uri is required for action=snippet"}
        lang = str(params.get("lang") or "python")
        return {
            "status": "ok",
            "service": "proc://system/process/manage/v1",
            "action": "snippet",
            "target_uri": target_uri,
            "lang": lang,
            "snippet": render_uri_call_snippet(target_uri, params.get("defaults"), lang=lang),
        }
    if not target_uri:
        return {"status": "error", "error": "target_uri is required"}

    data = _load_proc_manifest(manifest_path)
    processes: list[dict[str, Any]] = data["processes"]

    if action in ("generate", "upsert", "modify"):
        run_cmd = params.get("run") or ["echo", f"Executed {target_uri}"]
        entry: dict[str, Any] = {
            "uri": target_uri,
            "name": str(params.get("name") or target_uri.split("://")[-1].replace("/", "-")),
            "description": str(params.get("description") or f"Managed URI process {target_uri}"),
            "trigger": str(params.get("trigger") or "manual"),
            "run": [run_cmd] if isinstance(run_cmd, str) else list(run_cmd),
        }
        if params.get("cwd"):
            entry["cwd"] = str(params["cwd"])
        if isinstance(params.get("env"), dict):
            entry["env"] = {str(k): str(v) for k, v in params["env"].items()}

        updated = False
        for idx, existing in enumerate(processes):
            if isinstance(existing, dict) and existing.get("uri") == target_uri:
                processes[idx] = {**existing, **entry}
                updated = True
                break
        if not updated:
            processes.append(entry)

        if not params.get("dry_run", False):
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        digest = hashlib.sha256(json.dumps(entry, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return {
            "status": "ok",
            "service": "proc://system/process/manage/v1",
            "action": "modified" if updated else "generated",
            "manifest": str(manifest_path),
            "process": entry,
            "call_snippets": {
                "python": render_uri_call_snippet(target_uri, lang="python"),
                "bash": render_uri_call_snippet(target_uri, lang="bash"),
            },
            "receipt_urn": f"urn:dockuri:receipt:process-manage:{'modified' if updated else 'generated'}:{digest}",
        }

    if action in ("relocate", "move", "rename"):
        new_uri = str(params.get("new_uri") or target_uri).strip()
        dest_manifest = Path(str(params["dest_manifest"])).expanduser() if params.get("dest_manifest") else manifest_path
        found: dict[str, Any] | None = None
        remaining: list[dict[str, Any]] = []
        for existing in processes:
            if isinstance(existing, dict) and existing.get("uri") == target_uri and found is None:
                found = dict(existing)
            else:
                remaining.append(existing)
        if found is None:
            return {"status": "error", "error": f"URI process not found: {target_uri}"}
        found["uri"] = new_uri
        if params.get("new_name"):
            found["name"] = str(params["new_name"])

        if dest_manifest.resolve() == manifest_path.resolve():
            data["processes"] = remaining + [found]
            if not params.get("dry_run", False):
                manifest_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        else:
            data["processes"] = remaining
            dest_data = _load_proc_manifest(dest_manifest)
            dest_data["processes"] = [
                p for p in dest_data["processes"] if not (isinstance(p, dict) and p.get("uri") == new_uri)
            ] + [found]
            if not params.get("dry_run", False):
                manifest_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
                dest_manifest.parent.mkdir(parents=True, exist_ok=True)
                dest_manifest.write_text(yaml.safe_dump(dest_data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        digest = hashlib.sha256(json.dumps(found, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return {
            "status": "ok",
            "service": "proc://system/process/manage/v1",
            "action": "relocated",
            "old_uri": target_uri,
            "new_uri": new_uri,
            "source_manifest": str(manifest_path),
            "dest_manifest": str(dest_manifest),
            "process": found,
            "receipt_urn": f"urn:dockuri:receipt:process-manage:relocated:{digest}",
        }

    return {"status": "error", "error": f"Unsupported action: {action}"}


_BUILTIN_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "proc://planfile/repo/normalize/v1": _handle_repo_normalize,
    "proc://planfile/yaml/read/v1": _handle_yaml_read,
}

_PROCESS_MANAGE_URIS = {
    "proc://system/process/manage/v1",
    "proc://system/process/generate/v1",
    "proc://system/process/relocate/v1",
}


def _invoke_single(clean_uri: str, params: dict[str, Any], base_dir: Path | None = None) -> dict[str, Any]:
    if clean_uri in _CUSTOM_URI_HANDLERS:
        return _CUSTOM_URI_HANDLERS[clean_uri](params)
    if clean_uri in _BUILTIN_HANDLERS:
        return _BUILTIN_HANDLERS[clean_uri](params)

    try:
        import dockuri_uri as _dockuri_runtime  # type: ignore

        res = _dockuri_runtime.uri(clean_uri, params, base_dir=base_dir)
        return res if isinstance(res, dict) else {"status": "ok", "results": res}
    except ImportError:
        pass

    if clean_uri in _PROCESS_MANAGE_URIS:
        return _handle_process_manage(params)

    uri_bin = shutil.which("uri") or shutil.which("dockuri")
    if uri_bin and not os.environ.get("PLANFILE_DISABLE_URI_SUBPROCESS"):
        cmd = [uri_bin, clean_uri] if os.path.basename(uri_bin) == "uri" else [uri_bin, "uri", clean_uri]
        proc = subprocess.run(
            cmd,
            input=json.dumps(params, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
        )
        out = proc.stdout.strip()
        if out:
            lines = [ln for ln in out.splitlines() if ln.strip()]
            return json.loads(lines[-1])
        return {"status": "error", "error": proc.stderr.strip() or f"Exit {proc.returncode}"}

    return {"status": "error", "uri": clean_uri, "error": f"No handler or dockuri runtime found for {clean_uri}"}


def uri(address: str, payload: Any = None, *, base_dir: Path | None = None, **kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
    """Standard `uri('<full-uri>', [payload])` function for cross-project URI execution (`DOCK-URI-001`)."""
    clean_uri, query_params = _split_uri_and_query(address)
    records, is_batch = parse_jsonl_payload(payload)
    results = [_invoke_single(clean_uri, {**query_params, **rec, **kwargs}, base_dir=base_dir) for rec in records]
    return results if is_batch else results[0]


def uri_jsonl(
    address: str,
    lines: Iterable[str | dict[str, Any]],
    *,
    base_dir: Path | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Invoke a URI process over a stream of JSONL lines or dicts and return list of results (`DOCK-URI-001`)."""
    clean_uri, query_params = _split_uri_and_query(address)
    outputs: list[dict[str, Any]] = []
    for item in lines:
        if isinstance(item, str):
            stripped = item.strip()
            if not stripped:
                continue
            parsed = json.loads(stripped)
            record = parsed if isinstance(parsed, dict) else {"value": parsed}
        elif isinstance(item, dict):
            record = dict(item)
        else:
            record = {"value": item}
        outputs.append(_invoke_single(clean_uri, {**query_params, **record, **kwargs}, base_dir=base_dir))
    return outputs


def manage_uri_process(action: str, target_uri: str, **kwargs: Any) -> dict[str, Any]:
    """Generate, modify, relocate, or render snippets for a `dockuri` URI process (`DOCK-LFC-001`)."""
    res = uri("proc://system/process/manage/v1", {"action": action, "target_uri": target_uri, **kwargs})
    return res if isinstance(res, dict) else {"status": "ok", "results": res}


def uri_main(argv: list[str] | None = None) -> int:
    """CLI entrypoint (`python3 -m planfile.utils.uri <full-uri> [jsonl_or_json ...]`)."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print(
            "Usage: uri <scheme://authority/path[?k=v]> [json_or_jsonl_payload | @file.jsonl | -]\n"
            "       echo '{\"k\":\"v\"}' | uri <scheme://authority/path>\n"
            "       uri --snippet <lang> <scheme://authority/path>"
        )
        return 0
    if args[0] == "--snippet" and len(args) >= 3:
        print(render_uri_call_snippet(args[2], lang=args[1]), end="")
        return 0

    address, rest = args[0], args[1:]
    payload: Any = None
    if rest:
        payload = sys.stdin.read() if (len(rest) == 1 and rest[0] == "-") else (rest[0] if len(rest) == 1 else "\n".join(rest))
    elif not sys.stdin.isatty():
        stdin_data = sys.stdin.read().strip()
        if stdin_data:
            payload = stdin_data

    result = uri(address, payload)
    if isinstance(result, list):
        for item in result:
            print(json.dumps(item, ensure_ascii=False))
        return 0 if all(r.get("status") != "error" for r in result if isinstance(r, dict)) else 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if (isinstance(result, dict) and result.get("status") != "error") else 1


if __name__ == "__main__":
    raise SystemExit(uri_main())
