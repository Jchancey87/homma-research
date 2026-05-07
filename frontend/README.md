# Trading Journal Frontend 🖼️

The frontend is a modern Next.js 14 application designed for rapid ticker analysis and data visualization.

## 🚀 Key Features

- **Command Center**: A unified hub for real-time gainers, historical ticker tracking, and period-aware heatmaps.
- **Interactive Charting**: Powered by `lightweight-charts`, providing a TradingView-like experience with EMA ribbons, RVOL, ATR, and ADX panels.
- **Deep Research Interface**: A tabbed `/research` page with four parallel analysis modules that all fire simultaneously when you submit a ticker.
- **Dynamic Dashboard**: "Today's Movers" briefing, watchlist quick-access, and archetype performance metrics.
- **Responsive Layout**: Tailwind CSS with dark mode throughout.

## 🛠️ Getting Started

### Prerequisites

- Node.js 18+
- Backend server running at `http://localhost:5000`

### Installation

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## 📁 Project Structure

```
frontend/
├── app/
│   ├── page.tsx              # Main dashboard (Today's Movers)
│   ├── history/
│   │   └── page.tsx          # Command Center (Ticker History & Heatmaps)
│   ├── research/
│   │   └── page.tsx          # Deep Research page (4 parallel tabs)
│   ├── daily-charts/
│   │   └── page.tsx          # Responsive grid of daily gainers
│   └── watchlist/            # Watchlist & notes management
├── components/
│   ├── research/
│   │   └── FeaturePanel.tsx  # Reusable tab panel for research modules
│   ├── InteractiveSessionChart.tsx  # lightweight-charts integration
│   ├── HeatMap.tsx           # Vega-lite powered heatmap
│   └── ...
├── lib/
│   └── api.ts                # Typed Axios API client
└── hooks/                    # Custom React hooks
```

## 🔬 Deep Research Page (`/research`)

The research page fires **4 parallel LLM jobs** when you click **ANALYZE**:

| Tab | Backend Job | What it does |
|---|---|---|
| **Full Report** | `POST /api/research` | Full fundamental + technical + vision analyst report |
| **🚨 Risk Detection** | `POST /api/research/risk` | Scans SEC filings, short interest, insider activity, toxic financing |
| **⚡ Catalyst Analysis** | `POST /api/research/catalyst` | Rates catalyst quality (Tier 1/2/3) from news, 8-K, earnings |
| **📊 Deep Context** | `POST /api/research/context` | Setup Score (1–10) with SMA levels, RS vs SPY, options sentiment |

- Each tab has its own independent loading/error/report state.
- Each tab has a **Re-run** button for refreshing individual modules without rerunning all four.
- The optional **date picker** anchors the Catalyst Analysis to a specific trading date (inherits from the search bar automatically).

### State Pattern

Each feature uses an independent `FeatureState`:
```typescript
interface FeatureState {
  jobId:   string | null  // UUID from backend, null when idle or complete
  loading: boolean
  report:  string | null  // Markdown output from LLM
  error:   string | null
  status:  string | null  // Loading status message
}
```

All four states poll `GET /api/jobs/<job_id>` every 2.5s until `status === 'done'`.

## 📈 `FeaturePanel` Component

`components/research/FeaturePanel.tsx` is a reusable panel used by Risk, Catalyst, and Context tabs.

**Props:**
```typescript
{
  title:       string
  description: string
  Icon:        LucideIcon
  accentColor: 'orange' | 'emerald' | 'blue'
  state:       FeatureState
  onTrigger:   () => void   // Re-run callback
  ticker:      string | null
}
```

## 🔧 Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:5000
```
