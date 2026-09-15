# Ticket 091: Record LLM latency cost and replayable receipts

- **ID**: ticket-091
- **Owner**: codex
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-15

## Goal and scope

Record bounded, replayable observations for Planfile LLM calls without storing
prompts, responses, credentials, or provider error text. The implementation
covers the LiteLLM/proxy client boundary and exposes a JSON export with
correlation IDs, model/fallback, latency, token usage, cost when supplied by a
provider, and retry outcome. It does not claim provider-specific billing
accuracy when a response omits cost metadata.

## Acceptance criteria

- [ ] AC-01: Each attempted backend call emits a schema-versioned receipt with
  a request digest, correlation ID, UTC timestamp, latency, status, and
  redacted error type only.
- [ ] AC-02: Usage and provider-reported cost are preserved as nullable values;
  missing usage/cost is not reported as zero.
- [ ] AC-03: Receipts can be loaded and exported into deterministic aggregate
  metrics without replaying a prompt or exposing response content/secrets.
- [ ] AC-04: Offline tests cover success, fallback, missing usage, failure,
  redaction, and export aggregation; no live provider is invoked.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.

## Evidence and limits

The receipt file is an ignored local evidence artifact selected by
`PLANFILE_LLM_METRICS_PATH`, or `.planfile/metrics/llm.jsonl` when the current
directory is a Planfile project. Records are append-only under a file lock and
contain hashes rather than content. Provider billing, server-side retries, and
calls made outside this client boundary remain unknown. A receipt is valid only
for its recorded model, request digest, dependency/runtime, and configuration.
