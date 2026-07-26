# ADR 0005: Extract Services from Fat Routers (market.py, gainers.py, analysis.py)

## Status
Accepted

## Context
Rule 4 in `AGENTS.md` (enforced by RFC-001) specifies that API routers MUST be thin wrappers (~30 lines max per handler) responsible ONLY for:
1. Parsing and validating request inputs
2. Calling exactly one service function
3. Formatting the response or translating domain exceptions to HTTP errors

Three routers (`market.py`, `gainers.py`, and `analysis.py`) contained inline business logic, complex SQL FILTER-aggregate queries, VIX term structure math, float bucket calculations, and LLM job dispatching directly in route handlers.

## Decision
We extract dedicated domain services in `backend/services/`:
1. **`MarketService` (`backend/services/market_service.py`)**: Owns market regime calculation, VIX term structure parsing, SQL FILTER-aggregate momentum breadth math, and economic calendar fetching.
2. **`GainersService` (`backend/services/gainers_service.py`)**: Owns float bucket aggregation, sector rotation trend math, and ticker history query logic.
3. **`AnalysisService` (`backend/services/analysis_service.py`)**: Owns LLM research job dispatching, status polling, report caching, and research history queries.
4. **Thin Routers**: Refactor `market.py`, `gainers.py`, and `analysis.py` into thin handlers that delegate directly to their respective service functions.

## Consequences
### Positive
- Strict adherence to RFC-001 thin router rules.
- Pure domain and SQL logic isolated in services, testable without spinning up FastAPI test clients.
- Clean separation of concerns across HTTP transport vs core business logic.

### Negative / Trade-offs
- Adds three service modules (`market_service.py`, `gainers_service.py`, `analysis_service.py`) under `backend/services/`.
