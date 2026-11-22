# Ticket 317: Isolate per-project dotenv values in IntegrationConfig to prevent cross-repo GITHUB_TOKEN pollution in fleet sync

- **ID**: ticket-317
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-21
- **Authorization**: `SESSION_EXECUTION_AUTHORIZATION` (user request to diagnose and fix Planfile-to-GitHub synchronization across all projects).

## Goal and scope

During `planfile sync fleet ~/github`, `discover_fleet_repositories()` instantiates `IntegrationConfig(str(repo))` across hundreds of repositories in one Python process. Previously, `IntegrationConfig.load_dotenv()` called `dotenv.load_dotenv(env_file)`, which globally mutated `os.environ` — leaking a stale `GITHUB_TOKEN` from one repository's `.env` file into every subsequent repository and causing `401 Bad credentials` failures across the entire fleet even when `gh auth token` is valid (`HTTP 200`).

Replace global `load_dotenv()` with per-instance `dotenv_values()` stored in `self._dotenv_vars`, preserving `os.environ` > project `.env` > `gh auth token` precedence without mutating `os.environ`.

## Acceptance criteria

- [x] AC-01: `IntegrationConfig(repo)` reads `<repo>/.env` into an instance-local mapping without mutating `os.environ`.
- [x] AC-02: Variable expansion and GitHub/OneDev integration lookups honor `os.environ` first, then the instance's own `.env`, then `gh auth token` fallback for GitHub.
- [x] AC-03: Unit test proves a stale `.env` `GITHUB_TOKEN` in repo A never leaks into `os.environ` or repo B; ruff, pytest, and `./project/governance-check.sh --base origin/main` pass.
