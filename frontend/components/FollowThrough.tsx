'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getFollowThrough, FollowThroughResult } from '@/lib/api'
import { TrendingUp, TrendingDown, Minus, HelpCircle } from 'lucide-react'

const STATUS_CONFIG = {
  following: { icon: TrendingUp,  color: 'text-emerald-400', label: 'Following',  bg: 'bg-emerald-500/10' },
  fading:    { icon: TrendingDown, color: 'text-red-400',     label: 'Fading',     bg: 'bg-red-500/10' },
  flat:      { icon: Minus,       color: 'text-yellow-400',  label: 'Flat',       bg: 'bg-yellow-500/10' },
  no_data:   { icon: HelpCircle,  color: 'text-gray-600',    label: 'No Data',    bg: 'bg-gray-800' },
}

export default function FollowThrough() {
  const router = useRouter()
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
      {[1,2,3].map(i => <div key={i} className="h-10 bg-gray-800/60 rounded-lg" />)}
    </div>
  )

  if (!data || data.results.length === 0) return (
    <div className="flex items-center justify-center h-20 text-gray-700 text-xs">
      No prior-day data available yet
    </div>
  )

  return (
    <div className="space-y-1">
      <p className="text-[10px] text-gray-650 uppercase tracking-wider font-bold pb-1.5 pl-1">
        From {data.date} (Yesterday&apos;s Gainers)
      </p>
      {data.results.map(r => {
        const cfg = STATUS_CONFIG[r.status]
        const Icon = cfg.icon
        return (
          <div
            key={r.ticker}
            className="group flex items-center justify-between gap-3 px-3 py-2 rounded-lg hover:bg-gray-850/60 border border-transparent hover:border-gray-800/40 transition-all cursor-pointer"
            onClick={() => router.push(`/research?ticker=${r.ticker}`)}
          >
            {/* Left: status icon, ticker, float */}
            <div className="flex items-center gap-2.5 min-w-0">
              <div className={`p-1.5 rounded-md shrink-0 ${cfg.bg}`}>
                <Icon size={12} className={cfg.color} />
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-bold text-white font-mono leading-none group-hover:text-emerald-400 transition-colors">
                  {r.ticker}
                </span>
                {r.float_shares != null && (
                  <span className="text-[10px] text-gray-500 font-mono mt-1">
                    {(r.float_shares / 1e6).toFixed(1)}M float
                  </span>
                )}
              </div>
            </div>

            {/* Middle: Yesterday stats */}
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-xs text-emerald-400 font-semibold font-mono leading-none">
                +{r.prev_gap != null ? r.prev_gap.toFixed(1) : '—'}%
              </span>
              <span className="text-[10px] text-gray-550 font-mono mt-1">
                close ${r.prev_close != null ? r.prev_close.toFixed(2) : '—'}
              </span>
            </div>

            {/* Right: Live Price & change today */}
            <div className="flex flex-col text-right items-end shrink-0 min-w-[75px]">
              <span className={`text-xs font-mono font-bold leading-none ${cfg.color}`}>
                {r.change_pct != null
                  ? `${r.change_pct >= 0 ? '+' : ''}${r.change_pct.toFixed(1)}%`
                  : cfg.label}
              </span>
              {(r.today_last ?? r.today_open) != null && (
                <span className="text-[10px] text-gray-400 font-mono mt-1">
                  ${(r.today_last ?? r.today_open)?.toFixed(2)}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
