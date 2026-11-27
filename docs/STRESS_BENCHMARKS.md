# Repeated deep-book stress measurements

The original release recorded one 2,000-command mixed workload. That case reached a small resting book. This extension adds distinct deep-book, reverse-cancellation, and multi-maker sweep workloads and retains all repetitions instead of reporting one favorable run.

Run:

```sh
python3 -m scripts.stress_benchmark --count 10000 --repeats 3
```

The recorded run has 24 independent processes/stores: four workloads, two storage modes, three repetitions. Raw samples, machine/compiler metadata, source hash, deterministic workload/final-state checksums, and ranges are in [stress-benchmark.json](stress-benchmark.json).

## Recorded results

Values below are medians of three run-level measurements. The p99 column is the median of each run's p99, not a pooled percentile or confidence bound.

| Profile | Storage | Peak resting orders | Median commands/s | Median run p99 (µs) |
| --- | --- | ---: | ---: | ---: |
| mixed | memory | 30 | 730,313 | 5.125 |
| mixed | durable | 30 | 20,862 | 104.125 |
| deep | memory | 10,000 | 987,760 | 3.625 |
| deep | durable | 10,000 | 21,353 | 103.125 |
| cancel-burst | memory | 5,000 | 1,225,600 | 1.875 |
| cancel-burst | durable | 5,000 | 21,343 | 114.375 |
| sweep | memory | 5,000 | 753,369 | 8.125 |
| sweep | durable | 5,000 | 21,200 | 127.083 |

Machine: macOS-15.7.3-arm64-arm-64bit-Mach-O / arm64. Compiler: Apple clang version 17.0.0 (clang-1700.0.13.5).

## What is measured

- `mixed`: the existing seed-42 four-participant limit/IOC/cancel flow.
- `deep`: 10,000 bids at distinct prices. This exercises a growing ordered map and 10,000 price levels.
- `cancel-burst`: build 5,000 resting orders over 32 levels, then cancel in reverse insertion order.
- `sweep`: build 5,000 unit asks, eight per price level, then execute crossing eight-unit IOC buys. Later IOC requests see an empty book.

Per-command service latency includes validation, matching, response JSON serialization, and deduplication storage. Durable mode adds checksumming and journal open/append/fsync/close. Overall throughput also includes loop bookkeeping. Workload generation, TSV parsing, Python, IPC, HTTP, final state hashes, and conservation checks are outside the timed section.

Each repetition starts a fresh process and store. There is no warmup, CPU affinity, allocator isolation, network transport, live feed, production load, or constant-memory guarantee. The core retains responses and trades. These are machine/workload-specific measurements, not exchange latency or proof of performance superiority.

The fixed profiles produced identical input and final-state checksums across storage modes and repetitions, with cash and inventory conserved. FNV-64 identifies accidental differences; it is not a cryptographic proof. A 127-command stream from each new profile is also cross-checked against the independent Python matcher, including FIFO/sweep results; separate tests cover minimal counts and even-sized depth outcomes.

## Verification and next useful work

The full suite now has 20 Python tests and three frontend checks. New workload tests cover independent-reference agreement, durable/memory state identity, depth, conservation, minimal counts, and invalid profiles. Sanitizer runs exercise all four profiles.

Further high-value work would measure retained-history memory and recovery cost as command count grows, or implement tested journal compaction. More presentation changes would add less evidence about the engine itself.
