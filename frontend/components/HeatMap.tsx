'use client'
import dynamic from 'next/dynamic'
import { useEffect, useState } from 'react'
import { getHeatmap } from '@/lib/api'
import { RefreshCw } from 'lucide-react'

// Plotly must be client-side only (no SSR)
const Plot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-64 text-gray-600 text-sm">
      Loading…
    </div>
  ),
})

type View = 'float_rvol' | 'sector'

type HeatmapSpec = { data: unknown[]; layout: Record<string, unknown> } | null

interface Props {
  /** Pre-fetched spec from a server component. Only used for float_rvol view with no period. */
  spec?:   HeatmapSpec
  /** If provided, component manages its own fetch with this period. */
  period?: string
  height?: number
  /** Whether to show the view tab switcher inside the component. Default true. */
  showTabs?: boolean
}

const VIEW_TABS: { key: View; label: string }[] = [
  { key: 'float_rvol', label: 'Float × RVOL' },
  { key: 'sector',     label: 'By Sector' },
]

export default function HeatMap({ spec: initialSpec, period, height = 320, showTabs = true }: Props) {
  const clientManaged = period !== undefined

  const [view,    setView]    = useState<View>('float_rvol')
  const [spec,    setSpec]    = useState<HeatmapSpec>(initialSpec ?? null)
  const [loading, setLoading] = useState(clientManaged)

  // Re-fetch whenever period or view changes (client-managed mode)
  useEffect(() => {
    if (!clientManaged && view === 'float_rvol') return  // use passed-in spec for default case
    let cancelled = false
    setLoading(true)
    getHeatmap(
      period === 'all' ? undefined : period,
      view === 'sector' ? 'sector' : undefined,
    )
      .then(s => { if (!cancelled) setSpec(s) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [period, view, clientManaged])

  // Compute dynamic height: sector chart needs more room for many sector labels
  const chartHeight = view === 'sector'
    ? Math.max(height, 340)   // sector bar chart tends to be taller
    : height

  return (
    <div className="flex flex-col gap-0">
      {/* View tab switcher */}
      {showTabs && (
        <div className="flex items-center gap-1 mb-3">
          {VIEW_TABS.map(({ key, label }) => (
            <button
              key={key}
              id={`heatmap-tab-${key}`}
              onClick={() => setView(key)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                view === key
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'text-gray-500 hover:text-gray-300 border border-transparent hover:border-gray-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Chart */}
      {loading ? (
        <div
          className="flex items-center justify-center gap-2 text-gray-600 text-sm rounded-xl border border-gray-800/60"
          style={{ height: chartHeight }}
        >
          <RefreshCw size={14} className="animate-spin" />
          <span>Loading…</span>
        </div>
      ) : !spec?.data?.length ? (
        <div
          className="flex items-center justify-center rounded-xl border border-gray-800 text-gray-600 text-sm"
          style={{ height: chartHeight }}
        >
          No data for this period yet.
        </div>
      ) : (
        <Plot
          data={spec.data as Plotly.Data[]}
          layout={{
            ...spec.layout,
            autosize:      true,
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor:  'rgba(0,0,0,0)',
            font:          { color: '#94a3b8', family: 'Inter, system-ui, sans-serif', size: 11 },
            // Tighter margins for sector (y-axis labels handled by automargin)
            margin: view === 'sector'
              ? { t: 8, b: 50, l: 130, r: 70 }
              : { t: 8, b: 50, l: 65,  r: 10 },
            xaxis: {
              ...(spec.layout.xaxis as object ?? {}),
              fixedrange: true,
            },
            yaxis: {
              ...(spec.layout.yaxis as object ?? {}),
              fixedrange:  true,
              automargin:  true,
            },
          }}
          config={{ responsive: true, displayModeBar: false }}
          style={{ width: '100%', height: `${chartHeight}px` }}
        />
      )}
    </div>
  )
}
