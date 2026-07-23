# Formal baseline findings

## Measured result

- Agent-tree tokens: `31,381,550`
- Wall time: `3,002,429 ms`
- Hidden quality: `30/100` (`6/20` assertions)
- Critical gate: failed

## Quality regression

The Q2 repair introduced new required config reads (`max_sessions`, upload/response limits, TTL and device ID length). The frozen evaluator deliberately starts the backend with the original four-field dynamic override contract. The final backend therefore raises `KeyError` inside request processing and converts fourteen protocol/integration checks to `internal processing failure`.

Public unit, E2E and pipeline verify remained green because they loaded the expanded full `config.json`. This is direct evidence that fix validation must replay the original minimal-config contract and frozen acceptance smoke after each QA repair batch.

## Token evidence

| Phase | Tokens |
|---|---:|
| Main executor | 8,885,391 |
| Q1 intent reviewer + follow-up | 5,403,836 |
| Q2 correctness reviewer + follow-up | 7,500,284 |
| Q3 evidence reviewer | 9,592,039 |
| Total | 31,381,550 |

The original QA flow reused Q1 and Q2 reviewer sessions for incremental follow-up turns. Those turns retained the full reviewer context and materially increased the measured tree. Q3 also consumed a large context while enumerating evidence gaps that could not be repaired after the shared three-round limit.
