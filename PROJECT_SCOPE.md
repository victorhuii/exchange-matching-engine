# Exchange Matching Engine · release scope

Build a standalone exchange simulator that demonstrates matching correctness, durable command handling, deterministic recovery and measurable systems performance. This is the software engineering companion to MarketLab, with its own implementation and repository.

## Requirements

- C++20 single-instrument price-time matching using ordered price levels, FIFO queues and indexed cancellation.
- Limit and IOC orders, cancellations, partial fills, resting-price execution, participant balances and request deduplication.
- Explicit input rules and deterministic cancellation/fill ordering.
- Checksummed, fsync-backed command journal; materialized atomic snapshots; recovery from snapshot plus subsequent journal records; one-writer process lock.
- Python standard-library local HTTP bridge, seeded participants and a clean browser view for order entry, depth, trades, balances, replay and recovery.
- Independent Python reference comparison, invariant checks, duplicate/invalid input tests and crash/failure recovery tests.
- Reproducible core-versus-durable benchmark with actual throughput, latency, hardware, order mix and limitations.
- Polished GitHub README/metadata; portfolio Markdown, generated demo pictures and download bundle; CI and compact continuation context.

## Boundaries

Local simulation only. No exchange credentials, live trading, market data subscriptions or profitability claims. One instrument, one matching thread, one writer; integer ticks and quantity units. No market orders, auctions, hidden liquidity, replace orders, funding checks, self-trade prevention or network latency claims. A bounded retained command history favors an inspectable recovery model over a production memory footprint.

## Acceptance

The app builds with a C++20 compiler and runs on macOS/Linux without application package dependencies. Correctness, API and recovery checks pass. Performance claims are generated from a recorded workload. Portfolio images disclose whether they are result figures or UI captures. Each completed milestone is pushed to the requested origin with a simple lowercase message.
