---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "planfile-321-activation",
  "kind": "analysis",
  "version": 1,
  "title": "Planfile #321 activation and the SQLite index finding",
  "status": "implemented",
  "owner": "semcod/planfile",
  "created": "2026-10-30",
  "updated": "2026-10-30",
  "review_after": "2026-11-30",
  "source_revision": "57d085698cd2a92f6da7bf69a4e6a270571aec0e",
  "affected_repositories": [
    "semcod/planfile"
  ],
  "evidence": [
    "https://github.com/semcod/planfile/pull/321",
    "https://github.com/semcod/planfile/issues/317",
    "https://github.com/semcod/planfile/issues/313"
  ]
}
---

# Planfile #321 activation and the SQLite index finding

<!-- docs:section purpose -->
## Purpose

Record, in the owning repository, what was observed when planfile PR #321 was
activated in production and what actually reduced the resource use. Moved from
an operator-local note; it grants no deployment authority.

<!-- docs:section scope -->
## Scope

Production planfile service on 2026-10-30. Covers #321 (connection handling and
retryable store-lock refusals), the SQLite ticket index and the later Compose
deployment. Out of scope: PR #322 (status-position index), whose native
migration is recorded separately in
`/home/tom/.local/state/ecosystem-throughput-20261030/planfile262-live-migration-receipt.json`.

<!-- docs:section evidence -->
## Evidence

- Source: #321 merged as 57d0856 by the independent Validator. Wheel 0.1.127,
  sha256 612120c33b3eb82544481ccc2c09d6cddc99e72f32ebffa3021bd18c848fc30d
  (192 files verified).
- Before: container about 182-190% CPU and 8-10.9 GiB; workers held only 20-25
  open file descriptors and none were SQLite.
- Canary on a copy of the data (isolated port, 2 CPU / 12 GiB): 2,771 reads and
  32 writes, 0 failures, worker RSS flat at 400-630 MiB.
- Activation at about 14:50Z: standalone replacement container, same address,
  alias `planfile`, port 18769 and volumes; other clients resumed within about
  90 s. Immediately afterwards CPU and memory were again high (about 184% CPU,
  4.7-5.7 GiB).
- Cause measured on the live service: `GET /tickets?sprint=all&offset=0&limit=1000&view=operational`
  took about 35 s and returned 6.1 MB, against 0.05 s for `sprint=current`.
  `planfile storage status` reported `"index": "none"`; the index file existed
  (487 MB, 20,925 tickets) but was disabled and stale, so #321 had no SQLite
  connections to close.
- Canary with the index enabled (`planfile storage index-enable --project /workspace`,
  about 125 s): the same call dropped from 24.5 s to 0.01-1.7 s, idle CPU 7.5%.
  Soak at about 20 req/s (about 50 times production) plus 33 writes: 3,596 reads,
  p50 0.08 s, p95 0.64 s, 7 typed 503 on the full `status=open` list during
  repair and 12 background lock timeouts that self-recovered.
- Later: the platform owners replaced the standalone container with the
  `subactor-platform` Docker Compose deployment at 16:21Z. The SQLite index was
  enabled in production at 17:12:23Z by an actor that was not identified (no
  config-change record). Measured afterwards: `sprint=all` 0.15-0.33 s,
  container about 29% CPU and 2.2 GiB, 21,016 tickets, index current.

<!-- docs:section content -->
## Content

The large drop in CPU, memory and read latency followed enabling the SQLite
index, not #321 alone. #321 supplies the connection handling and the retryable
503 for a busy store lock that make the index safe under concurrent writes; the
two work together. What the index change touches: one config key
(`store.storage.index = sqlite` in `.planfile/config.yaml`) and the disposable
projection `.planfile/index/tickets.sqlite3`, rebuilt from the YAML and evidence
journals. Ticket, sprint and evidence YAML, the container, image, network and
volumes are untouched. Undo: `python -m planfile storage index-disable --project /workspace`
(sets the key back to `none`, keeps the database file).

<!-- docs:section limitations -->
## Limitations

- A minutes-long canary cannot prove an hours-long memory leak is gone.
- The actor that enabled the index in production is unknown.
- A previous attempt on 2026-10-29 was refused with
  `ticket_index_sources_changed_during_rebuild` under write churn.
- Index freshness and contention were observed at a point in time; current
  configuration alone does not prove either.
- The standalone activation script that did the first replacement has been
  retired (it refuses a Compose-managed container); its original note is
  operator-local and is not reproduced here.

<!-- docs:section next_actions -->
## Next actions

- Owners decide whether to summarize this in planfile#317 and #313; nothing was
  posted there.
- Remove the unused runtime tree
  `~/.local/share/planfile/runtime/57d085698cd2-ticket260-wheel0.1.127` when
  convenient; production no longer mounts it.
