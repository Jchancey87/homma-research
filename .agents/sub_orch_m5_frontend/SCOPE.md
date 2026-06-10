# Scope: Milestone 5 — Performance Dashboard & Scorecard

## Target Files
- `/home/jackc/projects/homma-research/frontend/app/alerts/page.tsx`

## Requirements
Enhance the frontend Alert Journal page:
1. **Render metrics next to alerts**:
   - For each alert, display calculated forward returns (1m, 3m, 5m, 15m) and excursions (MFE/MAE) in the alert list and/or detail panel.
   - Format returns as color-coded text (e.g. green for positive, red for negative, e.g. `+1.2%` or `-0.8%`).
2. **Add a Performance Scorecard**:
   - Add a summary scorecard to the page (e.g. at the top or in a collapsible container).
   - The scorecard must summarize:
     - **Win Rate**: % of alerts with 15m forward return > 0% (or general positive performance).
     - **Expectancy**: Formula `(Win Rate * Average Win) - (Loss Rate * Average Loss)`.
     - **Rankings**: Lists/tables summarizing average returns sorted by:
       - Trigger type (e.g. `HOD_BREAKOUT`, `VOLUME_SPIKE`, etc.).
       - Price bucket (`$1.00-$2.00`, `$2.00-$5.00`, `$5.00-$15.00`, `$15.00+`).
       - Float category (`Micro`, `Small`, `Mid`, `Large`).
3. **TypeScript & Validation**:
   - Ensure the new fields returned by `/api/alerts/daily-summary` are added to TypeScript interfaces in `frontend/lib/api.ts` (or inline if needed).
   - Ensure the Next.js production build completes with 0 warnings.
