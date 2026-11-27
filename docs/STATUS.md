# Status

Standalone release complete.

Desktop checkout: /Users/vhui/Desktop/exchange-matching-engine
Origin: https://github.com/victorhuii/exchange-matching-engine.git

Read PROJECT_SCOPE.md for release acceptance. This project is separate from MarketLab and uses its own C++ matching implementation.

## Completed

- C++20 ordered price levels, FIFO queues, indexed cancellations, limit/IOC orders, partial fills and integer balances.
- Canonical request deduplication, checksummed fsync journal, materialized atomic snapshots, single-writer lock and deterministic recovery.
- Plain local workbench with order entry, book depth, trades, balances, isolated replay, recovery comparison and export.
- Independent Python reference; 1,200-command comparison; crash, corruption, tombstone and original-response recovery checks.
- Recorded 2,000-command memory/durable benchmark with compiler, hardware, build flags and timing exclusions.
- GitHub README and portfolio Markdown; four PNGs and editable SVGs; recorded matching/recovery demo; CI.

## Verification

20 Python tests and 3 Node frontend checks passed. JavaScript syntax check passed. A 2,000-command C++ run completed with address and undefined-behavior sanitizers. Figures were visually inspected; Markdown links and image dimensions are checked during packaging.

Browser access host is unavailable. Actual browser layout/screenshot QA is not verified. The figures are generated evidence charts and an actual engine trace, not UI screenshots. CI is configured; remote results should be checked on GitHub Actions.

## Efficient continuation

Read README.md and this status, then only the relevant source. Start with python3 -m exchange.server (port 8766); compilation is automatic. No runtime package dependencies. Use a new --data directory for a fresh durable session.

Optional figure regeneration requires requirements-assets.txt. Runtime state/build outputs are ignored. Future improvements should start with browser QA, deeper-book/repeated benchmarks, memory profiling or tested journal compaction rather than unsupported production claims.

## Follow-up engineering review

Added repeated 10,000-command mixed, deep-book, reverse-cancellation, and multi-maker sweep measurements. All 24 runs retain raw timings and matching workload/state identities. Peak book depth now reaches 10,000 orders/price levels. See STRESS_BENCHMARKS.md for timing boundaries, source identity, and limitations. All four profiles are exercised under sanitizers.
