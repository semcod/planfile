"""Closed contracts for resumable Strategy delivery plans.

The Strategy compiler is deliberately inert.  These models preserve that
boundary while giving Planfile enough structured data to materialize tickets,
record explicit checkpoints and resume after an interrupted process.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

COMPILED_WORK_PLAN_SCHEMA = "subactor.compiled-work-plan/v1"
COMPILED_WORK_PLAN_V2_SCHEMA = "subactor.compiled-work-plan/v2"
AUTODO_PLANFILE_IMPORT_SCHEMA = "autodo.planfile-import/v1"
TICKET_CANDIDATE_SCHEMA = "subactor.ticket-candidate/v1"
TICKET_CANDIDATE_V2_SCHEMA = "subactor.ticket-candidate/v2"
DELIVERY_PLACEMENT_V2_SCHEMA = "planfile.delivery-placement/v2"
DELIVERY_PLAN_BUNDLE_SCHEMA = "planfile.delivery-plan-bundle/v1"
DELIVERY_PLAN_BUNDLE_STATE_SCHEMA = "planfile.delivery-plan-bundle-state/v1"
TRUSTED_TARGET_POLICY_SCHEMA = "planfile.trusted-delivery-targets/v1"
TERMINAL_RECEIPT_SCHEMA = "subactor.work-plan-terminal-receipt/v1"
DELIVERY_CHECKPOINT_SCHEMA = "planfile.delivery-checkpoint/v1"
DELIVERY_SPLIT_SCHEMA = "planfile.delivery-plan-split/v1"
DELIVERY_PLAN_STATE_SCHEMA = "planfile.delivery-plan-state/v1"
DELIVERY_PLAN_RESUME_SCHEMA = "planfile.delivery-plan-resume/v1"

_ID = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_NAMESPACE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REPOSITORY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}/(?:\*|[A-Za-z0-9._-]+)$")
_SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")
_GIT_SHA = re.compile(r"^[a-f0-9]{40}$")
_REFERENCE = re.compile(r"^(?:artifact|knowledge)://[^\s?#]+$")
_RECEIPT_REFERENCE = re.compile(r"^receipt://[^\s?#]+$")
_CHECKPOINT_REFERENCE = re.compile(r"^checkpoint://[^\s?#]+$")
_SAFE_PATH = re.compile(
    r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$"
)
_BRANCH = re.compile(r"^(?!/)(?!.*(?:\.\.|//|@\{|[~^:?*\[\\]))[A-Za-z0-9._/-]+$")


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()}"


def _tuple_of_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("expected a list or tuple")
    return tuple(str(item) for item in value)


def _timestamp(value: object) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("delivery_plan_timestamp_invalid") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("delivery_plan_timestamp_invalid")
    return value


class _ClosedContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True, strict=True)


def _normalize_adopt_tuple(value: object) -> tuple[str, ...]:
    result = _tuple_of_strings(value)
    if not result or len(set(result)) != len(result):
        raise ValueError("delivery_plan_adoption_invalid")
    if any(not re.fullmatch(r"wellmanifest/[a-z0-9][a-z0-9-]{1,79}", item) for item in result):
        raise ValueError("delivery_plan_adoption_invalid")
    return tuple(sorted(result))


class DeliveryPlacementV1(_ClosedContract):
    home: Literal["wellmanifest", "subactor", "semcod"]
    shape: Literal["domain_pack", "runtime_service", "both"]
    runtime_owner: Literal["wellmanifest", "subactor", "semcod"]
    adopt: tuple[str, ...]

    @field_validator("adopt", mode="before")
    @classmethod
    def _normalize_adopt(cls, value: object) -> tuple[str, ...]:
        return _normalize_adopt_tuple(value)

    @model_validator(mode="after")
    def _runtime_home(self) -> DeliveryPlacementV1:
        if self.shape == "runtime_service" and (
            self.home == "wellmanifest" or self.runtime_owner == "wellmanifest"
        ):
            raise ValueError("delivery_plan_runtime_home_invalid")
        return self


class DeliveryPlacementV2(_ClosedContract):
    """Explicitly versioned placement supporting verified ecosystem owner namespaces."""

    schema_id: Literal["planfile.delivery-placement/v2"] = Field(
        default="planfile.delivery-placement/v2",
        alias="schema",
    )
    home: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    shape: Literal["domain_pack", "runtime_service", "both"]
    runtime_owner: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    adopt: tuple[str, ...]

    @field_validator("adopt", mode="before")
    @classmethod
    def _normalize_adopt(cls, value: object) -> tuple[str, ...]:
        return _normalize_adopt_tuple(value)

    @model_validator(mode="after")
    def _runtime_home(self) -> DeliveryPlacementV2:
        if self.shape == "runtime_service" and (
            self.home == "wellmanifest" or self.runtime_owner == "wellmanifest"
        ):
            raise ValueError("delivery_plan_runtime_home_invalid")
        return self


class TrustedDeliveryTarget(_ClosedContract):
    """Declared allowlist entry authorizing placement schema verification (not execution)."""

    repository_pattern: str
    owner_namespace: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    allowed_runtime_owners: tuple[str, ...]
    allow_runtime_service: bool = True
    execution_authority: Literal["none"] = "none"

    @field_validator("repository_pattern")
    @classmethod
    def _validate_pattern(cls, value: str) -> str:
        if not _REPOSITORY_PATTERN.fullmatch(value):
            raise ValueError("delivery_plan_trusted_target_pattern_invalid")
        return value

    @field_validator("allowed_runtime_owners", mode="before")
    @classmethod
    def _validate_runtime_owners(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)) or any(
            not isinstance(item, str) or not _NAMESPACE.fullmatch(item) for item in value
        ):
            raise ValueError("delivery_plan_trusted_runtime_owners_invalid")
        result = tuple(sorted(set(value)))
        if not result:
            raise ValueError("delivery_plan_trusted_runtime_owners_invalid")
        return result

    @model_validator(mode="after")
    def _validate_owner_prefix(self) -> TrustedDeliveryTarget:
        prefix = self.repository_pattern.split("/", 1)[0].lower()
        if prefix != self.owner_namespace:
            raise ValueError("delivery_plan_trusted_owner_mismatch")
        return self


class TrustedTargetPolicyV1(_ClosedContract):
    """Explicit repository/owner placement policy; schema validity never grants execution authority."""

    schema_id: Literal["planfile.trusted-delivery-targets/v1"] = Field(
        default="planfile.trusted-delivery-targets/v1",
        alias="schema",
    )
    targets: tuple[TrustedDeliveryTarget, ...]

    @field_validator("targets", mode="before")
    @classmethod
    def _normalize_targets(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        return tuple(value)

    @model_validator(mode="after")
    def _validate_unique_patterns(self) -> TrustedTargetPolicyV1:
        patterns = [target.repository_pattern.lower() for target in self.targets]
        if not patterns or len(set(patterns)) != len(patterns):
            raise ValueError("delivery_plan_trusted_targets_invalid")
        return self

    def verify_target(
        self,
        repository: str,
        placement: DeliveryPlacementV1 | DeliveryPlacementV2,
    ) -> TrustedDeliveryTarget:
        if not _REPOSITORY.fullmatch(repository):
            raise ValueError("delivery_plan_repository_invalid")
        repo_lower = repository.lower()
        repo_owner = repo_lower.split("/", 1)[0]
        if repo_owner != placement.home:
            raise ValueError("delivery_plan_owner_namespace_mismatch")
        by_pattern = {target.repository_pattern.lower(): target for target in self.targets}
        matched = by_pattern.get(repo_lower) or by_pattern.get(f"{repo_owner}/*")
        if matched is None:
            raise ValueError(f"delivery_plan_target_not_trusted:{repository}")
        if placement.runtime_owner not in matched.allowed_runtime_owners:
            raise ValueError(f"delivery_plan_runtime_owner_not_trusted:{placement.runtime_owner}")
        if placement.shape == "runtime_service" and not matched.allow_runtime_service:
            raise ValueError("delivery_plan_runtime_home_invalid")
        return matched


DEFAULT_TRUSTED_TARGET_POLICY = TrustedTargetPolicyV1(
    targets=(
        TrustedDeliveryTarget(
            repository_pattern="wellmanifest/*",
            owner_namespace="wellmanifest",
            allowed_runtime_owners=("wellmanifest", "subactor", "semcod"),
            allow_runtime_service=False,
        ),
        TrustedDeliveryTarget(
            repository_pattern="subactor/*",
            owner_namespace="subactor",
            allowed_runtime_owners=("subactor",),
            allow_runtime_service=True,
        ),
        TrustedDeliveryTarget(
            repository_pattern="semcod/*",
            owner_namespace="semcod",
            allowed_runtime_owners=("semcod", "subactor"),
            allow_runtime_service=True,
        ),
        TrustedDeliveryTarget(
            repository_pattern="dockuri/*",
            owner_namespace="dockuri",
            allowed_runtime_owners=("dockuri", "subactor"),
            allow_runtime_service=True,
        ),
        TrustedDeliveryTarget(
            repository_pattern="uritime/autodo",
            owner_namespace="uritime",
            allowed_runtime_owners=("uritime", "subactor"),
            allow_runtime_service=True,
        ),
        TrustedDeliveryTarget(
            repository_pattern="paxlet-com/heyasa",
            owner_namespace="paxlet-com",
            allowed_runtime_owners=("paxlet-com", "subactor"),
            allow_runtime_service=True,
        ),
    )
)


class DeliveryBudgetV1(_ClosedContract):
    complexity: Literal["XS", "S", "M", "L"]
    estimated_minutes: int = Field(ge=1, le=240)
    max_implementation_files: int = Field(ge=1, le=30)
    max_affected_components: int = Field(ge=1, le=10)
    max_public_interface_changes: int = Field(ge=0, le=10)
    max_runtime_dependencies: int = Field(ge=0, le=10)


class DeliveryTestBindingV1(_ClosedContract):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    kind: Literal["docker", "governance", "node-test", "python-test"]
    target: str

    @field_validator("target")
    @classmethod
    def _safe_target(cls, value: str) -> str:
        if not _SAFE_PATH.fullmatch(value):
            raise ValueError("delivery_plan_test_target_invalid")
        return value


class DeliveryAcceptanceV1(_ClosedContract):
    id: str = Field(pattern=r"^AC-[0-9]{2}$")
    statement: str = Field(min_length=1)
    test_ids: tuple[str, ...]

    @field_validator("test_ids", mode="before")
    @classmethod
    def _normalize_test_ids(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if not result or len(set(result)) != len(result) or any(not _ID.fullmatch(v) for v in result):
            raise ValueError("delivery_plan_acceptance_tests_invalid")
        return tuple(sorted(result))


class TicketCandidateV1(_ClosedContract):
    schema_id: Literal["subactor.ticket-candidate/v1"] = Field(
        default="subactor.ticket-candidate/v1",
        alias="schema",
    )
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    candidate_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    order: int = Field(ge=0, le=1023)
    title: str = Field(min_length=1)
    workstream: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    depends_on: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    placement: DeliveryPlacementV1
    delivery: DeliveryBudgetV1
    components: tuple[str, ...]
    public_interfaces: tuple[str, ...]
    runtime_dependencies: tuple[str, ...]
    acceptance: tuple[DeliveryAcceptanceV1, ...]
    tests: tuple[DeliveryTestBindingV1, ...]
    execution: Literal["inert"]
    candidate_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    state: Literal["pending", "split_required", "terminal"]
    split_reasons: tuple[str, ...]
    terminal_receipt_ref: str | None

    @field_validator(
        "depends_on",
        "allowed_paths",
        "components",
        "public_interfaces",
        "runtime_dependencies",
        "split_reasons",
        mode="before",
    )
    @classmethod
    def _normalize_string_tuple(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if len(set(result)) != len(result):
            raise ValueError("delivery_plan_candidate_set_duplicate")
        return tuple(sorted(result))

    @field_validator("acceptance", "tests", mode="before")
    @classmethod
    def _normalize_model_tuple(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        return tuple(value)

    @model_validator(mode="after")
    def _validate_candidate(self) -> TicketCandidateV1:
        _validate_candidate_invariants(self)
        _validate_candidate_digests(
            self,
            {
                "schema_id",
                "plan_hash",
                "candidate_key",
                "order",
                "title",
                "workstream",
                "depends_on",
                "allowed_paths",
                "placement",
                "delivery",
                "components",
                "public_interfaces",
                "runtime_dependencies",
                "acceptance",
                "tests",
                "execution",
            },
        )
        return self


class CompiledWorkPlanV1(_ClosedContract):
    schema_id: Literal["subactor.compiled-work-plan/v1"] = Field(
        default="subactor.compiled-work-plan/v1",
        alias="schema",
    )
    status: Literal["ready", "split_required"]
    execution: Literal["inert"]
    authority: Literal["none"]
    plan_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    plan_ref: str
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    repository: str
    accepted_base_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    target_branch: str
    placement: DeliveryPlacementV1
    candidate_count: int = Field(ge=1, le=12)
    pending_count: int = Field(ge=0, le=12)
    split_required: tuple[str, ...]
    terminal_candidates: tuple[str, ...]
    candidates: tuple[TicketCandidateV1, ...]

    @field_validator("split_required", "terminal_candidates", mode="before")
    @classmethod
    def _normalize_key_tuple(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if len(set(result)) != len(result) or any(not _ID.fullmatch(item) for item in result):
            raise ValueError("delivery_plan_candidate_keys_invalid")
        return tuple(sorted(result))

    @field_validator("candidates", mode="before")
    @classmethod
    def _normalize_candidates(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        return tuple(value)

    @field_validator("plan_ref")
    @classmethod
    def _plan_reference(cls, value: str) -> str:
        if not _REFERENCE.fullmatch(value):
            raise ValueError("delivery_plan_ref_invalid")
        return value

    @field_validator("repository")
    @classmethod
    def _repository(cls, value: str) -> str:
        if not _REPOSITORY.fullmatch(value):
            raise ValueError("delivery_plan_repository_invalid")
        return value

    @field_validator("target_branch")
    @classmethod
    def _branch(cls, value: str) -> str:
        if not _BRANCH.fullmatch(value):
            raise ValueError("delivery_plan_branch_invalid")
        return value

    @model_validator(mode="after")
    def _validate_graph(self) -> CompiledWorkPlanV1:
        _validate_compiled_plan_graph(self)
        return self


class WorkPlanTerminalReceiptV1(_ClosedContract):
    schema_id: Literal["subactor.work-plan-terminal-receipt/v1"] = Field(
        default="subactor.work-plan-terminal-receipt/v1",
        alias="schema",
    )
    receipt_ref: str
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    candidate_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    candidate_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    accepted_base_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    outcome: Literal["merged", "no-change"]
    terminal_sha: str = Field(pattern=r"^[a-f0-9]{40}$")

    @field_validator("receipt_ref")
    @classmethod
    def _receipt_reference(cls, value: str) -> str:
        if not _RECEIPT_REFERENCE.fullmatch(value):
            raise ValueError("delivery_plan_receipt_ref_invalid")
        return value


class DeliveryCheckpointV1(_ClosedContract):
    schema_id: Literal["planfile.delivery-checkpoint/v1"] = Field(
        default="planfile.delivery-checkpoint/v1",
        alias="schema",
    )
    checkpoint_ref: str
    plan_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    candidate_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    candidate_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    sequence: int = Field(ge=1)
    phase: Literal["materialized", "development", "testing", "review", "waiting"]
    head_sha: str | None = Field(default=None, pattern=r"^[a-f0-9]{40}$")
    evidence_refs: tuple[str, ...] = ()
    recorded_at: datetime

    @field_validator("recorded_at", mode="before")
    @classmethod
    def _recorded_timestamp(cls, value: object) -> datetime:
        return _timestamp(value)

    @field_validator("checkpoint_ref")
    @classmethod
    def _checkpoint_reference(cls, value: str) -> str:
        if not _CHECKPOINT_REFERENCE.fullmatch(value):
            raise ValueError("delivery_plan_checkpoint_ref_invalid")
        return value

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _evidence_references(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if len(set(result)) != len(result) or any(not _REFERENCE.fullmatch(item) for item in result):
            raise ValueError("delivery_plan_checkpoint_evidence_invalid")
        return tuple(sorted(result))


class DeliveryPlanSplitV1(_ClosedContract):
    schema_id: Literal["planfile.delivery-plan-split/v1"] = Field(
        default="planfile.delivery-plan-split/v1",
        alias="schema",
    )
    split_ref: str
    plan_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    parent_candidate_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    parent_candidate_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    child_candidate_keys: tuple[str, ...]
    recorded_at: datetime

    @field_validator("recorded_at", mode="before")
    @classmethod
    def _recorded_timestamp(cls, value: object) -> datetime:
        return _timestamp(value)

    @field_validator("split_ref")
    @classmethod
    def _split_reference(cls, value: str) -> str:
        if not value.startswith("split://") or any(character.isspace() for character in value):
            raise ValueError("delivery_plan_split_ref_invalid")
        return value

    @field_validator("child_candidate_keys", mode="before")
    @classmethod
    def _children(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if len(result) < 2 or len(set(result)) != len(result) or any(
            not _ID.fullmatch(item) for item in result
        ):
            raise ValueError("delivery_plan_split_children_invalid")
        return tuple(sorted(result))


class AutodoPlanfileImportMetadataV1(_ClosedContract):
    """Explicit external import envelope kept separate from native compiled work plans."""

    schema_id: Literal["autodo.planfile-import/v1"] = Field(
        default="autodo.planfile-import/v1",
        alias="schema",
    )
    campaign_id: str = Field(min_length=1)
    importer: str = Field(min_length=1)
    imported_at: datetime
    source_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    proposal_keys: tuple[str, ...] = ()
    compiled_plan: CompiledWorkPlanV1 | None = None

    @field_validator("imported_at", mode="before")
    @classmethod
    def _imported_timestamp(cls, value: object) -> datetime:
        return _timestamp(value)

    @field_validator("proposal_keys", mode="before")
    @classmethod
    def _normalize_proposal_keys(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            raise ValueError("delivery_plan_import_proposal_keys_invalid")
        result = tuple(value)
        if len(set(result)) != len(result):
            raise ValueError("delivery_plan_import_proposal_keys_invalid")
        return result


def _validate_candidate_invariants(candidate: Any) -> None:
    if not candidate.allowed_paths or any(
        not _SAFE_PATH.fullmatch(path) for path in candidate.allowed_paths
    ):
        raise ValueError("delivery_plan_candidate_paths_invalid")
    if not candidate.components or not candidate.acceptance or not candidate.tests:
        raise ValueError("delivery_plan_candidate_evidence_invalid")
    test_ids = {binding.id for binding in candidate.tests}
    if len(test_ids) != len(candidate.tests):
        raise ValueError("delivery_plan_candidate_test_duplicate")
    if len({criterion.id for criterion in candidate.acceptance}) != len(candidate.acceptance):
        raise ValueError("delivery_plan_candidate_acceptance_duplicate")
    if any(not set(criterion.test_ids).issubset(test_ids) for criterion in candidate.acceptance):
        raise ValueError("delivery_plan_candidate_acceptance_test_unknown")
    if candidate.state == "terminal":
        if not candidate.terminal_receipt_ref or not _RECEIPT_REFERENCE.fullmatch(
            candidate.terminal_receipt_ref
        ):
            raise ValueError("delivery_plan_candidate_terminal_receipt_invalid")
    elif candidate.terminal_receipt_ref is not None:
        raise ValueError("delivery_plan_candidate_terminal_receipt_unexpected")
    if (candidate.state == "split_required") != bool(candidate.split_reasons):
        raise ValueError("delivery_plan_candidate_split_state_invalid")


def _validate_candidate_digests(candidate: Any, include_fields: set[str]) -> None:
    core = candidate.model_dump(mode="json", by_alias=True, include=include_fields)
    if _digest(core) != candidate.candidate_digest:
        raise ValueError("delivery_plan_candidate_digest_mismatch")
    expected_idempotency = _digest(
        {
            "plan_hash": candidate.plan_hash,
            "candidate_key": candidate.candidate_key,
            "candidate_digest": candidate.candidate_digest,
        }
    )
    if expected_idempotency != candidate.idempotency_key:
        raise ValueError("delivery_plan_candidate_idempotency_mismatch")


def _validate_compiled_plan_graph(plan: Any) -> None:
    if len(plan.candidates) != plan.candidate_count:
        raise ValueError("delivery_plan_candidate_count_mismatch")
    keys = [candidate.candidate_key for candidate in plan.candidates]
    if len(set(keys)) != len(keys):
        raise ValueError("delivery_plan_candidate_key_duplicate")
    if [candidate.order for candidate in plan.candidates] != list(range(len(plan.candidates))):
        raise ValueError("delivery_plan_candidate_order_invalid")
    order = {candidate.candidate_key: candidate.order for candidate in plan.candidates}
    for candidate in plan.candidates:
        if candidate.plan_hash != plan.plan_hash or candidate.placement != plan.placement:
            raise ValueError("delivery_plan_candidate_binding_mismatch")
        if any(dependency not in order for dependency in candidate.depends_on):
            raise ValueError("delivery_plan_dependency_unknown")
        if any(order[dependency] >= candidate.order for dependency in candidate.depends_on):
            raise ValueError("delivery_plan_dependency_order_invalid")
    split = tuple(sorted(c.candidate_key for c in plan.candidates if c.state == "split_required"))
    terminal = tuple(sorted(c.candidate_key for c in plan.candidates if c.state == "terminal"))
    if split != plan.split_required or terminal != plan.terminal_candidates:
        raise ValueError("delivery_plan_candidate_state_projection_mismatch")
    if plan.pending_count != len(plan.candidates) - len(split) - len(terminal):
        raise ValueError("delivery_plan_pending_count_mismatch")
    if (plan.status == "split_required") != bool(split):
        raise ValueError("delivery_plan_status_mismatch")


class CrossPlanDependencyRefV1(_ClosedContract):
    """Explicit canonical reference to a prerequisite candidate in another bounded subplan."""

    plan_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    candidate_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")


class TicketCandidateV2(_ClosedContract):
    schema_id: Literal["subactor.ticket-candidate/v2"] = Field(
        default="subactor.ticket-candidate/v2",
        alias="schema",
    )
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    candidate_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    order: int = Field(ge=0, le=1023)
    title: str = Field(min_length=1)
    workstream: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    depends_on: tuple[str, ...]
    external_depends_on: tuple[CrossPlanDependencyRefV1, ...] = ()
    allowed_paths: tuple[str, ...]
    placement: DeliveryPlacementV2
    delivery: DeliveryBudgetV1
    components: tuple[str, ...]
    public_interfaces: tuple[str, ...]
    runtime_dependencies: tuple[str, ...]
    acceptance: tuple[DeliveryAcceptanceV1, ...]
    tests: tuple[DeliveryTestBindingV1, ...]
    execution: Literal["inert"]
    candidate_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    state: Literal["pending", "split_required", "terminal"]
    split_reasons: tuple[str, ...]
    terminal_receipt_ref: str | None

    @field_validator(
        "depends_on",
        "allowed_paths",
        "components",
        "public_interfaces",
        "runtime_dependencies",
        "split_reasons",
        mode="before",
    )
    @classmethod
    def _normalize_string_tuple(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if len(set(result)) != len(result):
            raise ValueError("delivery_plan_candidate_set_duplicate")
        return tuple(sorted(result))

    @field_validator("external_depends_on", mode="before")
    @classmethod
    def _normalize_external_depends_on(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        return tuple(value)

    @field_validator("acceptance", "tests", mode="before")
    @classmethod
    def _normalize_model_tuple(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        return tuple(value)

    @model_validator(mode="after")
    def _validate_candidate(self) -> TicketCandidateV2:
        _validate_candidate_invariants(self)
        ext_pairs = [(ref.plan_id, ref.candidate_key) for ref in self.external_depends_on]
        if len(set(ext_pairs)) != len(ext_pairs):
            raise ValueError("delivery_plan_external_dependency_duplicate")
        if ext_pairs != sorted(ext_pairs):
            raise ValueError("delivery_plan_external_dependency_order_invalid")
        _validate_candidate_digests(
            self,
            {
                "schema_id",
                "plan_hash",
                "candidate_key",
                "order",
                "title",
                "workstream",
                "depends_on",
                "external_depends_on",
                "allowed_paths",
                "placement",
                "delivery",
                "components",
                "public_interfaces",
                "runtime_dependencies",
                "acceptance",
                "tests",
                "execution",
            },
        )
        return self


class CompiledWorkPlanV2(_ClosedContract):
    """Explicitly versioned bounded work plan supporting verified owner namespaces."""

    schema_id: Literal["subactor.compiled-work-plan/v2"] = Field(
        default="subactor.compiled-work-plan/v2",
        alias="schema",
    )
    status: Literal["ready", "split_required"]
    execution: Literal["inert"]
    authority: Literal["none"]
    plan_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    plan_ref: str
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    repository: str
    accepted_base_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    target_branch: str
    placement: DeliveryPlacementV2
    candidate_count: int = Field(ge=1, le=12)
    pending_count: int = Field(ge=0, le=12)
    split_required: tuple[str, ...]
    terminal_candidates: tuple[str, ...]
    candidates: tuple[TicketCandidateV2, ...]

    @field_validator("split_required", "terminal_candidates", mode="before")
    @classmethod
    def _normalize_key_tuple(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if len(set(result)) != len(result) or any(not _ID.fullmatch(item) for item in result):
            raise ValueError("delivery_plan_candidate_keys_invalid")
        return tuple(sorted(result))

    @field_validator("candidates", mode="before")
    @classmethod
    def _normalize_candidates(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        return tuple(value)

    @field_validator("plan_ref")
    @classmethod
    def _plan_reference(cls, value: str) -> str:
        if not _REFERENCE.fullmatch(value):
            raise ValueError("delivery_plan_ref_invalid")
        return value

    @field_validator("repository")
    @classmethod
    def _repository(cls, value: str) -> str:
        if not _REPOSITORY.fullmatch(value):
            raise ValueError("delivery_plan_repository_invalid")
        return value

    @field_validator("target_branch")
    @classmethod
    def _branch(cls, value: str) -> str:
        if not _BRANCH.fullmatch(value):
            raise ValueError("delivery_plan_branch_invalid")
        return value

    @model_validator(mode="after")
    def _validate_graph(self) -> CompiledWorkPlanV2:
        _validate_compiled_plan_graph(self)
        if self.repository.split("/", 1)[0].lower() != self.placement.home:
            raise ValueError("delivery_plan_owner_namespace_mismatch")
        for candidate in self.candidates:
            if any(ref.plan_id == self.plan_id for ref in candidate.external_depends_on):
                raise ValueError("delivery_plan_external_dependency_self_plan")
        return self


def _bundle_digest_payload(
    bundle_id: str,
    bundle_ref: str,
    subplans: Sequence[CompiledWorkPlanV2],
) -> dict[str, object]:
    return {
        "bundle_id": bundle_id,
        "bundle_ref": bundle_ref,
        "subplans": [
            {
                "plan_id": subplan.plan_id,
                "plan_hash": subplan.plan_hash,
                "repository": subplan.repository,
                "accepted_base_sha": subplan.accepted_base_sha,
            }
            for subplan in subplans
        ],
    }


class DeliveryPlanBundleV1(_ClosedContract):
    """Multi-repository composition of bounded single-repo native delivery subplans."""

    schema_id: Literal["planfile.delivery-plan-bundle/v1"] = Field(
        default="planfile.delivery-plan-bundle/v1",
        alias="schema",
    )
    bundle_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    bundle_ref: str
    bundle_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    execution: Literal["inert"] = "inert"
    authority: Literal["none"] = "none"
    subplans: tuple[CompiledWorkPlanV2, ...] = Field(min_length=1, max_length=32)

    @field_validator("bundle_ref")
    @classmethod
    def _bundle_reference(cls, value: str) -> str:
        if not _REFERENCE.fullmatch(value):
            raise ValueError("delivery_plan_bundle_ref_invalid")
        return value

    @field_validator("subplans", mode="before")
    @classmethod
    def _normalize_subplans(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        return tuple(value)

    @model_validator(mode="after")
    def _validate_bundle(self) -> DeliveryPlanBundleV1:
        plan_ids = [subplan.plan_id for subplan in self.subplans]
        if len(set(plan_ids)) != len(plan_ids):
            raise ValueError("delivery_plan_bundle_plan_duplicate")

        repo_bindings: dict[str, tuple[str, dict[str, Any]]] = {}
        nodes: set[tuple[str, str]] = set()
        adjacency: dict[tuple[str, str], list[tuple[str, str]]] = {}
        in_degree: dict[tuple[str, str], int] = {}

        for subplan in self.subplans:
            binding = (
                subplan.accepted_base_sha,
                subplan.placement.model_dump(mode="json", by_alias=True),
            )
            previous = repo_bindings.get(subplan.repository)
            if previous is not None and previous != binding:
                raise ValueError("delivery_plan_bundle_repository_conflict")
            repo_bindings[subplan.repository] = binding
            for candidate in subplan.candidates:
                node = (subplan.plan_id, candidate.candidate_key)
                nodes.add(node)
                adjacency.setdefault(node, [])
                in_degree.setdefault(node, 0)

        for subplan in self.subplans:
            for candidate in subplan.candidates:
                node = (subplan.plan_id, candidate.candidate_key)
                for dep in candidate.depends_on:
                    dep_node = (subplan.plan_id, dep)
                    adjacency[dep_node].append(node)
                    in_degree[node] += 1
                for ext in candidate.external_depends_on:
                    ext_node = (ext.plan_id, ext.candidate_key)
                    if ext_node not in nodes:
                        raise ValueError("delivery_plan_bundle_dependency_unknown")
                    adjacency[ext_node].append(node)
                    in_degree[node] += 1

        queue: deque[tuple[str, str]] = deque(
            sorted(node for node, deg in in_degree.items() if deg == 0)
        )
        visited = 0
        while queue:
            current = queue.popleft()
            visited += 1
            for dependent in adjacency[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        if visited != len(nodes):
            raise ValueError("delivery_plan_bundle_dependency_cycle")

        expected_hash = _digest(
            _bundle_digest_payload(self.bundle_id, self.bundle_ref, self.subplans)
        )
        if expected_hash != self.bundle_hash:
            raise ValueError("delivery_plan_bundle_hash_mismatch")
        return self


def _subplan_id(bundle_id: str, repository: str, part_index: int) -> str:
    repo_slug = re.sub(r"[^a-z0-9]+", "-", repository.lower()).strip("-")
    suffix = f"-{part_index:02d}"
    raw = f"{bundle_id}-{repo_slug}{suffix}"
    if len(raw) <= 64 and _ID.fullmatch(raw):
        return raw
    short_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    head_max = 64 - len(suffix) - len(short_hash) - 1
    prefix = f"{bundle_id}-{repo_slug}"[: max(2, head_max)].rstrip("-")
    candidate = f"{prefix}-{short_hash}{suffix}"
    if not _ID.fullmatch(candidate):
        return f"p-{short_hash}{suffix}"
    return candidate


def compose_delivery_plan_bundle(
    proposals: Sequence[dict[str, Any]],
    *,
    bundle_id: str,
    bundle_ref: str,
    target_branch: str = "main",
    max_candidates_per_plan: int = 12,
    trusted_policy: TrustedTargetPolicyV1 = DEFAULT_TRUSTED_TARGET_POLICY,
) -> DeliveryPlanBundleV1:
    """Deterministically compose cross-repo proposals into bounded <=12 native subplans."""
    if not _ID.fullmatch(bundle_id):
        raise ValueError("delivery_plan_bundle_id_invalid")
    if not _REFERENCE.fullmatch(bundle_ref):
        raise ValueError("delivery_plan_bundle_ref_invalid")
    if not _BRANCH.fullmatch(target_branch):
        raise ValueError("delivery_plan_branch_invalid")
    if not isinstance(max_candidates_per_plan, int) or not (1 <= max_candidates_per_plan <= 12):
        raise ValueError("delivery_plan_bundle_chunk_limit_invalid")
    if not proposals:
        raise ValueError("delivery_plan_bundle_empty")

    by_key: dict[str, dict[str, Any]] = {}
    repo_bindings: dict[str, tuple[str, DeliveryPlacementV2]] = {}
    deps_by_key: dict[str, tuple[str, ...]] = {}
    dependents_by_key: dict[str, list[str]] = {}

    for raw in proposals:
        if not isinstance(raw, dict):
            raise ValueError("delivery_plan_bundle_proposal_invalid")
        key = str(raw.get("proposal_key") or "").strip()
        if not _ID.fullmatch(key):
            raise ValueError("delivery_plan_bundle_proposal_key_invalid")
        if key in by_key:
            raise ValueError("delivery_plan_bundle_proposal_duplicate")
        candidate_key = str(raw.get("candidate_key") or key).strip()
        if not _ID.fullmatch(candidate_key):
            raise ValueError("delivery_plan_candidate_keys_invalid")
        repository = str(raw.get("repository") or "").strip()
        if not _REPOSITORY.fullmatch(repository):
            raise ValueError("delivery_plan_repository_invalid")
        accepted_base_sha = str(raw.get("accepted_base_sha") or "").strip()
        if not _GIT_SHA.fullmatch(accepted_base_sha):
            raise ValueError("delivery_plan_bundle_base_sha_invalid")
        raw_placement = raw.get("placement")
        placement_dict = (
            dict(raw_placement, schema=DELIVERY_PLACEMENT_V2_SCHEMA)
            if isinstance(raw_placement, dict) and "schema" not in raw_placement
            else raw_placement
        )
        placement = DeliveryPlacementV2.model_validate(placement_dict)
        trusted_policy.verify_target(repository, placement)

        prev_binding = repo_bindings.get(repository)
        if prev_binding is not None and (
            prev_binding[0] != accepted_base_sha or prev_binding[1] != placement
        ):
            raise ValueError("delivery_plan_bundle_repository_conflict")
        repo_bindings[repository] = (accepted_base_sha, placement)

        raw_deps = raw.get("depends_on_proposals", ())
        if not isinstance(raw_deps, (list, tuple)) or any(
            not isinstance(dep, str) for dep in raw_deps
        ):
            raise ValueError("delivery_plan_bundle_dependency_invalid")
        deps = tuple(sorted(set(raw_deps)))
        if key in deps:
            raise ValueError("delivery_plan_bundle_dependency_cycle")
        by_key[key] = {**raw, "proposal_key": key, "candidate_key": candidate_key}
        deps_by_key[key] = deps
        dependents_by_key.setdefault(key, [])

    for key, deps in deps_by_key.items():
        for dep in deps:
            if dep not in by_key:
                raise ValueError(f"delivery_plan_bundle_dependency_unknown:{dep}")
            dependents_by_key[dep].append(key)

    in_degree = {key: len(deps) for key, deps in deps_by_key.items()}
    topo_depth = dict.fromkeys(by_key, 0)
    ready_queue: deque[str] = deque(sorted(key for key, deg in in_degree.items() if deg == 0))
    topo_order: list[str] = []
    while ready_queue:
        current = ready_queue.popleft()
        topo_order.append(current)
        for dependent in sorted(dependents_by_key[current]):
            topo_depth[dependent] = max(topo_depth[dependent], topo_depth[current] + 1)
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready_queue.append(dependent)
    if len(topo_order) != len(by_key):
        raise ValueError("delivery_plan_bundle_dependency_cycle")

    global_rank = {key: idx for idx, key in enumerate(topo_order)}
    by_repo: dict[str, list[str]] = {}
    for key in by_key:
        by_repo.setdefault(str(by_key[key]["repository"]), []).append(key)
    for keys in by_repo.values():
        keys.sort(key=lambda item: (topo_depth[item], global_rank[item], by_key[item]["candidate_key"]))
        if len({by_key[item]["candidate_key"] for item in keys}) != len(keys):
            raise ValueError("delivery_plan_candidate_key_duplicate")

    ordered_repos = sorted(
        by_repo,
        key=lambda repo: (min(global_rank[item] for item in by_repo[repo]), repo.lower()),
    )

    chunks: list[tuple[str, str, list[str]]] = []
    proposal_location: dict[str, tuple[str, str]] = {}
    for repository in ordered_repos:
        keys = by_repo[repository]
        for chunk_idx, start in enumerate(range(0, len(keys), max_candidates_per_plan), start=1):
            slice_keys = keys[start : start + max_candidates_per_plan]
            plan_id = _subplan_id(bundle_id, repository, chunk_idx)
            chunks.append((repository, plan_id, slice_keys))
            for item_key in slice_keys:
                proposal_location[item_key] = (plan_id, str(by_key[item_key]["candidate_key"]))

    subplans: list[CompiledWorkPlanV2] = []
    for repository, plan_id, slice_keys in chunks:
        accepted_base_sha, placement = repo_bindings[repository]
        placement_dump = placement.model_dump(mode="json", by_alias=True)
        plan_ref = f"artifact://{repository}/{plan_id}"
        in_chunk_keys = set(slice_keys)

        candidate_cores: list[dict[str, Any]] = []
        raw_states: list[tuple[str, list[str], str | None]] = []
        for order_idx, item_key in enumerate(slice_keys):
            raw = by_key[item_key]
            local_deps = sorted(
                str(by_key[dep]["candidate_key"])
                for dep in deps_by_key[item_key]
                if dep in in_chunk_keys
            )
            ext_deps = sorted(
                (
                    {
                        "plan_id": proposal_location[dep][0],
                        "candidate_key": proposal_location[dep][1],
                    }
                    for dep in deps_by_key[item_key]
                    if dep not in in_chunk_keys
                ),
                key=lambda item: (item["plan_id"], item["candidate_key"]),
            )
            core = {
                "schema": TICKET_CANDIDATE_V2_SCHEMA,
                "plan_hash": "sha256:" + "0" * 64,
                "candidate_key": str(raw["candidate_key"]),
                "order": order_idx,
                "title": str(raw["title"]),
                "workstream": str(raw.get("workstream") or "application"),
                "depends_on": local_deps,
                "external_depends_on": ext_deps,
                "allowed_paths": sorted(str(p) for p in raw["allowed_paths"]),
                "placement": placement_dump,
                "delivery": dict(raw["delivery"]),
                "components": sorted(str(c) for c in raw["components"]),
                "public_interfaces": sorted(str(p) for p in raw.get("public_interfaces", ())),
                "runtime_dependencies": sorted(str(d) for d in raw.get("runtime_dependencies", ())),
                "acceptance": [
                    {**item, "test_ids": sorted(str(t) for t in item["test_ids"])}
                    if isinstance(item, dict) and "test_ids" in item
                    else item
                    for item in raw["acceptance"]
                ],
                "tests": list(raw["tests"]),
                "execution": "inert",
            }
            candidate_cores.append(core)
            raw_states.append(
                (
                    str(raw.get("state") or "pending"),
                    list(raw.get("split_reasons") or []),
                    raw.get("terminal_receipt_ref"),
                )
            )

        plan_hash = _digest(
            {
                "bundle_id": bundle_id,
                "plan_id": plan_id,
                "plan_ref": plan_ref,
                "repository": repository,
                "accepted_base_sha": accepted_base_sha,
                "target_branch": target_branch,
                "placement": placement_dump,
                "candidates": [
                    {k: v for k, v in core.items() if k != "plan_hash"} for core in candidate_cores
                ],
            }
        )

        candidates_payload: list[dict[str, Any]] = []
        split_required: list[str] = []
        terminal_candidates: list[str] = []
        for core, (state, split_reasons, terminal_receipt_ref) in zip(
            candidate_cores, raw_states, strict=True
        ):
            core_with_hash = {**core, "plan_hash": plan_hash}
            candidate_digest = _digest(core_with_hash)
            idempotency_key = _digest(
                {
                    "plan_hash": plan_hash,
                    "candidate_key": core_with_hash["candidate_key"],
                    "candidate_digest": candidate_digest,
                }
            )
            if state == "split_required":
                split_required.append(core_with_hash["candidate_key"])
            elif state == "terminal":
                terminal_candidates.append(core_with_hash["candidate_key"])
            candidates_payload.append(
                {
                    **core_with_hash,
                    "candidate_digest": candidate_digest,
                    "idempotency_key": idempotency_key,
                    "state": state,
                    "split_reasons": sorted(split_reasons),
                    "terminal_receipt_ref": terminal_receipt_ref,
                }
            )

        split_required.sort()
        terminal_candidates.sort()
        subplan_payload = {
            "schema": COMPILED_WORK_PLAN_V2_SCHEMA,
            "status": "split_required" if split_required else "ready",
            "execution": "inert",
            "authority": "none",
            "plan_id": plan_id,
            "plan_ref": plan_ref,
            "plan_hash": plan_hash,
            "repository": repository,
            "accepted_base_sha": accepted_base_sha,
            "target_branch": target_branch,
            "placement": placement_dump,
            "candidate_count": len(candidates_payload),
            "pending_count": len(candidates_payload) - len(split_required) - len(terminal_candidates),
            "split_required": split_required,
            "terminal_candidates": terminal_candidates,
            "candidates": candidates_payload,
        }
        subplans.append(CompiledWorkPlanV2.model_validate(subplan_payload))

    bundle_hash = _digest(_bundle_digest_payload(bundle_id, bundle_ref, subplans))
    return DeliveryPlanBundleV1(
        bundle_id=bundle_id,
        bundle_ref=bundle_ref,
        bundle_hash=bundle_hash,
        subplans=tuple(subplans),
    )


def _target_error_code(error: ValueError) -> str:
    text = str(error)
    for code in (
        "delivery_plan_owner_namespace_mismatch",
        "delivery_plan_runtime_home_invalid",
        "delivery_plan_repository_invalid",
    ):
        if text == code:
            return code
    if text.startswith("delivery_plan_runtime_owner_not_trusted:"):
        return "delivery_plan_runtime_owner_not_trusted"
    if text.startswith("delivery_plan_target_not_trusted:"):
        return "delivery_plan_target_not_trusted"
    return "delivery_plan_target_verification_failed"


def _validation_errors_with_paths(exc: ValidationError) -> list[dict[str, object]]:
    formatted: list[dict[str, object]] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        formatted.append(
            {
                "field_path": ".".join(str(part) for part in loc),
                "type": str(err.get("type") or "validation_error"),
                "message": str(err.get("msg") or "Validation failed"),
            }
        )
    return formatted


def preflight_delivery_plan_payload(
    payload: object,
    *,
    trusted_policy: TrustedTargetPolicyV1 = DEFAULT_TRUSTED_TARGET_POLICY,
) -> dict[str, object]:
    """Classify and validate a delivery-plan, bundle, or external import envelope without mutating storage."""
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "kind": "invalid_payload",
            "materialize_allowed": False,
            "code": "delivery_plan_payload_not_mapping",
            "errors": [
                {
                    "field_path": "",
                    "type": "dict_type",
                    "message": "Expected mapping payload",
                }
            ],
        }
    schema = payload.get("schema")
    if schema == AUTODO_PLANFILE_IMPORT_SCHEMA:
        try:
            AutodoPlanfileImportMetadataV1.model_validate(payload)
        except ValidationError as exc:
            return {
                "ok": False,
                "kind": "external_import_envelope",
                "schema": AUTODO_PLANFILE_IMPORT_SCHEMA,
                "materialize_allowed": False,
                "code": "delivery_plan_import_envelope_invalid",
                "errors": _validation_errors_with_paths(exc),
            }
        return {
            "ok": False,
            "kind": "external_import_envelope",
            "schema": AUTODO_PLANFILE_IMPORT_SCHEMA,
            "materialize_allowed": False,
            "code": "delivery_plan_import_envelope_not_native",
            "errors": [
                {
                    "field_path": "schema",
                    "type": "import_envelope_not_native",
                    "message": (
                        "autodo.planfile-import/v1 is import metadata and cannot be "
                        "materialized as native subactor.compiled-work-plan/v1"
                    ),
                }
            ],
        }
    if schema == COMPILED_WORK_PLAN_SCHEMA:
        try:
            plan = CompiledWorkPlanV1.model_validate(payload)
        except ValidationError as exc:
            errors = _validation_errors_with_paths(exc)
            placement_unsupported = any(
                err["field_path"] in {"placement.home", "placement.runtime_owner"}
                or str(err["field_path"]).endswith(".placement.home")
                or str(err["field_path"]).endswith(".placement.runtime_owner")
                for err in errors
            )
            return {
                "ok": False,
                "kind": "native_compiled_work_plan",
                "schema": COMPILED_WORK_PLAN_SCHEMA,
                "materialize_allowed": False,
                "code": (
                    "delivery_plan_v1_placement_unsupported"
                    if placement_unsupported
                    else "delivery_plan_validation_failed"
                ),
                "errors": errors,
            }
        return {
            "ok": True,
            "kind": "native_compiled_work_plan",
            "schema": COMPILED_WORK_PLAN_SCHEMA,
            "materialize_allowed": True,
            "plan_id": plan.plan_id,
            "repository": plan.repository,
            "candidate_count": plan.candidate_count,
            "authority": plan.authority,
            "execution": plan.execution,
            "errors": [],
        }
    if schema == COMPILED_WORK_PLAN_V2_SCHEMA:
        try:
            plan_v2 = CompiledWorkPlanV2.model_validate(payload)
        except ValidationError as exc:
            return {
                "ok": False,
                "kind": "native_compiled_work_plan_v2",
                "schema": COMPILED_WORK_PLAN_V2_SCHEMA,
                "materialize_allowed": False,
                "code": "delivery_plan_validation_failed",
                "errors": _validation_errors_with_paths(exc),
            }
        try:
            trusted_policy.verify_target(plan_v2.repository, plan_v2.placement)
        except ValueError as exc:
            return {
                "ok": False,
                "kind": "native_compiled_work_plan_v2",
                "schema": COMPILED_WORK_PLAN_V2_SCHEMA,
                "materialize_allowed": False,
                "code": _target_error_code(exc),
                "errors": [
                    {
                        "field_path": "repository",
                        "type": "untrusted_target",
                        "message": str(exc),
                    }
                ],
            }
        return {
            "ok": True,
            "kind": "native_compiled_work_plan_v2",
            "schema": COMPILED_WORK_PLAN_V2_SCHEMA,
            "materialize_allowed": True,
            "plan_id": plan_v2.plan_id,
            "repository": plan_v2.repository,
            "candidate_count": plan_v2.candidate_count,
            "authority": plan_v2.authority,
            "execution": plan_v2.execution,
            "errors": [],
        }
    if schema == DELIVERY_PLAN_BUNDLE_SCHEMA:
        try:
            bundle = DeliveryPlanBundleV1.model_validate(payload)
        except ValidationError as exc:
            return {
                "ok": False,
                "kind": "delivery_plan_bundle",
                "schema": DELIVERY_PLAN_BUNDLE_SCHEMA,
                "materialize_allowed": False,
                "code": "delivery_plan_bundle_validation_failed",
                "errors": _validation_errors_with_paths(exc),
            }
        for index, subplan in enumerate(bundle.subplans):
            try:
                trusted_policy.verify_target(subplan.repository, subplan.placement)
            except ValueError as exc:
                return {
                    "ok": False,
                    "kind": "delivery_plan_bundle",
                    "schema": DELIVERY_PLAN_BUNDLE_SCHEMA,
                    "materialize_allowed": False,
                    "code": _target_error_code(exc),
                    "errors": [
                        {
                            "field_path": f"subplans.{index}.repository",
                            "type": "untrusted_target",
                            "message": str(exc),
                        }
                    ],
                }
        return {
            "ok": True,
            "kind": "delivery_plan_bundle",
            "schema": DELIVERY_PLAN_BUNDLE_SCHEMA,
            "materialize_allowed": True,
            "bundle_id": bundle.bundle_id,
            "subplan_count": len(bundle.subplans),
            "subplan_sizes": [subplan.candidate_count for subplan in bundle.subplans],
            "repositories": list(dict.fromkeys(subplan.repository for subplan in bundle.subplans)),
            "authority": bundle.authority,
            "execution": bundle.execution,
            "errors": [],
        }
    return {
        "ok": False,
        "kind": "unsupported_schema",
        "schema": schema,
        "materialize_allowed": False,
        "code": "delivery_plan_schema_unsupported",
        "errors": [
            {
                "field_path": "schema",
                "type": "unsupported_schema",
                "message": f"Unsupported delivery plan schema: {schema!r}",
            }
        ],
    }


__all__ = [
    "AUTODO_PLANFILE_IMPORT_SCHEMA",
    "COMPILED_WORK_PLAN_SCHEMA",
    "COMPILED_WORK_PLAN_V2_SCHEMA",
    "DEFAULT_TRUSTED_TARGET_POLICY",
    "DELIVERY_CHECKPOINT_SCHEMA",
    "DELIVERY_PLACEMENT_V2_SCHEMA",
    "DELIVERY_PLAN_BUNDLE_SCHEMA",
    "DELIVERY_PLAN_BUNDLE_STATE_SCHEMA",
    "DELIVERY_PLAN_RESUME_SCHEMA",
    "DELIVERY_PLAN_STATE_SCHEMA",
    "DELIVERY_SPLIT_SCHEMA",
    "TERMINAL_RECEIPT_SCHEMA",
    "TICKET_CANDIDATE_SCHEMA",
    "TICKET_CANDIDATE_V2_SCHEMA",
    "TRUSTED_TARGET_POLICY_SCHEMA",
    "AutodoPlanfileImportMetadataV1",
    "CompiledWorkPlanV1",
    "CompiledWorkPlanV2",
    "CrossPlanDependencyRefV1",
    "DeliveryCheckpointV1",
    "DeliveryPlacementV1",
    "DeliveryPlacementV2",
    "DeliveryPlanBundleV1",
    "DeliveryPlanSplitV1",
    "TicketCandidateV1",
    "TicketCandidateV2",
    "TrustedDeliveryTarget",
    "TrustedTargetPolicyV1",
    "WorkPlanTerminalReceiptV1",
    "compose_delivery_plan_bundle",
    "preflight_delivery_plan_payload",
]
