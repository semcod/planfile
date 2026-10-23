# ticket-236: Advisory radar for direct ticket creation

- **ID**: ticket-236
- **Owner**: agent:codex
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: continue the existing user-authorized issue #279 and native execution ticket PLF-19711 through Subactor, Willman and protected publication. Reuse the native allocation and preserve its implementation commit. The native writer ended; a fresh protected observation confirmed no checkout owners before the fenced continuation.

Single and bulk creation optionally append bounded advisory metrics. The original description stays intact; tool failures never prevent otherwise valid ticket creation. Radar grants no execution, ownership, review or merge authority.

## Acceptance criteria

- [x] AC-01: Shared creation preparation persists validated complexity, score, estimated effort and split recommendation before generating new journal payloads.
- [x] AC-02: Preserve human descriptions verbatim and append at most one advisory block, bounded to 512 characters; existing producer blocks remain unchanged.
- [x] AC-03: Missing executables, failures, deadlines, excessive output and invalid or mismatched assessments leave descriptions unchanged and creation available.
- [x] AC-04: Assessment cannot change lifecycle, execution, priority, dependencies, ownership or delivery authority. Existing tracker transport carries advisory descriptions.
- [x] AC-05: Both storage backends, creation deduplication, bulk allocation, journaling and credential redaction pass their relevant regressions and the managed governance gate.

## Implementation

The private adapter invokes the existing optional ticket-radar executable without a shell or output artifacts. Assessment has a one-second deadline per ticket and a five-second aggregate bulk deadline, with at most 65,536 captured output bytes. Only schema-checked scalar metrics with the matching ticket identity enter the advisory block.

The required operational-journal regression now exercises both an unavailable radar and a valid assessment, checking that appended advisory text preserves nested credential redaction. This adds one existing test file to the accepted scope and raises the implementation-file budget from three to four, within the unchanged S profile. No new runtime dependency or product objective is introduced.

Process cleanup is verified through closure of real pipes, including inherited writer handles, without Linux-specific process-state files or an omitted platform case. Credential examples use explicit inert placeholders.

## Validation and continuation

The original native attempt recorded 63 passing radar tests, one incompatible legacy description assertion, and a governance refusal caused by machine-local paths in its ticket README. Original logs and the previous README remain in external continuation receipts. Those historical results do not establish publication readiness.

Current continuation validation:

- Approved Wellman execution, explicit same-repository primary virtual environment, and the native governance plugin enabled: `python -m pytest tests/test_operational_dsl.py tests/test_ticket_radar.py -q` — 68 passed. Both radar availability branches preserve credential redaction.
- Ruff on all four material source/test paths — passed.
- `project/governance-check.sh --base origin/main` — passed with zero errors and warnings.
- Validator publication preflight using the actual deployed OneDev configuration — configuration checked, no findings. Runtime and publication verification remain pending; configuration coverage grants neither test success nor merge authority.

No governance plugin, required check or regression case was disabled in this continuation. Original OneDev verification and independent exact-head Validator approval remain required after publication; keep this ticket IN_PROGRESS through protected merge.

External continuity: receipt:ticket236/source-lease and receipt:ticket236/validation-evidence. The original Willman request and its frozen records remain preserved; this continuation creates no competing allocation.
