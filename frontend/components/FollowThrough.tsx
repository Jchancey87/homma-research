'use client'
import { useEffect, useState } from 'react'
import { getFollowThrough, FollowThroughResult } from '@/lib/api'
import { TrendingUp, TrendingDown, Minus, HelpCircle } from 'lucide-react'

const STATUS_CONFIG = {
  following: { icon: TrendingUp,  color: 'text-emerald-400', label: 'Following',  bg: 'bg-emerald-500/10' },
  fading:    { icon: TrendingDown, color: 'text-red-400',     label: 'Fading',     bg: 'bg-red-500/10' },
  flat:      { icon: Minus,       color: 'text-yellow-400',  label: 'Flat',       bg: 'bg-yellow-500/10' },
  no_data:   { icon: HelpCircle,  color: 'text-gray-600',    label: 'No Data',    bg: 'bg-gray-800' },
}

export default function FollowThrough() {
  const [data, setData]       = useState<{ date: string; results: FollowThroughResult[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getFollowThrough()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="space-y-2 animate-pulse">
      {[1,2,3].map(i => <div key={i} className="h-9 bg-gray-800/60 rounded-lg" />)}
    </div>
  )

  if (!data || data.results.length === 0) return (
    <div className="flex items-center justify-center h-20 text-gray-700 text-xs">
      No prior-day data available yet
    </div>
  )

  return (
    <div className="space-y-1">
      <p className="text-[10px] text-gray-600 uppercase tracking-wide font-semibold pb-1 pl-1">
        From {data.date}
      </p>
      {data.results.map(r => {
        const cfg = STATUS_CONFIG[r.status]
        const Icon = cfg.icon
        return (
          <div
            key={r.ticker}
            className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-800/40 transition-colors"
          >
            {/* Status icon */}
            <div className={`p-1 rounded-md ${cfg.bg}`}>
              <Icon size={11} className={cfg.color} />
            </div>

            {/* Ticker */}
            <span className="text-sm font-bold text-white font-mono w-14 shrink-0">{r.ticker}</span>

            {/* Yesterday's gap */}
            <span className="text-xs text-gray-500 hidden sm:block">
              +{r.prev_gap != null ? r.prev_gap.toFixed(1) : '—'}% yesterday
            </span>

            {/* Today change */}
            <span className={`text-xs font-mono font-semibold ml-auto ${cfg.color}`}>
              {r.change_pct != null
                ? `${r.change_pct >= 0 ? '+' : ''}${r.change_pct.toFixed(1)}% today`
                : cfg.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}
