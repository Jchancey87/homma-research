# ADR 0004: Modularize Frontend API Client (api.ts)

## Status
Accepted

## Context
`frontend/lib/api.ts` was a 1,056-line monolithic file (the highest churn file in the repository with 45 commits). It mixed core Axios transport configuration, ~30 TypeScript interface definitions, and 40+ API calls across gainers, alerts, market breadth, and LLM analysis endpoints.

Adding any new endpoint forced modifications to `api.ts`, making it a shallow module where interface complexity grew linearly with implementation size.

## Decision
We modularize `frontend/lib/api.ts` into focused domain modules under `frontend/lib/api/`:
1. **`client.ts`**: Core Axios HTTP client instance, environment detection (`NEXT_PUBLIC_API_URL` vs `INTERNAL_API_URL`), and error interceptors.
2. **`types.ts`**: Centralized TypeScript interface definitions (`Gainer`, `ChartCapture`, `LLMJob`, `AlertItem`, etc.).
3. **`gainers.ts`**: Gainers, live quotes, screener summary, ticker history, float buckets, sector rotation endpoints.
4. **`alerts.ts`**: Alert evaluation, hysteresis rules, suppressions, Telegram notification endpoints.
5. **`market.ts`**: Market session, momentum breadth, economic calendar endpoints.
6. **`analysis.ts`**: LLM research jobs, continuation reports, post-market reflection endpoints.
7. **`api.ts` (Barrel Export)**: Transparent re-export facade re-exporting all methods and types from `frontend/lib/api/*` to maintain 100% backward compatibility for all existing Next.js pages and components.

## Consequences
### Positive
- High-churn API file split into small, domain-scoped files with single responsibility.
- Type definitions separated from endpoint callables.
- 100% backward compatibility preserved for existing imports (`import { getGainers } from '@/lib/api'`).

### Negative / Trade-offs
- Replaces a single 1,056-line `api.ts` file with 6 modular files under `frontend/lib/api/`.
