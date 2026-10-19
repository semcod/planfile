"""Safe, typed configuration surface shared by every Planfile DSL entry point."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from planfile.core.operational_dsl import canonical_json, redact
from planfile.core.operational_dsl import line as operational_line
from planfile.runtime_context import (
    DEFAULT_CONFIG as DEFAULT_RUNTIME_CONFIG,
)
from planfile.runtime_context import (
    load_runtime_context_config,
    save_runtime_context_config,
)

from planfile.utils.yaml_cache import read_yaml_file as _read_yaml_file

if TYPE_CHECKING:
    from planfile import Planfile


_SENSITIVE_PATH = re.compile(
    r"(^|[._-])(authorization|cookie|credential|password|passwd|secret|token|"
    r"api[_-]?key|private[_-]?key)($|[._-])",
    re.I,
)
_PREFIX = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,15}$")
_TERMINAL_STATUSES = {"done", "blocked", "canceled", "failed"}
_SYNC_INTEGRATION_NAMES = {"github", "gitlab", "jira"}
_INTEGRATION_CONFIG_NAME = "integrations.oql.planfile.yaml"


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "on", "1"}:
            return True
        if normalized in {"false", "no", "off", "0"}:
            return False
    raise ValueError("config_value_boolean_required")


def _nonnegative_integer(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("config_value_integer_required")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("config_value_integer_required") from exc
    if normalized < 0:
        raise ValueError("config_value_must_be_nonnegative")
    return normalized


def _positive_integer(value: Any) -> int:
    normalized = _nonnegative_integer(value)
    if normalized < 1:
        raise ValueError("config_value_must_be_positive")
    return normalized


def _custom_shards(value: Any) -> int:
    normalized = _positive_integer(value)
    if normalized > 256:
        raise ValueError("config_custom_shards_maximum_256")
    return normalized


def _text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("config_value_text_required")
    normalized = value.strip()
    if not normalized:
        raise ValueError("config_value_text_required")
    return normalized


def _prefix(value: Any) -> str:
    normalized = _text(value).upper()
    if not _PREFIX.fullmatch(normalized):
        raise ValueError("config_prefix_invalid")
    return normalized


def _choice(*values: str) -> Callable[[Any], str]:
    allowed = set(values)

    def validate(value: Any) -> str:
        normalized = str(value).strip().lower()
        if normalized not in allowed:
            raise ValueError(f"config_value_invalid:{','.join(values)}")
        return normalized

    return validate


def _terminal_statuses(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [part.strip().lower() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        values = [str(part).strip().lower() for part in value]
    else:
        raise ValueError("config_terminal_statuses_list_required")
    normalized = list(dict.fromkeys(item for item in values if item))
    if not normalized:
        raise ValueError("config_terminal_statuses_required")
    invalid = sorted(set(normalized) - _TERMINAL_STATUSES)
    if invalid:
        raise ValueError(f"config_terminal_status_invalid:{invalid[0]}")
    return normalized


def _runtime_overrides(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("config_runtime_overrides_mapping_required")

    def validate(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                key_path = f"{path}.{key}".strip(".")
                if _SENSITIVE_PATH.search(str(key)):
                    raise ValueError(f"config_sensitive_path_forbidden:{key_path}")
                validate(item, key_path)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                validate(item, f"{path}.{index}")
        else:
            try:
                json.dumps(node, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise ValueError("config_value_not_json") from exc

    validate(value)
    return copy.deepcopy(value)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        raise ValueError("config_value_string_list_required")
    normalized = list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))
    if not normalized:
        raise ValueError("config_value_string_list_required")
    return normalized


def _identifier(value: Any) -> str | int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("config_value_identifier_required")
    if isinstance(value, str):
        return _text(value)
    if value < 0:
        raise ValueError("config_value_identifier_required")
    return value


def _url(value: Any) -> str:
    normalized = _text(value)
    if not re.match(r"^https?://[^/\s]+", normalized, re.I):
        raise ValueError("config_value_http_url_required")
    return normalized.rstrip("/")


@dataclass(frozen=True)
class Setting:
    validator: Callable[[Any], Any]
    source: str
    description: str


_CFG_SRC = ".planfile/config.yaml"
_RT_SRC = ".koru/runtime-context.json"
_INT_SRC = f".planfile/{_INTEGRATION_CONFIG_NAME}"

STORE_SETTINGS: dict[str, Setting] = {
    "store.project": Setting(_text, _CFG_SRC, "Project display name"),
    "store.prefix": Setting(_prefix, _CFG_SRC, "Prefix for newly allocated ticket IDs"),
    "store.archive.enabled": Setting(_boolean, _CFG_SRC, "Automatic archive switch"),
    "store.archive.max_current_tickets": Setting(_nonnegative_integer, _CFG_SRC, "Current-sprint ticket threshold; 0 disables it"),
    "store.archive.max_current_bytes": Setting(_nonnegative_integer, _CFG_SRC, "Current-sprint byte threshold; 0 disables it"),
    "store.archive.retain_terminal_tickets": Setting(_nonnegative_integer, _CFG_SRC, "Terminal tickets retained in current sprint"),
    "store.archive.retain_terminal_days": Setting(
        _nonnegative_integer, _CFG_SRC, "UTC calendar dates retained before terminal tickets move to daily history"
    ),
    "store.archive.terminal_statuses": Setting(_terminal_statuses, _CFG_SRC, "Statuses eligible for archiving"),
    "store.storage.backend": Setting(_choice("single-yaml", "sharded-yaml"), _CFG_SRC, "Physical ticket backend"),
    "store.storage.shard_size": Setting(_positive_integer, _CFG_SRC, "Sequential tickets per YAML shard"),
    "store.storage.custom_shards": Setting(_custom_shards, _CFG_SRC, "Hash buckets for custom ticket IDs"),
    "store.storage.index": Setting(_choice("none", "sqlite"), _CFG_SRC, "Rebuildable ticket query index"),
}

RUNTIME_ENABLED_SETTINGS: dict[str, Setting] = {
    f"runtime.enabled.{name}": Setting(_boolean, _RT_SRC, f"Include {name} in generated runtime context")
    for name in DEFAULT_RUNTIME_CONFIG["enabled"]
}
RUNTIME_SETTINGS: dict[str, Setting] = {
    **RUNTIME_ENABLED_SETTINGS,
    "runtime.overrides": Setting(_runtime_overrides, _RT_SRC, "Complete runtime context override mapping"),
}

INTEGRATION_SETTINGS: dict[str, Setting] = {
    "integrations.github.sync.enqueue_on_done": Setting(
        _boolean, _INT_SRC, "Queue completed GitHub tickets locally; an authorized retry worker delivers"
    ),
    "integrations.github.repo": Setting(_text, _INT_SRC, "GitHub owner/repository"),
    "integrations.github.default_labels": Setting(_string_list, _INT_SRC, "Default labels for GitHub issues"),
    "integrations.github.issue_template": Setting(_text, _INT_SRC, "GitHub issue body template"),
    "integrations.gitlab.url": Setting(_url, _INT_SRC, "GitLab HTTP(S) base URL"),
    "integrations.gitlab.project_id": Setting(_identifier, _INT_SRC, "GitLab project identifier"),
    "integrations.jira.url": Setting(_url, _INT_SRC, "Jira HTTP(S) base URL"),
    "integrations.jira.project": Setting(_text, _INT_SRC, "Jira project key"),
    "integrations.onedev.url": Setting(_url, _INT_SRC, "OneDev HTTP(S) base URL"),
    "integrations.onedev.project": Setting(_text, _INT_SRC, "OneDev project path"),
    "integrations.onedev.publish_to": Setting(_string_list, _INT_SRC, "OneDev publication targets"),
    "integrations.markdown.todo_file": Setting(_text, _INT_SRC, "Markdown TODO output path"),
    "integrations.markdown.changelog_file": Setting(_text, _INT_SRC, "Markdown changelog output path"),
    "integrations.markdown.sync_on_plan_run": Setting(_boolean, _INT_SRC, "Synchronize Markdown during a plan run"),
}


def _nested_get(data: dict[str, Any], parts: list[str]) -> Any:
    node: Any = data
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            raise ValueError("config_path_not_found")
        node = node[part]
    return node


def _nested_set(data: dict[str, Any], parts: list[str], value: Any) -> None:
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


class ConfigurationManager:
    """Expose an allowlisted configuration API without exposing secrets or state."""

    def __init__(self, planfile: Planfile):
        self.planfile = planfile
        self.store = planfile.store
        self.project_dir = self.store.project_dir

    @property
    def writable_paths(self) -> list[str]:
        return sorted(
            [
                *STORE_SETTINGS,
                *RUNTIME_SETTINGS,
                *INTEGRATION_SETTINGS,
                "runtime.overrides.<path>",
                "integrations.<github|gitlab|jira>.sync.<path>",
            ]
        )

    def _store_values(self) -> dict[str, Any]:
        raw = self.store._read_config()
        return {
            "project": raw.get("project", self.project_dir.name),
            "prefix": raw.get("prefix", "PLF"),
            "archive": {
                **self.store.DEFAULT_ARCHIVE_CONFIG,
                **((raw.get("archive") or {}) if isinstance(raw.get("archive"), dict) else {}),
            },
            "storage": self.store._storage_config(),
        }

    @property
    def _integration_config_path(self) -> Path:
        return self.store.base_dir / _INTEGRATION_CONFIG_NAME

    def _integration_paths(self) -> list[Path]:
        paths = []
        for directory in (self.project_dir, self.project_dir / ".planfile"):
            for pattern in ("*.planfile.yaml", "*.planfile.yml"):
                paths.extend(directory.glob(pattern))
        unique = set(paths)
        canonical = self._integration_config_path
        ordinary = sorted(
            path
            for path in unique
            if path != canonical and not path.name.startswith("tickets.")
        )
        tickets = sorted(path for path in unique if path.name.startswith("tickets."))
        return [*ordinary, *tickets, *([canonical] if canonical in unique else [])]

    def _integration_values(self) -> dict[str, Any]:
        # Read source files without dotenv expansion. Configuration inspection
        # must neither mutate the process environment nor materialize secrets.
        values: dict[str, Any] = {}
        for path in self._integration_paths():
            loaded = _read_yaml_file(path) or {}
            if isinstance(loaded, dict):
                self._deep_merge(values, loaded)
        integrations = values.get("integrations", {}) if isinstance(values, dict) else {}
        return redact(integrations if isinstance(integrations, dict) else {})

    @classmethod
    def _deep_merge(cls, base: dict[str, Any], update: dict[str, Any]) -> None:
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                cls._deep_merge(base[key], value)
            else:
                base[key] = value

    def revision(self) -> str:
        """Return a stable optimistic-lock revision without exposing secret values."""
        runtime = load_runtime_context_config(self.project_dir)
        runtime.pop("updated_at", None)
        integration_sources = []
        for path in self._integration_paths():
            try:
                document = _read_yaml_file(path) or {}
            except FileNotFoundError:
                continue
            integrations = (
                document.get("integrations", {})
                if isinstance(document, dict)
                else {}
            )
            if not integrations:
                continue
            integration_sources.append(
                {
                    "path": str(path.relative_to(self.project_dir)),
                    "sha256": hashlib.sha256(
                        canonical_json(integrations).encode()
                    ).hexdigest(),
                }
            )
        payload = {
            "store": self._store_values(),
            "runtime": runtime,
            "integration_sources": integration_sources,
        }
        return f"cfg_{hashlib.sha256(canonical_json(payload).encode()).hexdigest()[:24]}"

    def _check_revision(self, expected_revision: str | None) -> str:
        current = self.revision()
        if expected_revision and expected_revision != current:
            raise ValueError(f"config_revision_conflict:{current}")
        return current

    def list(self) -> dict[str, Any]:
        """Return effective values and the explicit safety contract."""
        return {
            "revision": self.revision(),
            "values": {
                "store": self._store_values(),
                "runtime": load_runtime_context_config(self.project_dir),
                "integrations": self._integration_values(),
            },
            "writable": self.writable_paths,
            "schema": {
                path: {
                    "source": setting.source,
                    "description": setting.description,
                }
                for path, setting in sorted(
                    {
                        **STORE_SETTINGS,
                        **RUNTIME_SETTINGS,
                        **INTEGRATION_SETTINGS,
                    }.items()
                )
            }
            | {
                "runtime.overrides.<path>": {
                    "source": ".koru/runtime-context.json",
                    "description": "Nested JSON runtime context override",
                },
                "integrations.<github|gitlab|jira>.sync.<path>": {
                    "source": f".planfile/{_INTEGRATION_CONFIG_NAME}",
                    "description": "Non-secret integration synchronization setting",
                },
            },
            "read_only": {
                "integrations.* credentials": (
                    "merged from *.planfile.yaml; secret-like fields are redacted "
                    "and never writable through OQL"
                ),
                "environment.*": "process-owned PLANFILE_* and provider variables",
            },
            "excluded": {
                "store.next_id": "allocator-owned; direct writes could create duplicate IDs",
                "sync.*": "runtime state, not configuration",
                "leases.*": "coordination state, not configuration",
                "evidence.*": "append-only execution evidence, not configuration",
            },
        }

    def show(self, path: str | None = None) -> dict[str, Any]:
        """Show one redacted value, or the full configuration contract."""
        if not path:
            return self.list()
        normalized = self._normalize_path(path)
        listing = self.list()
        try:
            value = _nested_get(listing["values"], normalized.split("."))
        except ValueError:
            if normalized.startswith("runtime.overrides."):
                return {
                    "path": normalized,
                    "value": None,
                    "writable": True,
                    "revision": listing["revision"],
                }
            if normalized in listing["excluded"]:
                return {
                    "path": normalized,
                    "value": None,
                    "writable": False,
                    "reason": listing["excluded"][normalized],
                    "revision": listing["revision"],
                }
            if self._is_integration_writable(normalized):
                return {
                    "path": normalized,
                    "value": None,
                    "writable": True,
                    "revision": listing["revision"],
                }
            raise
        writable = (
            normalized in STORE_SETTINGS
            or normalized in RUNTIME_SETTINGS
            or self._is_integration_writable(normalized)
        )
        if normalized.startswith("runtime.overrides."):
            writable = True
        return {
            "path": normalized,
            "value": redact(value, normalized.rsplit(".", 1)[-1]),
            "writable": writable,
            "revision": listing["revision"],
        }

    @staticmethod
    def _normalize_path(path: str) -> str:
        normalized = str(path or "").strip().strip(".")
        if normalized.startswith("config."):
            normalized = normalized[7:]
        if not normalized:
            raise ValueError("config_path_required")
        return normalized

    def _setting(self, path: str) -> Setting:
        static_setting = STORE_SETTINGS.get(path) or RUNTIME_SETTINGS.get(path) or INTEGRATION_SETTINGS.get(path)
        if static_setting is not None:
            return static_setting
        if path.startswith("runtime.overrides."):
            return self._override_setting(path)
        if path == "store.next_id":
            raise ValueError("config_path_allocator_owned")
        if path.startswith("integrations."):
            return self._integration_sync_setting(path)
        if path.startswith(("environment.", "sync.", "leases.", "evidence.")):
            raise ValueError("config_path_not_configuration")
        raise ValueError("config_path_not_writable")

    def _override_setting(self, path: str) -> Setting:
        override_path = path.removeprefix("runtime.overrides.")
        if not override_path:
            raise ValueError("config_override_path_required")
        if _SENSITIVE_PATH.search(override_path):
            raise ValueError("config_sensitive_path_forbidden")
        return Setting(self._json_value, _RT_SRC, "Runtime context override")

    def _integration_sync_setting(self, path: str) -> Setting:
        if _SENSITIVE_PATH.search(path):
            raise ValueError("config_sensitive_path_forbidden")
        if self._is_integration_sync_path(path):
            return Setting(self._json_value, _INT_SRC, "Integration synchronization setting")
        raise ValueError("config_integration_path_not_writable")

    @staticmethod
    def _is_integration_sync_path(path: str) -> bool:
        parts = path.split(".")
        return (
            len(parts) >= 4
            and parts[0] == "integrations"
            and parts[1] in _SYNC_INTEGRATION_NAMES
            and parts[2] == "sync"
            and not _SENSITIVE_PATH.search(".".join(parts[3:]))
        )

    @classmethod
    def _is_integration_writable(cls, path: str) -> bool:
        return path in INTEGRATION_SETTINGS or cls._is_integration_sync_path(path)

    @staticmethod
    def _json_value(value: Any) -> Any:
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("config_value_not_json") from exc
        return value

    def _normalize_changes(self, changes: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
        normalized: dict[str, Any] = {}
        for raw_path, value in changes.items():
            path = self._normalize_path(raw_path)
            if path in normalized:
                raise ValueError(f"config_path_duplicate:{path}")
            normalized[path] = self._setting(path).validator(value)
        scopes = {path.split(".", 1)[0] for path in normalized}
        if len(scopes) != 1:
            raise ValueError("config_mixed_scope_not_atomic")
        return normalized, scopes

    def _apply_scope_mutation(self, normalized: dict[str, Any], scopes: set[str], before_revision: str) -> dict[str, Any] | None:
        if "store.storage.backend" in normalized:
            return self._set_storage_backend(normalized, expected_revision=before_revision)
        if "store.storage.index" in normalized:
            return self.store.configure_ticket_index(
                normalized["store.storage.index"] == "sqlite",
                before_mutation=lambda: self._check_revision(before_revision),
            )
        if scopes == {"store"}:
            self._set_store_values(normalized, expected_revision=before_revision)
            return None
        if scopes == {"runtime"}:
            self._set_runtime_values(normalized, expected_revision=before_revision)
            return None
        return self._set_integration_values(normalized, expected_revision=before_revision)

    def set_many(
        self,
        changes: dict[str, Any],
        *,
        mode: str = "apply",
        actor: str = "dsl",
        reason: str = "",
        expected_revision: str | None = None,
    ) -> dict[str, Any]:
        """Validate and apply a same-scope batch, with migrations for physical changes."""
        if mode not in {"apply", "dry-run"}:
            raise ValueError("config_mode_must_be_apply_or_dry-run")
        if not changes:
            raise ValueError("config_changes_required")
        before_revision = self._check_revision(expected_revision)
        normalized, scopes = self._normalize_changes(changes)

        before = {path: self._current_value(path) for path in normalized}
        changed = [
            {"path": path, "old": redact(before[path], path), "new": redact(value, path)}
            for path, value in normalized.items()
            if before[path] != value
        ]
        result: dict[str, Any] = {
            "mode": mode,
            "revision": before_revision,
            "changed": changed,
            "unchanged": sorted(path for path, value in normalized.items() if before[path] == value),
        }
        self._validate_operation(normalized)
        if mode == "dry-run" or not changed:
            return result

        op = self._apply_scope_mutation(normalized, scopes, before_revision)
        if op is not None:
            result["operation"] = op
        after_revision = self.revision()
        result["revision"] = after_revision
        result["previous_revision"] = before_revision
        self._record_change(normalized, actor=actor, reason=reason, before_revision=before_revision, after_revision=after_revision)
        return result

    def _validate_backend_transition(self, changes: dict[str, Any]) -> None:
        allowed = {"store.storage.backend", "store.storage.shard_size", "store.storage.custom_shards"}
        if unexpected := set(changes) - allowed:
            raise ValueError(f"config_storage_transition_must_be_isolated:{sorted(unexpected)[0]}")
        current = self.store._storage_config()
        if current["backend"] != "sharded-yaml":
            return
        if changes["store.storage.backend"] == "single-yaml":
            raise ValueError("config_storage_rollback_not_implemented")
        shard_size = changes.get("store.storage.shard_size", current["shard_size"])
        custom_shards = changes.get("store.storage.custom_shards", current["custom_shards"])
        if shard_size != current["shard_size"] or custom_shards != current["custom_shards"]:
            raise ValueError("config_storage_reshard_required")

    def _validate_operation(self, changes: dict[str, Any]) -> None:
        if "store.storage.backend" in changes:
            self._validate_backend_transition(changes)
        if "store.storage.index" in changes and len(changes) != 1:
            raise ValueError("config_storage_index_must_be_isolated")
        routing_keys = {"store.storage.shard_size", "store.storage.custom_shards"}
        if "store.storage.backend" not in changes and (set(changes) & routing_keys) and self.store.storage_backend() == "sharded-yaml":
            raise ValueError("config_storage_reshard_required")

    def _current_value(self, path: str) -> Any:
        if path.startswith("store."):
            return _nested_get(self._store_values(), path.split(".")[1:])
        if path.startswith("integrations."):
            try:
                return _nested_get({"integrations": self._integration_values()}, path.split("."))
            except ValueError:
                return None
        runtime = load_runtime_context_config(self.project_dir)
        if path.startswith("runtime.overrides."):
            parts = path.removeprefix("runtime.overrides.").split(".")
            node: Any = runtime.get("overrides", {})
            for part in parts:
                if not isinstance(node, dict) or part not in node:
                    return None
                node = node[part]
            return node
        return _nested_get(runtime, path.split(".")[1:])

    def _set_store_values(self, changes: dict[str, Any], *, expected_revision: str) -> None:
        routing_changes = set(changes) & {"store.storage.shard_size", "store.storage.custom_shards"}
        if self.store.storage_backend() == "sharded-yaml" and routing_changes:
            raise ValueError("config_storage_reshard_required")
        with self.store.mutation_lock():
            self._check_revision(expected_revision)
            config = self.store._read_config()
            for path, value in changes.items():
                _nested_set(config, path.split(".")[1:], copy.deepcopy(value))
            self.store._write_config(config)

    def _set_storage_backend(self, changes: dict[str, Any], *, expected_revision: str) -> dict[str, Any]:
        target = changes["store.storage.backend"]
        current = self.store._storage_config()
        shard_size = changes.get("store.storage.shard_size", current["shard_size"])
        custom_shards = changes.get("store.storage.custom_shards", current["custom_shards"])
        if current["backend"] == "sharded-yaml":
            return {"backend": target, "migrated": False}
        if target == "single-yaml":
            self._set_store_values(changes, expected_revision=expected_revision)
            return {"backend": target, "migrated": False}
        return self.store.migrate_to_sharded_yaml(
            shard_size=shard_size,
            custom_shards=custom_shards,
            before_mutation=lambda: self._check_revision(expected_revision),
        )

    def _set_runtime_values(self, changes: dict[str, Any], *, expected_revision: str) -> None:
        with self.store.mutation_lock():
            self._check_revision(expected_revision)
            config = load_runtime_context_config(self.project_dir)
            for path, value in changes.items():
                _nested_set(config, path.split(".")[1:], copy.deepcopy(value))
            save_runtime_context_config(self.project_dir, config)

    def _find_shadowed_integration_paths(self, canonical_path: Path, setting_paths: Any) -> list[dict[str, str]]:
        shadowed: list[dict[str, str]] = []
        for source in self._integration_paths():
            if source == canonical_path or not source.is_file():
                continue
            data = _read_yaml_file(source) or {}
            for setting_path in setting_paths:
                try:
                    _nested_get(data, setting_path.split("."))
                    shadowed.append({"path": setting_path, "source": str(source.relative_to(self.project_dir))})
                except ValueError:
                    continue
        return shadowed

    def _set_integration_values(self, changes: dict[str, Any], *, expected_revision: str) -> dict[str, Any]:
        path = self._integration_config_path
        with self.store.mutation_lock():
            self._check_revision(expected_revision)
            config = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.is_file() else {}
            if not isinstance(config, dict):
                raise ValueError("config_integration_document_invalid")
            for setting_path, value in changes.items():
                _nested_set(config, setting_path.split("."), copy.deepcopy(value))
            self._write_yaml_document_atomic(path, config)
        return {
            "source": str(path.relative_to(self.project_dir)),
            "shadowed": self._find_shadowed_integration_paths(path, changes),
        }

    @staticmethod
    def _write_yaml_document_atomic(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=True,
        )
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)

    def _record_change(
        self,
        changes: dict[str, Any],
        *,
        actor: str,
        reason: str,
        before_revision: str,
        after_revision: str,
    ) -> None:
        event = operational_line(
            kind="configuration",
            source="planfile",
            actor=str(actor or "dsl"),
            oql="config.set",
            uri="planfile://config",
            mode="apply",
            status="applied",
            replayable=False,
            data={
                "changes": changes,
                "reason": reason,
                "previous_revision": before_revision,
                "revision": after_revision,
            },
        )
        with self.store.mutation_lock():
            self.store._append_operational_line(event)
