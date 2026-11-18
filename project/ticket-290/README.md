# Ticket 290: Enforce trusted project_dir boundary for GitHub issue templates

- **ID**: ticket-290
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
- **Created**: 2026-11-18

SESSION_EXECUTION_AUTHORIZATION: user requested "wykonaj zalegle zadania https://github.com/semcod/planfile/issues"; hardens semcod/planfile#6 trusted template containment boundary per PR #350 Validator advisory finding.

## Goal and scope

Prevent repository-supplied `integrations.github.project_dir` configuration from overriding the trusted `IntegrationConfig.directory` boundary when instantiating `GitHubBackend` in `planfile/integrations/config.py`, and add a regression test in `tests/test_github_issue_templates.py` proving untrusted external template targets fail closed.

## Acceptance criteria

- [x] AC-01: `IntegrationConfig.get_integration_backend("github")` always sets `config["project_dir"] = str(self.directory)` after merging `config` so repository configuration cannot override the trusted root.
- [x] AC-02: Regression test `test_integration_config_ignores_untrusted_project_dir_override` passes alongside `tests/test_github_issue_templates.py`, Ruff, `./project/governance-check.sh --base origin/main`, and `wellman check`.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
