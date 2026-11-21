# Ticket 314: Expose privacy-safe urtlog bridge health summary on GET /health

- **ID**: ticket-314
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-21
- **Authorization**: `SESSION_EXECUTION_AUTHORIZATION` (user continuation to unify privacy-safe `urtlog_bridge` health reporting across `planfile`, `heyasa`, `willgui`, and `oqllm-proxy` and publish via protected delivery).

## Goal and scope

1. Add privacy-safe, read-only `bridge_health_summary(state_dir=None)` to `planfile/urtlog_bridge.py` (consistent with `oqllm-proxy`, `willgui`, and `heyasa`) without leaking filesystem paths.
2. Include `"urtlog_bridge": bridge_health_summary()` in `GET /health` in `planfile/api/server.py`.
3. Add unit tests in `tests/test_urtlog_bridge.py` covering both `bridge_health_summary()` and `GET /health` (including zero path leakage).

## Acceptance criteria

- [x] AC-01: `bridge_health_summary()` returns privacy-safe boolean readiness (`advisory_only=True`, `execution_allowed=False`, `max_decision_slice_bytes=600`, `enabled`, `state_dir_configured`, `urtlog_importable`) without leaking `URTLOG_STATE_DIR`.
- [x] AC-02: `GET /health` in `planfile/api/server.py` exposes `"urtlog_bridge"` without leaking paths.
- [x] AC-03: Unit tests, ruff lint, and `./project/governance-check.sh --base origin/main` pass.
