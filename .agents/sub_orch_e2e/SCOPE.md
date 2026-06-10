# Scope: E2E Test Suite (Milestone 1)

## Architecture
The E2E test suite validates the entire real-time momentum alert pipeline and performance journaling from end to end using opaque-box testing. It runs within a test environment and verifies:
1. **Schwab Stream Alert Engine (R1)**: Feeding simulated ticks/candles via mock streaming clients, checking that triggers (HOD breakout, RVOL, VWAP ATR, Post-halt) behave correctly.
2. **Telegram Alert Delivery (R2)**: Intercepting Celery payloads and verifying they match the detailed Markdown format (with TV links and stats).
3. **Expectancy Feedback Backend & UI (R3)**: Seeding TimescaleDB, querying `/api/alerts/daily-summary` for forward returns and excursions, and verifying scorecard computation logic.

The test suite will run using `pytest` for the backend and api integration tests, and a Python-based test runner that drives the database seeding, streaming mocks, Celery verification, and UI mock validations.

## Code Layout
- `backend/tests/e2e/` - Directory for E2E tests and helper modules
- `backend/tests/e2e/test_runner.py` - Test runner orchestrating all Tiers 1-4 tests
- `backend/tests/e2e/mock_stream_generator.py` - Helper to simulate Level 1 streaming quotes
- `backend/tests/e2e/test_cases.py` - Python test cases implementation
- `TEST_INFRA.md` - E2E test infrastructure specification and setup guide
- `TEST_READY.md` - Verification results and coverage check (published upon completion)

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| M1.1 | Setup E2E Test Infra | Write `TEST_INFRA.md`, build streaming mocker, Celery interceptor, and DB test fixtures. | None | PLANNED |
| M1.2 | Implement Tier 1 (Feature Coverage) | Write >=20 tests covering all basic functionality of R1, R2, and R3. | M1.1 | PLANNED |
| M1.3 | Implement Tier 2 (Boundaries) | Write >=20 boundary and corner cases for R1, R2, and R3 features. | M1.2 | PLANNED |
| M1.4 | Implement Tier 3 & 4 (Combinations/Scenarios) | Write >=4 Tier 3 and >=5 Tier 4 tests for complex interactions and real workloads. | M1.3 | PLANNED |
| M1.5 | Verify & Publish TEST_READY.md | Execute full test suite, verify compilation/reporting status, and write `TEST_READY.md`. | M1.4 | PLANNED |

## Interface Contracts
- **Live Quotes Stream**: Schwab Level 1 quote updates mapped to `SchwabStreamer.on_level1_equity_message`.
- **Redis Pub/Sub**: Channel `screener:alerts` publishes alert payloads.
- **Celery Task**: `fastapi_app.tasks.alerts.send_telegram_alert_task` processed with a mocked Telegram API.
- **API Endpoint**: `GET /api/alerts/daily-summary` returning computed forward returns and excursions.
