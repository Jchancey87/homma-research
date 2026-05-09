'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getRepeatRunners, RepeatRunner } from '@/lib/api'
import { RotateCcw, ExternalLink } from 'lucide-react'

function fmt(n: number | null, suffix = '') {
  if (n == null) return '—'
  return `${n.toFixed(1)}${suffix}`
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
      No repeat runners in today's live scan
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
          <div className="flex items-center gap-2 w-28 shrink-0">
            <span className="text-sm font-bold text-white font-mono">{r.ticker}</span>
            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400">
              {r.appearances}
            </span>
          </div>

          {/* Key stats */}
          <div className="flex items-center gap-3 text-xs flex-1 min-w-0">
            <span className="text-gray-600">Best</span>
            <span className="text-emerald-400 font-mono font-semibold">+{fmt(r.best_gap_pct)}%</span>
            <span className="text-gray-700 hidden sm:block">·</span>
            <span className="text-gray-500 hidden sm:block font-mono">{fmt(r.avg_float_m)}M float</span>
            <span className="text-gray-700 hidden sm:block">·</span>
            <span className="text-gray-500 hidden sm:block">last {r.last_seen}</span>
          </div>

          {/* Action */}
          <ExternalLink
            size={12}
            className="text-gray-700 group-hover:text-amber-400 transition-colors shrink-0"
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
