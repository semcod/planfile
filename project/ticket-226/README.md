# Ticket 226: Extract storage bottlenecks into reusable Rust package planfile-native

- **ID**: ticket-226
- **Owner**: agent:antigravity (requested by the repository owner)
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-10-19

## Goal and scope

Move the measured storage bottleneck of planfile into a reusable Rust package that planfile
imports optionally, keeping YAML as the single source of truth and the on-disk format unchanged.

Decisions confirmed by the owner: new crate inside this repository
(`packages/planfile-native`), scope = write path (YAML dump, JSON mirror, atomic write) plus
mirror normalization, YAML output byte-identical to PyYAML `CSafeDumper` with a Python fallback,
data-plane/data-gateway handled as an aligned storage-kernel contract (no event-sourcing
migration).

Baseline profile (3000 tickets, one 7.9 MB `current.yaml`): every mutation spent ~95% of its time
in `yaml.dump` (pure Python representer over ~340k nodes) plus the `_json_safe` walk and
`json.dumps` for the mirror. The existing `planfile-io` wheel is not a usable substitute:
`fastio.read_yaml_native` is dead code, its mirror schema (`mtime_ns`) is incompatible with
planfile's (`yaml_mtime_ns`), and its `serde_yaml` output formats differently from PyYAML.

## Acceptance criteria

- [x] AC-01: `planfile_native.dump_yaml` is byte-identical to `yaml.dump(..., CSafeDumper,
  default_flow_style=False)` for curated edge cases and 4800 random documents, with and without
  `allow_unicode` (`packages/planfile-native/tests/test_parity.py`).
- [x] AC-02: Unsupported values (subclasses, sets, non-str keys, shared containers that PyYAML
  anchors, cycles, lone surrogates) raise `Unsupported` before any file is touched; planfile then
  uses PyYAML (`tests/test_native_integration.py`).
- [x] AC-03: `PLANFILE_NATIVE=off|auto|verify` and `PLANFILE_NATIVE_FSYNC` switch behavior at
  runtime; unknown values fail closed to `off`; no policy is hardcoded in the crate.
- [x] AC-04: Full planfile suite passes with `PLANFILE_NATIVE=verify` (every write compared with
  PyYAML): 1292 passed, 6 skipped. `tests/test_release_availability.py::test_release_metadata_
  matches_published_offline_snapshot` fails identically on an unmodified tree and is unrelated.
- [x] AC-05: Same-workload benchmark (`packages/planfile-native/benches/bench_store.py 3000`,
  2 runs x 7 samples each, medians):

  | operation | PLANFILE_NATIVE=off | auto | speed-up |
  |---|---|---|---|
  | update_ticket | 695 ms | 162 ms | 4.3x |
  | create_ticket | 678 ms | 148 ms | 4.6x |
  | list_tickets (warm) | 176 ms | 139 ms | 1.3x |
  | get_ticket (warm) | 34 ms | 24 ms | 1.4x |
  | list_tickets (cold, no mirror) | 1014 ms | 871 ms | 1.2x |

- [ ] AC-06: Governance gates (`./project/governance-check.sh`, `wellman check`) pass.

## Remaining bottlenecks (follow-up, not in this ticket)

- Each mutation still `json.loads` the 8 MB mirror about twice (~40 ms) and rebuilds index and
  evidence state in Python; a byte-offset index would let `get_ticket` avoid parsing a whole
  sprint.
- Per-ticket projection (`_project_ticket_evidence`, Pydantic validation) dominates warm
  `list_tickets`.
- Cold YAML parse remains PyYAML/libyaml; a native parser must reproduce YAML 1.1 resolution
  (`yes`/`no`, sexagesimal ints, timestamps) before it can replace it safely.
- A `docs/` performance report and a `wellmanifest/performance` plan record belong to the
  integration workstream (`docs/**`), which this application ticket does not own.

## Rollback

Set `PLANFILE_NATIVE=off` (no data migration is involved because files are byte-identical), or
revert this ticket's commit.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose and raw command
logs are not required delivery output.
