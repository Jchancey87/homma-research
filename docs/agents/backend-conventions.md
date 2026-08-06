# Backend Conventions (RFC-001)

## Router Layer Rules

Routers are thin. An endpoint may only: (a) parse + validate input, (b) call one service function, (c) format the response or translate domain exceptions to HTTP errors.

| Forbidden in routers | Where it belongs |
|---|---|
| Business logic (indicator math, FILTER-aggregate SQL, MFE/MAE, win-rate) | `services/<name>_service.py` |
| Raw SQL strings | `services/<name>_service.py` or `fastapi_app/db/<name>.py` |
| External API calls (Schwab, FMP, SEC, Massive, yfinance) | `services/schwab_client.py` (facade) or `services/<source>_service.py` |

If an endpoint exceeds ~30 lines, extract a service.

Routers obtain a `db` via `Depends(get_db)` and pass it to a service — never issue queries directly.

## Testing Split

- **Unit tests** — pure transforms (no DB / no HTTP): `tests/test_<service>.py`
- **Integration tests** — HTTP surface only: `tests/test_<router>.py`

Analytics services own their own unit tests.

## Reference Implementations

- [services/chart_data_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_data_service.py)
- [services/alerts_analytics.py](file:///home/jackc/projects/homma-research/backend/services/alerts_analytics.py)
- [services/continuation_analytics.py](file:///home/jackc/projects/homma-research/backend/services/continuation_analytics.py)
