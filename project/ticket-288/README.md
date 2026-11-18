# Ticket 288: Support GitHub issue templates when creating issues

- **ID**: ticket-288
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-18

SESSION_EXECUTION_AUTHORIZATION: user requested "wykonaj zalegle zadania https://github.com/semcod/planfile/issues"; resolves semcod/planfile#6 with protected Validator publication.

## Goal and scope

Implement support for `integrations.github.issue_template` when creating GitHub issues via `GitHubBackend.create_ticket` (`planfile/sync/github.py`) and project-relative template path resolution in `IntegrationConfig.get_integration_backend` (`planfile/integrations/config.py`). Support inline templates, Markdown templates with optional YAML frontmatter, and GitHub YAML issue forms while preserving `<!-- planfile:description:start -->...<!-- planfile:description:end -->` managed-description readback, round-trip updates, and fail-closed template validation.

## Acceptance criteria

- [x] AC-01: Configured inline, Markdown (with YAML frontmatter), and GitHub YAML issue form templates are resolved relative to `project_dir` (and fail closed on missing/invalid/escaping paths during `preflight` and `create_ticket`).
- [x] AC-02: Rendered issues preserve the delimited `planfile:description` section once, pass `outbound._verify_remote_readback`, and retain template prose across subsequent updates.
- [x] AC-03: Focused tests (`tests/test_github_issue_templates.py`), existing sync regressions, Ruff, and `./project/governance-check.sh` pass cleanly.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
