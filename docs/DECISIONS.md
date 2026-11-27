# Design choices

Exchange Matching Engine — implementation rationale and tradeoffs.

| Choice | Why it fits this project | Cost or boundary |
| --- | --- | --- |
| Integer ticks and quantities | Make matching and conservation checks deterministic. | No multi-currency or fractional-price venue model. |
| Price levels, FIFO queues and indexed cancels | Expose price priority and arrival priority in explicit data structures. | One instrument; no live network or queue-position claim. |
| Journal before acknowledgment and original request IDs | Recover accepted commands and return the original response after a lost acknowledgment. | Retained history grows; filesystem durability assumptions still apply. |

## Evidence and scope

Independent reference and bounded mixed-session recovery campaign. Synthetic local exchange; measured throughput is not production venue latency.

Ownership: **Original implementation**. Attribution and source notices remain in the [README](../README.md).

See [architecture](ARCHITECTURE.md) and [portfolio notes](PORTFOLIO.md) for implementation details and existing evidence. This documentation update does not add a new benchmark or training run.
