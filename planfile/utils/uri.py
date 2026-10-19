"""Standard polyglot URI process invocation bridge (`uri('')` & `uri <address> + jsonl`).

Implements `wellmanifest/dockuri` `DOCK-URI-001` and `DOCK-LFC-001` inside `planfile.utils`
(foundation layer) so scripts, modules, and LLM agents across languages can invoke, generate,
modify, and relocate `dockuri` and `urirun` URI processes without duplicating helper logic.
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

_SNIPPET_TEMPLATES: dict[str, str] = {
    "bash": "#!/usr/bin/env bash\nset -euo pipefail\nexec uri {uri_q} \"${{1:-{sample}}}\"\n",
    "js": (
        "import {{ execFileSync }} from 'node:child_process';\n"
        "export const callUri = (payload = {sample}) =>\n"
        "  JSON.parse(execFileSync('uri', [{uri_q}, JSON.stringify(payload)], {{ encoding: 'utf8' }}));\n"
    ),
    "rust": (
        "use std::process::Command;\n"
        "pub fn uri(address: &str, jsonl_payload: &str) -> Result<String, String> {{\n"
        "    let out = Command::new(\"uri\").arg(address).arg(jsonl_payload).output().map_err(|e| e.to_string())?;\n"
        "    String::from_utf8(out.stdout).map_err(|e| e.to_string())\n"
        "}}\n"
        "// Example: uri({uri_q}, {sample_q})\n"
    ),
    "go": (
        "package uribridge\n\nimport \"os/exec\"\n\n"
        "func Uri(address string, jsonl string) ([]byte, error) {{\n"
        "    return exec.Command(\"uri\", address, jsonl).Output()\n"
        "}}\n"
        "// Example: Uri({uri_q}, {sample_q})\n"
    ),
    "php": (
        "<?php\n"
        "function uri(string $address = {uri_q}, array $payload = []): array {{\n"
        "    $cmd = sprintf('uri %s %s', escapeshellarg($address), escapeshellarg(json_encode($payload)));\n"
        "    return json_decode((string) shell_exec($cmd), true) ?? [];\n"
        "}}\n"
    ),
    "python": (
        "from planfile.utils.uri import uri\n\n"
        "def invoke(payload: dict | str | None = None):\n"
        "    return uri({uri_r}, payload or {sample})\n"
    ),
}

_LANG_ALIASES: dict[str, str] = {
    "sh": "bash",
    "bash": "bash",
    "shell": "bash",
    "js": "js",
    "javascript": "js",
    "node": "js",
    "ts": "js",
    "typescript": "js",
    "rs": "rust",
    "rust": "rust",
    "go": "go",
    "golang": "go",
    "php": "php",
}

_PRIORITY_RANK: dict[str, int] = {
    "p0": 0,
    "critical": 0,
    "p1": 1,
    "high": 1,
    "p2": 2,
    "normal": 2,
    "medium": 2,
    "p3": 3,
    "low": 3,
}


def _coerce_json_or_str(value: str) -> Any:
    if (value.startswith("{") and value.endswith("}")) or (value.startswith("[") and value.endswith("]")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _coerce_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none"):
        return None
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)
    return _coerce_json_or_str(value)


def _merge_query_param(query_params: dict[str, Any], key: str, coerced: Any) -> None:
    if key not in query_params:
        query_params[key] = coerced
        return
    existing = query_params[key]
    query_params[key] = existing + [coerced] if isinstance(existing, list) else [existing, coerced]


def _split_uri_and_query(address: str) -> tuple[str, dict[str, Any]]:
    raw = (address or "").strip()
    if not raw:
        raise ValueError("URI address must not be empty")
    parts = urlsplit(raw)
    if not parts.scheme:
        raise ValueError(f"Invalid URI (missing scheme): {raw}")
    query_params: dict[str, Any] = {}
    for k, v in parse_qsl(parts.query, keep_blank_values=True):
        _merge_query_param(query_params, k, _coerce_scalar(v))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")), query_params


def register_uri_process(uri_str: str, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    """Register an in-process callable under a canonical URI (`DOCK-URI-001`)."""
    base_uri, _ = _split_uri_and_query(uri_str)
    _CUSTOM_URI_HANDLERS[base_uri] = handler


def _to_record_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {"value": value}


def _parse_sequence_payload(seq: list[Any] | tuple[Any, ...]) -> tuple[list[dict[str, Any]], bool]:
    items: list[dict[str, Any]] = []
    for elem in seq:
        if isinstance(elem, dict):
            items.append(dict(elem))
        elif isinstance(elem, str) and elem.strip():
            items.append(_to_record_dict(json.loads(elem)))
    return (items or [{}]), True


def _parse_string_payload(raw: str) -> tuple[list[dict[str, Any]], bool]:
    stripped = raw.strip()
    if not stripped:
        return [{}], False
    if stripped.startswith("@") and len(stripped) > 1:
        file_path = Path(stripped[1:]).expanduser()
        if file_path.is_file():
            return _parse_string_payload(file_path.read_text(encoding="utf-8"))
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    if len(lines) == 1:
        parsed = json.loads(lines[0])
        if isinstance(parsed, list):
            return [_to_record_dict(x) for x in parsed], True
        return [_to_record_dict(parsed)], False
    return [_to_record_dict(json.loads(ln)) for ln in lines], True


def parse_jsonl_payload(payload: Any) -> tuple[list[dict[str, Any]], bool]:
    """Parse payload into a list of parameter dicts and a flag indicating batch/JSONL mode."""
    if payload is None:
        return [{}], False
    if isinstance(payload, dict):
        return [dict(payload)], False
    if isinstance(payload, Path):
        return _parse_string_payload(payload.read_text(encoding="utf-8") if payload.exists() else "")
    if isinstance(payload, (list, tuple)):
        return _parse_sequence_payload(payload)
    if isinstance(payload, str):
        return _parse_string_payload(payload)
    raise TypeError(f"Unsupported URI payload type: {type(payload)!r}")


def render_uri_call_snippet(
    target_uri: str,
    default_params: dict[str, Any] | None = None,
    lang: str = "python",
) -> str:
    """Render a minimal cross-language wrapper snippet calling `uri('<uri>', ...)` (`DOCK-URI-001`)."""
    sample = json.dumps(default_params or {}, ensure_ascii=False)
    key = _LANG_ALIASES.get(lang.strip().lower(), "python")
    return _SNIPPET_TEMPLATES[key].format(
        uri_q=json.dumps(target_uri),
        uri_r=repr(target_uri),
        sample=sample,
        sample_q=json.dumps(sample),
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


def _normalize_ticket_entry(t: dict[str, Any], tid: str | None = None) -> dict[str, Any]:
    out = dict(t)
    if tid is not None:
        out["id"] = str(tid)
    out["name"] = out.get("name") or out.get("title") or ""
    return out


def _load_sprint_tickets(project: str | Path, sprint: str = "current") -> tuple[Path, list[dict[str, Any]]]:
    root = Path(project or ".").expanduser().resolve()
    sprint_file = root / ".planfile" / "sprints" / f"{sprint}.yaml"
    data = (read_yaml_file(sprint_file) if sprint_file.is_file() else None) or {}
    if not isinstance(data, dict):
        return root, []
    sprint_obj = data.get("sprint")
    if isinstance(sprint_obj, dict) and isinstance(sprint_obj.get("tickets"), dict):
        return root, [_normalize_ticket_entry(t, tid) for tid, t in sprint_obj["tickets"].items() if isinstance(t, dict)]
    tasks = data.get("tasks")
    if isinstance(tasks, list):
        return root, [_normalize_ticket_entry(t) for t in tasks if isinstance(t, dict)]
    return root, []


def _handle_tickets_list(params: dict[str, Any]) -> dict[str, Any]:
    root, tickets = _load_sprint_tickets(params.get("project", "."), str(params.get("sprint") or "current"))
    status = str(params.get("status") or "").strip().lower()
    if status and status != "all":
        tickets = [t for t in tickets if str(t.get("status") or "").lower() == status]
    priority = str(params.get("priority") or "").strip().lower()
    if priority:
        tickets = [t for t in tickets if str(t.get("priority") or "").lower() == priority]
    return {"ok": True, "status": "ok", "connector": "planfile", "project": str(root), "tickets": tickets}


def _handle_ticket_next(params: dict[str, Any]) -> dict[str, Any]:
    root, tickets = _load_sprint_tickets(params.get("project", "."), str(params.get("sprint") or "current"))
    done_ids = {str(t.get("id")) for t in tickets if str(t.get("status") or "").lower() in ("done", "closed", "canceled")}
    runnable = [
        t
        for t in tickets
        if str(t.get("status") or "").lower() in ("open", "todo", "ready")
        and all(str(b) in done_ids for b in (t.get("blocked_by") or []))
    ]
    runnable.sort(key=lambda t: (_PRIORITY_RANK.get(str(t.get("priority") or "normal").lower(), 2), str(t.get("id") or "")))
    return {"ok": True, "status": "ok", "connector": "planfile", "project": str(root), "ticket": runnable[0] if runnable else None}


def _handle_ticket_show(params: dict[str, Any]) -> dict[str, Any]:
    tid = str(params.get("ticket_id") or params.get("id") or "").strip()
    if not tid:
        return {"ok": False, "status": "error", "error": "ticket_id is required"}
    root, tickets = _load_sprint_tickets(params.get("project", "."), str(params.get("sprint") or "current"))
    found = next((t for t in tickets if str(t.get("id")) == tid), None)
    return {"ok": found is not None, "status": "ok" if found else "error", "project": str(root), "ticket": found}


def _load_proc_manifest(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {"version": "dockuri/proc-v2", "processes": []}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
            if not isinstance(data.get("processes"), list):
                data["processes"] = []
    return data


def _save_yaml(path: Path, data: dict[str, Any], dry_run: bool) -> None:
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _build_process_entry(target_uri: str, params: dict[str, Any]) -> dict[str, Any]:
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
    return entry


def _upsert_process(target_uri: str, manifest_path: Path, params: dict[str, Any]) -> dict[str, Any]:
    data = _load_proc_manifest(manifest_path)
    processes: list[dict[str, Any]] = data["processes"]
    entry = _build_process_entry(target_uri, params)
    existing_idx = next(
        (i for i, p in enumerate(processes) if isinstance(p, dict) and p.get("uri") == target_uri),
        None,
    )
    if existing_idx is not None:
        processes[existing_idx] = {**processes[existing_idx], **entry}
        act = "modified"
    else:
        processes.append(entry)
        act = "generated"
    _save_yaml(manifest_path, data, bool(params.get("dry_run", False)))
    digest = hashlib.sha256(json.dumps(entry, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return {
        "status": "ok",
        "service": "proc://system/process/manage/v1",
        "action": act,
        "manifest": str(manifest_path),
        "process": entry,
        "call_snippets": {
            "python": render_uri_call_snippet(target_uri, lang="python"),
            "bash": render_uri_call_snippet(target_uri, lang="bash"),
        },
        "receipt_urn": f"urn:dockuri:receipt:process-manage:{act}:{digest}",
    }


def _relocate_process(target_uri: str, manifest_path: Path, params: dict[str, Any]) -> dict[str, Any]:
    data = _load_proc_manifest(manifest_path)
    processes: list[dict[str, Any]] = data["processes"]
    found = next((dict(p) for p in processes if isinstance(p, dict) and p.get("uri") == target_uri), None)
    if found is None:
        return {"status": "error", "error": f"URI process not found: {target_uri}"}
    remaining = [p for p in processes if not (isinstance(p, dict) and p.get("uri") == target_uri)]
    new_uri = str(params.get("new_uri") or target_uri).strip()
    found["uri"] = new_uri
    if params.get("new_name"):
        found["name"] = str(params["new_name"])

    dest_manifest = Path(str(params["dest_manifest"])).expanduser() if params.get("dest_manifest") else manifest_path
    dry_run = bool(params.get("dry_run", False))
    if dest_manifest.resolve() == manifest_path.resolve():
        data["processes"] = remaining + [found]
        _save_yaml(manifest_path, data, dry_run)
    else:
        data["processes"] = remaining
        dest_data = _load_proc_manifest(dest_manifest)
        dest_data["processes"] = [
            p for p in dest_data["processes"] if not (isinstance(p, dict) and p.get("uri") == new_uri)
        ] + [found]
        _save_yaml(manifest_path, data, dry_run)
        _save_yaml(dest_manifest, dest_data, dry_run)
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


def _handle_process_manage(params: dict[str, Any]) -> dict[str, Any]:
    """Handler for `proc://system/process/manage/v1` (`DOCK-LFC-001`)."""
    action = str(params.get("action") or "generate").strip().lower()
    target_uri = str(params.get("target_uri") or params.get("uri") or "").strip()
    if not target_uri:
        return {"status": "error", "error": "target_uri is required"}
    if action == "snippet":
        lang = str(params.get("lang") or "python")
        return {
            "status": "ok",
            "service": "proc://system/process/manage/v1",
            "action": "snippet",
            "target_uri": target_uri,
            "lang": lang,
            "snippet": render_uri_call_snippet(target_uri, params.get("defaults"), lang=lang),
        }
    manifest_path = Path(str(params.get("manifest") or "dockuri.yaml")).expanduser()
    if action in ("generate", "upsert", "modify"):
        return _upsert_process(target_uri, manifest_path, params)
    if action in ("relocate", "move", "rename"):
        return _relocate_process(target_uri, manifest_path, params)
    return {"status": "error", "error": f"Unsupported action: {action}"}


_BUILTIN_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "proc://planfile/repo/normalize/v1": _handle_repo_normalize,
    "proc://planfile/yaml/read/v1": _handle_yaml_read,
    "proc://planfile/tickets/list/v1": _handle_tickets_list,
    "task://host/tickets/query/list": _handle_tickets_list,
    "proc://planfile/ticket/next/v1": _handle_ticket_next,
    "task://host/ticket/query/next": _handle_ticket_next,
    "proc://planfile/ticket/show/v1": _handle_ticket_show,
    "task://host/ticket/query/show": _handle_ticket_show,
}

_PROCESS_MANAGE_URIS = {
    "proc://system/process/manage/v1",
    "proc://system/process/generate/v1",
    "proc://system/process/relocate/v1",
}


def _invoke_subprocess_uri(clean_uri: str, params: dict[str, Any]) -> dict[str, Any] | None:
    uri_bin = shutil.which("uri") or shutil.which("dockuri")
    if not uri_bin or os.environ.get("PLANFILE_DISABLE_URI_SUBPROCESS"):
        return None
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
    sub_res = _invoke_subprocess_uri(clean_uri, params)
    if sub_res is not None:
        return sub_res
    return {"status": "error", "uri": clean_uri, "error": f"No handler or dockuri runtime found for {clean_uri}"}


def uri(address: str, payload: Any = None, *, base_dir: Path | None = None, **kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
    """Standard `uri('<full-uri>', [payload])` function for cross-project URI execution (`DOCK-URI-001`)."""
    clean_uri, query_params = _split_uri_and_query(address)
    records, is_batch = parse_jsonl_payload(payload)
    results = [_invoke_single(clean_uri, {**query_params, **rec, **kwargs}, base_dir=base_dir) for rec in records]
    return results if is_batch else results[0]


def _coerce_line_item(item: str | dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(item, dict):
        return dict(item)
    if isinstance(item, str):
        stripped = item.strip()
        return _to_record_dict(json.loads(stripped)) if stripped else None
    return {"value": item}


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
        record = _coerce_line_item(item)
        if record is not None:
            outputs.append(_invoke_single(clean_uri, {**query_params, **record, **kwargs}, base_dir=base_dir))
    return outputs


def manage_uri_process(action: str, target_uri: str, **kwargs: Any) -> dict[str, Any]:
    """Generate, modify, relocate, or render snippets for a `dockuri` URI process (`DOCK-LFC-001`)."""
    res = uri("proc://system/process/manage/v1", {"action": action, "target_uri": target_uri, **kwargs})
    return res if isinstance(res, dict) else {"status": "ok", "results": res}


def _resolve_cli_payload(rest: list[str]) -> Any:
    if rest:
        if len(rest) == 1 and rest[0] == "-":
            return sys.stdin.read()
        return rest[0] if len(rest) == 1 else "\n".join(rest)
    if not sys.stdin.isatty():
        stdin_data = sys.stdin.read().strip()
        return stdin_data or None
    return None


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

    result = uri(args[0], _resolve_cli_payload(args[1:]))
    if isinstance(result, list):
        for item in result:
            print(json.dumps(item, ensure_ascii=False))
        return 0 if all(r.get("status") != "error" for r in result if isinstance(r, dict)) else 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if (isinstance(result, dict) and result.get("status") != "error") else 1


if __name__ == "__main__":
    raise SystemExit(uri_main())
