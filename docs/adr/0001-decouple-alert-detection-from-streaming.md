# ADR 0001: Decouple Alert Detection from Streaming Infrastructure

## Status
Accepted

## Context
`SchwabStreamClient` in `momentum_screener/schwab/stream_client.py` was a 1,345-line monolithic god object. It mixed WebSocket protocol management, Level 1 quote parsing, 1-minute candle aggregation, alert strategy evaluation (11 strategy rules), VWAP hysteresis, database calls (`alerts.should_fire_alert`), Redis pub/sub publishing, and Celery dispatch.

As a result, testing whether an alert strategy (e.g. `VWAP_CROSSOVER`, `BULL_FLAG`, `NEAR_HOD_RADAR`) evaluated correctly required standing up a live database pool, Redis connection, and Celery broker.

## Decision
We decouple alert detection into a pure, side-effect-free module `services/alert_detection_service.py`:
1. `evaluate_alerts(tick: QuoteTick, state: SymbolState, config: AlertConfig) -> tuple[list[AlertCandidate], SymbolState]` is a pure state transition function.
2. It takes strongly-typed dataclasses (`QuoteTick`, `SymbolState`, `AlertConfig`) and produces `AlertCandidate` objects.
3. It performs zero database, network, Redis, or Celery I/O.
4. Side-effects (cooldown check DB calls, alert table persistence, Redis pub/sub, Celery dispatch) are handled downstream by an `AlertDispatcher` adapter inside `stream_client.py`.

## Consequences
### Positive
- All 11 alert strategies can be unit-tested in milliseconds with pure dict/dataclass inputs and zero mocks.
- `stream_client.py` shrinks significantly and acts strictly as a transport and dispatch adapter.
- Alert rules concentrate in a single deep module (`services/alert_detection_service.py`).

### Negative / Trade-offs
- Downstream adapter must explicitly map pure `AlertCandidate` outputs to DB/Redis/Celery calls.
