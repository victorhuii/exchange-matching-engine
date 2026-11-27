# Exchange Matching Engine

Standalone systems portfolio project. Read PROJECT_SCOPE.md and docs/STATUS.md first.

- One instrument, integer prices/quantities, deterministic price-time priority.
- Keep the browser UI simple. Clearly label synthetic orders and measured performance.
- Preserve journal acknowledgment, deduplication and recovery guarantees.
- Verify with python3 -m unittest discover -s tests -v and node --check web/app.js.
- Use lowercase, simple commit messages and push each completed milestone.
- No live trading, paid APIs, external AI calls or unverified production claims.
