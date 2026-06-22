# Frontend Optimization & Refactor Handoff

**Status:** Planned, ready to execute
**Target branch:** `feature/frontend-refactor`
**Created:** 2026-06-18

## Goal

Tame the 1438-line `LiveGainers.tsx`, eliminate chart/format duplication
across `MiniSessionChart.tsx` + `alerts/page.tsx` + `daily-charts/page.tsx`,
route all direct `fetch()` calls through `lib/api.ts`, extract a shared
`Panel` primitive, plug an SSE leak, and stand up Vitest for the new
pure-function utilities.

## Scope (4 phases + bonus)

### Phase 1 — Shared utilities

- `lib/format.ts` (new): `fmt1`, `fmtFloat`, `fmtVol`, `addDays`, `todayET`.
- `lib/chart.ts` (new): `OhlcBar`/`LinePt`/`HistoPt`/`ChartData` types,
  color constants (`CHART_BG`, `GRID_COLOR`, `TEXT_COLOR`, `UP_COLOR`,
  `DOWN_COLOR`, `EMA21_COL`), `dedupSort`, `shiftChartDataTime`.
- `lib/api.ts`: add `getChartData(ticker, date, mini=true)` and
  `getGainersByDate(date)`. Extend `GainerSummary` with
  `source: 'live' | 'db' | null`.
- Replace 4 direct `fetch()` sites:
  - `components/MiniSessionChart.tsx:117`
  - `app/alerts/page.tsx:160`
  - `app/daily-charts/page.tsx:151`
  - `app/daily-charts/page.tsx:168`
- Delete local dupes of `fmt1`/`fmtFloat`/`fmtVol` in `LiveGainers.tsx`,
  `MiniSessionChart.tsx`, `app/history/page.tsx`, `app/gainers/page.tsx`.
- Delete the local `GainerSummary` redefinition in
  `app/daily-charts/page.tsx:39-44`.

### Phase 2 — Decompose `LiveGainers.tsx`

- `components/live-gainers/styles.ts` — 8 pure badge fns
  (`getRvolBadgeStyle`, `getRvolColor`, `getFloatBadgeStyle`,
  `getSpreadBadgeStyle`, `getAtrHodColor`, `getAtrVwapStyle`,
  `getZenVStyle`, `getTimeAgoBadge`).
- `components/live-gainers/badges.tsx` — `SessionBadge`, `GapCell`,
  `PriceCell`, `MetricLabelWithTooltip`, `SkeletonRows`.
- `components/live-gainers/GainerTable.tsx` — sortable table.
- `components/live-gainers/useAlertStream.ts` — SSE + chime + toast hook
  (SSE leak fix lives here).
- `components/LiveGainers.tsx` — slim orchestrator (~250 lines).

### Phase 3 — Extract `Panel` primitives

- `components/Panel.tsx`: `Panel` + `PanelLabel`.
- Update `app/page.tsx` to import (delete 25 inlined lines).

### Phase 4 — Vitest setup

- `vitest`, `@testing-library/react`, `jsdom`, `@testing-library/jest-dom`
  in `devDependencies`.
- `vitest.config.ts` at frontend root.
- `pnpm test` script in `package.json`.
- Tests:
  - `lib/format.test.ts`
  - `lib/chart.test.ts` (`dedupSort`, `shiftChartDataTime`)
  - `components/live-gainers/styles.test.ts`

### Bonus: SSE leak fix

- In `useAlertStream`: `eventSource.close()` in effect cleanup return.
- Verify no ghost connections on hot-reload / route change.

## Risk / guardrails

- No behavior change to `LiveGainers` table render, sort, or flash logic.
- `Panel` extraction is 1:1; styling unchanged.
- Chart util migration preserves all 8 colors + localOffset math.
- New `GainerSummary.source` is `| null` → backward compatible.
- All edits via `replace_file_content` / `multi_replace_file_content`.
  Never parallel edits on the same file.

## Verification checklist

- [ ] `pnpm lint` clean
- [ ] `pnpm build` passes
- [ ] `pnpm test` passes
- [ ] Manual smoke: `/`, `/daily-charts`, `/alerts` charts render
- [ ] DevTools Network: no orphan `/api/alerts/stream` after route change

## Out of scope (follow-up)

- Decompose `app/continuation/page.tsx` (697) and `app/research/page.tsx`
  (619) — left for next pass.
- Add `useAlertStream` test using `msw` or fake EventSource.
- Migrate `lib/momentum.ts` exports into `lib/format.ts` if a single
  `lib/format.ts` becomes the convention.
