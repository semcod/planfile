# Agent plan — ticket-081

The implementation will set the local synthetic ticket key in the persisted
`id` field and mark external imports as backlog records. The same defaults will
be applied when refreshing a legacy record that is missing them. Tests will
exercise both paths through the existing sync helpers and confirm that the
backend-specific mapping remains intact.

Execution authorization is recorded in `README.md`. No user-owned intake file
is created or edited.
