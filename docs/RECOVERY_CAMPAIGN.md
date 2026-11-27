# Bounded recovery campaign

The deterministic campaign extends the original single-command crash checks into mixed sessions with resting orders, partial fills, cancellations, request deduplication, snapshots and later recovery. Each response and recovered full state is compared with the independent Python matching implementation. Cash and inventory conservation are checked after every accepted command.

## Recorded run

Five seeded streams, 180 unique commands each:

| Event | Count |
| --- | ---: |
| Accepted commands | 900 |
| Process exit immediately before journal append | 19 |
| Process exit after durable journal write, before apply/acknowledgment | 21 |
| Forced process kills after an acknowledged command | 45 |
| Materialized snapshots | 40 |
| Duplicate original-ID retries after a lost acknowledgment | 120 |
| Restarts including final cold reopens | 90 |
| Full-state reference comparisons | 945 |

Before-journal exits recover the prior state. After-journal exits recover the persisted command even though no response was received. Retrying the original request ID returns the original result without adding trades or another sequence number. This is why a disconnected client cannot safely generate a fresh request ID and assume the command was never accepted.

A separate byte-prefix campaign tested all 61 prefixes (including zero bytes and the complete record) of a 60-byte final candidate journal record. Incomplete unacknowledged tails were removed, the prior committed prefix was recovered, and the original-ID retry converged to the independently computed complete state. A complete record was recovered and deduplicated.

[Raw run environment, source hash and counts](recovery-campaign.json).

## Reproduce

```sh
python3 scripts/recovery_campaign.py
python3 -m unittest discover -s tests -v
```

The script uses temporary stores and writes a fresh measured report. CI uses two shorter seeded streams plus the complete byte-prefix matrix to check the same properties on every change.

## Limits

These are finite deterministic process-exit/kill tests and synthetic file-prefix fixtures. They do not simulate machine power loss, lost storage-device cache, disk corruption after a completed fsync, short writes, injected fsync failures, or arbitrary concurrent schedules. The byte-prefix fixture represents an unacknowledged candidate tail; it is not presented as proof that acknowledged durable records can be lost and safely ignored. Checksums detect accidental corruption; no authenticated-storage claim is made. A larger seed set does not prove the absence of all recovery bugs.
