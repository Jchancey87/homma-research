'use client'
import { useEffect, useState } from 'react'
import { getSectorRotation, SectorRotationItem } from '@/lib/api'
import { TrendingUp, TrendingDown, Minus, Sparkles } from 'lucide-react'

const TREND_CONFIG = {
  up:   { icon: TrendingUp,  color: 'text-emerald-400', label: '↑' },
  down: { icon: TrendingDown, color: 'text-red-400',    label: '↓' },
  flat: { icon: Minus,       color: 'text-gray-500',    label: '—' },
  new:  { icon: Sparkles,    color: 'text-amber-400',   label: 'NEW' },
}

function shortSector(s: string) {
  return s
    .replace('Consumer Cyclical', 'Cons. Cyclical')
    .replace('Consumer Defensive', 'Cons. Defensive')
    .replace('Communication Services', 'Comms')
    .replace('Financial Services', 'Financials')
    .replace('Real Estate', 'Real Estate')
    .replace('Basic Materials', 'Materials')
    .replace('SERVICES-COMPUTER PROCESSING & DATA PREPARATION', 'Tech Services')
    .replace('SERVICES-COMPUTER PROGRAMMING SERVICES', 'Tech Services')
    .replace('BLANK CHECKS', 'SPACs')
}

export default function SectorRotation() {
  const [sectors, setSectors] = useState<SectorRotationItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSectorRotation()
      .then(setSectors)
      .catch(() => setSectors([]))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="space-y-2 animate-pulse">
      {[1,2,3,4].map(i => <div key={i} className="h-8 bg-gray-800/60 rounded" />)}
    </div>
  )

  if (sectors.length === 0) return (
    <div className="flex items-center justify-center h-16 text-gray-700 text-xs">
      Not enough data for rotation analysis
    </div>
  )

  return (
    <div className="space-y-1">
      {sectors.map((s, i) => {
        const trend = TREND_CONFIG[s.trend]
        const Icon  = trend.icon
        return (
          <div
            key={s.sector}
            className="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-gray-800/40 transition-colors"
          >
            {/* Rank */}
            <span className="text-[11px] font-bold text-gray-700 w-4 shrink-0">#{i + 1}</span>

            {/* Trend icon */}
            <Icon size={12} className={`${trend.color} shrink-0`} />

            {/* Sector name */}
            <span className="text-xs text-gray-300 flex-1 min-w-0 truncate">
              {shortSector(s.sector)}
            </span>

            {/* Count */}
            <span className="text-[10px] text-gray-600 font-mono hidden sm:block shrink-0">
              {s.count}x
            </span>

            {/* Avg gap */}
            <span className="text-xs text-emerald-400 font-mono font-semibold w-14 text-right shrink-0">
              +{s.avg_gap_pct?.toFixed(1) ?? '—'}%
            </span>

            {/* Trend badge for NEW */}
            {s.trend === 'new' && (
              <span className="text-[10px] font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded shrink-0">
                NEW
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
