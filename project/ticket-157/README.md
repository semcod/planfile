# Ticket 157: Web conversational interface for plans and tasks

- **ID**: ticket-157
- **Owner**: human:tom
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-27
- **Authorization**: SESSION_EXECUTION_AUTHORIZATION

## Goal and scope

Implement an interactive conversational web interface in planfile's web service (`planfile serve` / `http://localhost:8000/`) allowing users to interact with plans, sprints, and tasks using natural language and voice:
1. Web Assistant panel in `_dashboard_html()` with real-time Option Network autocomplete pills.
2. Voice recognition (Web Speech API) toggle allowing hands-free speaking to tasks and plans.
3. Conversational query extensions in `DSLExecutor` (status of plans, blocked tasks, next tasks, high priority).
4. Direct integration with `/query` and WebSocket for instant status updates.

## Acceptance criteria

- [ ] AC-01: Conversational Assistant panel rendered in planfile dashboard with voice button and option network pills.
- [ ] AC-02: `DSLExecutor` answers conversational queries (blocked tasks, next task, sprint status, high priority) in Polish and English.
- [ ] AC-03: Regression tests in `tests/test_conversational_web.py` pass.
- [ ] AC-04: Governance checks pass (`./project/governance-check.sh`).

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
