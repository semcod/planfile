# Ticket 199 - Voice sprint digest endpoint

## Objective
Implement read-only `GET /api/voice-digest` endpoint in FastAPI server producing a bounded natural-language sprint summary suitable for TTS.

## Requirements
- Explicit sprint selection via query parameter `sprint` (default: `"current"`).
- Exact counts for total tickets, done/completed, in-progress/active, blocked, open/todo.
- Empty sprint handling (returns 0 counts and an informative summary rather than crashing).
- Formats a natural-language digest string suitable for Text-to-Speech (TTS) reading.
- Read-only: does not modify sprint or ticket states.
- High test coverage with dedicated test suite `tests/test_api_voice_digest.py`.
