'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getRepeatRunners, RepeatRunner } from '@/lib/api'
import { ExternalLink } from 'lucide-react'

function fmt(n: number | null, suffix = '') {
  if (n == null) return '—'
  return `${n.toFixed(1)}${suffix}`
}

function Sparkline({ points }: { points?: number[] }) {
  if (!points || points.length < 2) return <div className="w-16 h-5" />
  
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min
  
  const width = 64;
  const height = 20;
  const padding = 2;
  
  const coords = points.map((p, idx) => {
    const x = (idx / (points.length - 1)) * (width - 2 * padding) + padding
    const y = range === 0 
      ? height / 2 
      : height - padding - ((p - min) / range) * (height - 2 * padding)
    return { x, y }
  })
  
  const pathD = coords.reduce((acc, c, idx) => {
    return acc + `${idx === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`
  }, '')
  
  const lastPoint = coords[coords.length - 1]
  const strokeColor = points[points.length - 1] >= points[0] ? '#10b981' : '#f43f5e'
  
  return (
    <svg width={width} height={height} className="overflow-visible inline-block">
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={lastPoint.x}
        cy={lastPoint.y}
        r="2"
        fill={strokeColor}
      />
    </svg>
  )
}

function SmaPills({ r }: { r: RepeatRunner }) {
  const p20 = r.above_sma20 != null ? (r.above_sma20 ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-red-500/15 text-red-400 border-red-500/30') : 'bg-gray-800/60 text-gray-500 border-gray-700/20'
  const p50 = r.above_sma50 != null ? (r.above_sma50 ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-red-500/15 text-red-400 border-red-500/30') : 'bg-gray-800/60 text-gray-500 border-gray-700/20'
  const p100 = r.above_sma100 != null ? (r.above_sma100 ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-red-500/15 text-red-400 border-red-500/30') : 'bg-gray-800/60 text-gray-500 border-gray-700/20'
  
  return (
    <div className="flex items-center gap-1 text-[9px] font-bold">
      <span title={`SMA 20: ${r.sma20 != null ? r.sma20 : '—'}`} className={`px-1.5 py-0.5 rounded border ${p20}`}>20</span>
      <span title={`SMA 50: ${r.sma50 != null ? r.sma50 : '—'}`} className={`px-1.5 py-0.5 rounded border ${p50}`}>50</span>
      <span title={`SMA 100: ${r.sma100 != null ? r.sma100 : '—'}`} className={`px-1.5 py-0.5 rounded border ${p100}`}>100</span>
    </div>
  )
}

export default function RepeatRunnerAlert() {
  const router = useRouter()
  const [runners, setRunners] = useState<RepeatRunner[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getRepeatRunners()
      .then(setRunners)
      .catch(() => setRunners([]))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="space-y-2 animate-pulse">
      {[1,2].map(i => <div key={i} className="h-10 bg-gray-800/60 rounded-lg" />)}
    </div>
  )

  if (runners.length === 0) return (
    <div className="flex items-center justify-center h-20 text-gray-700 text-xs">
      No repeat runners in today&apos;s live scan
    </div>
  )

  return (
    <div className="space-y-1">
      {runners.map(r => (
        <div
          key={r.ticker}
          className="group flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-amber-500/5 border border-transparent hover:border-amber-500/15 transition-all cursor-pointer"
          onClick={() => router.push(`/research?ticker=${r.ticker}`)}
        >
          {/* Ticker + appearances */}
          <div className="flex items-center gap-2 w-24 shrink-0">
            <span className="text-sm font-bold text-white font-mono">{r.ticker}</span>
            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400">
              {r.appearances}
            </span>
          </div>

          {/* Sparkline */}
          <div className="shrink-0 w-16 flex items-center justify-center">
            <Sparkline points={r.sparkline_5d} />
          </div>

          {/* Key stats */}
          <div className="flex items-center gap-3 text-xs flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-gray-600">Best</span>
              <span className="text-emerald-400 font-mono font-semibold">+{fmt(r.best_gap_pct)}%</span>
              <span className="text-gray-700 hidden md:block">·</span>
              <span className="text-gray-500 hidden md:block font-mono">{fmt(r.avg_float_m)}M float</span>
              {r.today_gap_pct != null && (
                <>
                  <span className="text-gray-700 hidden sm:block">·</span>
                  <span className="text-amber-400 font-mono font-semibold">+{r.today_gap_pct.toFixed(1)}% today</span>
                </>
              )}
            </div>
          </div>

          {/* SMA indicators */}
          <div className="shrink-0">
            <SmaPills r={r} />
          </div>

          {/* Action */}
          <ExternalLink
            size={12}
            className="text-gray-700 group-hover:text-amber-400 transition-colors shrink-0 ml-1"
          />
        </div>
      ))}
      {runners.length > 0 && (
        <p className="text-[10px] text-gray-700 pl-3 pt-1">
          {runners.length} ticker{runners.length !== 1 ? 's' : ''} running today have prior history in your database
        </p>
      )}
    </div>
  )
}
