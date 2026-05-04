'use client'
import { useEffect, useState } from 'react'
import { getObservations, Observation } from '@/lib/api'
import { FileText } from 'lucide-react'

const SENTIMENT_DOT: Record<string, string> = {
  bullish: 'bg-emerald-400',
  bearish: 'bg-red-400',
  neutral: 'bg-gray-500',
}

const SENTIMENT_TEXT: Record<string, string> = {
  bullish: 'text-emerald-400',
  bearish: 'text-red-400',
  neutral: 'text-gray-500',
}

export default function RecentObservations() {
  const [obs, setObs] = useState<Observation[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getObservations({ limit: 5 })
      .then(setObs)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-gray-600 text-sm">Loading…</p>

  if (obs.length === 0) {
    return (
      <div className="text-center py-6">
        <FileText size={28} className="text-gray-700 mx-auto mb-2" />
        <p className="text-gray-600 text-sm">No observations yet.</p>
        <a href="/observations" className="text-xs text-emerald-400 hover:text-emerald-300 mt-1 inline-block">
          Write your first note →
        </a>
      </div>
    )
  }

  return (
    <div className="space-y-2.5">
      {obs.map(o => (
        <div
          key={o.id}
          className="px-3 py-2.5 rounded-xl bg-gray-800/50 border border-transparent hover:border-gray-700 hover:bg-gray-800 transition-all"
        >
          <div className="flex items-center gap-2 mb-1">
            <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${SENTIMENT_DOT[o.sentiment] ?? 'bg-gray-500'}`} />
            <span className="font-bold text-white text-sm">{o.ticker}</span>
            <span className="text-xs text-gray-500">{o.date}</span>
            <span className={`text-xs font-medium ml-auto ${SENTIMENT_TEXT[o.sentiment] ?? 'text-gray-400'}`}>
              {o.sentiment}
            </span>
          </div>
          {o.title && (
            <p className="text-xs font-semibold text-gray-300 mb-0.5">{o.title}</p>
          )}
          <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">{o.body}</p>
        </div>
      ))}
      <a
        href="/observations"
        className="block text-center text-xs text-gray-600 hover:text-gray-400 pt-1 transition-colors"
      >
        View all observations →
      </a>
    </div>
  )
}
