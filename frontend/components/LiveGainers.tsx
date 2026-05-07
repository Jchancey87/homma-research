'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { getLiveGainers, LiveGainerSnapshot, LiveGainerRow } from '@/lib/api'
import { useRouter } from 'next/navigation'
import { RefreshCw, TrendingUp, Clock, Wifi, WifiOff } from 'lucide-react'

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmt(n: number | null, dec = 1, suffix = '') {
  if (n == null) return '—'
  return n.toFixed(dec) + suffix
}

function fmtVol(n: number | null) {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`
  return n.toLocaleString()
}

function fmtAge(isoUtc: string | null): string {
  if (!isoUtc) return ''
  const seconds = Math.floor((Date.now() - new Date(isoUtc).getTime()) / 1000)
  if (seconds < 60)  return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

// ── Session badge ──────────────────────────────────────────────────────────────

const SESSION_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  pre_market:   { bg: 'bg-sky-500/15',     text: 'text-sky-300',    dot: 'bg-sky-400'    },
  open:         { bg: 'bg-emerald-500/15', text: 'text-emerald-400', dot: 'bg-emerald-400' },
  after_hours:  { bg: 'bg-violet-500/15',  text: 'text-violet-300', dot: 'bg-violet-400' },
  closed:       { bg: 'bg-gray-700/40',    text: 'text-gray-500',   dot: 'bg-gray-600'   },
}

function SessionBadge({ session, label }: { session: string; label: string }) {
  const s = SESSION_STYLES[session] ?? SESSION_STYLES.closed
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${session === 'open' ? 'animate-pulse' : ''}`} />
      {label}
    </span>
  )
}

// ── Price change cell ─────────────────────────────────────────────────────────

function GapCell({ gap }: { gap: number }) {
  const color = gap >= 50 ? 'text-amber-400' : gap >= 20 ? 'text-emerald-400' : 'text-emerald-300'
  return (
    <td className="py-2.5 pr-4 text-right font-mono">
      <span className={`font-bold ${color}`}>+{gap.toFixed(1)}%</span>
    </td>
  )
}

// ── RVOL cell ─────────────────────────────────────────────────────────────────

function RvolCell({ rvol }: { rvol: number | null }) {
  const color = rvol != null && rvol >= 5 ? 'text-amber-400' : 'text-gray-400'
  return (
    <td className="py-2.5 pr-3 text-right font-mono">
      <span className={color}>{fmt(rvol)}x</span>
    </td>
  )
}

// ── Price cell ────────────────────────────────────────────────────────────────

function PriceCell({ last, prev }: { last: number | null; prev: number | null }) {
  if (last == null) return <td className="py-2.5 pr-4 text-right font-mono text-gray-500">—</td>
  const up = prev == null || last >= prev
  return (
    <td className={`py-2.5 pr-4 text-right font-mono text-sm ${up ? 'text-white' : 'text-red-400'}`}>
      ${last.toFixed(2)}
    </td>
  )
}

// ── Row skeleton ──────────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 10 }).map((_, i) => (
        <tr key={i} className="animate-pulse">
          {Array.from({ length: 7 }).map((_, j) => (
            <td key={j} className="py-3 pr-4">
              <div className={`h-3 bg-gray-800 rounded ${j === 0 ? 'w-14' : j === 6 ? 'w-28' : 'w-12'}`} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function LiveGainers() {
  const router = useRouter()
  const [snap,        setSnap]        = useState<LiveGainerSnapshot | null>(null)
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState<string | null>(null)
  const [refreshing,  setRefreshing]  = useState(false)
  const [ageStr,      setAgeStr]      = useState('')
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchData = useCallback(async (force = false) => {
    try {
      if (force) setRefreshing(true)
      const data = await getLiveGainers(force)
      setSnap(data)
      setError(null)
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load live data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  // Initial load + polling
  useEffect(() => {
    fetchData()
    // Poll every 5 minutes — matches the backend cache TTL
    timerRef.current = setInterval(() => fetchData(), 5 * 60 * 1000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [fetchData])

  // Live "X ago" counter (updates every 10s)
  useEffect(() => {
    const tick = () => setAgeStr(snap?.fetched_at ? fmtAge(snap.fetched_at) : '')
    tick()
    const id = setInterval(tick, 10_000)
    return () => clearInterval(id)
  }, [snap?.fetched_at])

  const handleResearch = (g: LiveGainerRow) => {
    const today = new Date().toISOString().slice(0, 10)
    router.push(`/research?ticker=${g.ticker}&date=${today}`)
  }

  const session    = snap?.session ?? 'closed'
  const isActive   = session !== 'closed'
  const gainers    = snap?.gainers ?? []

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          {snap && (
            <SessionBadge session={session} label={snap.session_label} />
          )}
          {ageStr && (
            <span className="flex items-center gap-1 text-[11px] text-gray-600">
              <Clock size={10} />
              {ageStr}
            </span>
          )}
          {isActive && !error && (
            <span className="flex items-center gap-1 text-[11px] text-gray-700">
              <Wifi size={10} className="text-emerald-600" />
              auto-refresh 5m
            </span>
          )}
          {error && (
            <span className="flex items-center gap-1 text-[11px] text-red-500">
              <WifiOff size={10} />
              {error}
            </span>
          )}
        </div>

        <button
          id="live-gainers-refresh"
          onClick={() => fetchData(true)}
          disabled={refreshing}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-emerald-400 transition-colors disabled:opacity-40"
        >
          <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* EOD persist notice */}
      {session === 'after_hours' && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-xs text-violet-300">
          <TrendingUp size={12} className="shrink-0" />
          These gainers will be automatically saved to your database at 8:00 PM ET.
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
              <th className="pb-2 pr-4 font-medium">Ticker</th>
              <th className="pb-2 pr-4 font-medium text-right">Gap %</th>
              <th className="pb-2 pr-4 font-medium text-right">Price</th>
              <th className="pb-2 pr-3 font-medium text-right">RVOL</th>
              <th className="pb-2 pr-4 font-medium text-right">Volume</th>
              <th className="pb-2 pr-4 font-medium text-right">Prev Close</th>
              <th className="pb-2 font-medium">Sector / Note</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {loading ? (
              <SkeletonRows />
            ) : gainers.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-10 text-center text-gray-600 text-sm">
                  {session === 'closed'
                    ? 'Market is closed. Check back during pre-market (4 AM ET) or regular hours.'
                    : 'No gainers meeting criteria right now. Data refreshes every 5 minutes.'}
                </td>
              </tr>
            ) : (
              gainers.map((g, i) => (
                <tr
                  key={g.ticker}
                  className="hover:bg-gray-800/40 transition-colors group cursor-pointer"
                  onClick={() => handleResearch(g)}
                >
                  <td className="py-2.5 pr-4">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-600 text-xs w-4">{i + 1}</span>
                      <span className="font-bold text-white group-hover:text-emerald-400 transition-colors font-mono">
                        {g.ticker}
                      </span>
                    </div>
                  </td>
                  <GapCell gap={g.gap_pct} />
                  <PriceCell last={g.last_price} prev={g.prev_close} />
                  <RvolCell rvol={g.rvol_15m} />
                  <td className="py-2.5 pr-4 text-right font-mono text-xs text-gray-400">
                    {fmtVol(g.volume)}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-xs text-gray-500">
                    {g.prev_close != null ? `$${g.prev_close.toFixed(2)}` : '—'}
                  </td>
                  <td className="py-2.5">
                    <span className="text-gray-500 text-xs">
                      {g.sector ?? (g.news_headline ?? '—')}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Footer — last DB ingest */}
      <div className="pt-2 border-t border-gray-800/60">
        <LastIngestRow />
      </div>
    </div>
  )
}

// ── Last DB ingest sub-row ─────────────────────────────────────────────────────

function LastIngestRow() {
  const [summary, setSummary] = useState<{ date: string | null; total: number } | null>(null)

  useEffect(() => {
    import('@/lib/api').then(({ getGainersSummary }) =>
      getGainersSummary()
        .then(s => setSummary({ date: s.date, total: s.total }))
        .catch(() => {})
    )
  }, [])

  if (!summary?.date) return null

  const dateLabel = new Date(summary.date + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
  })

  return (
    <div className="flex items-center justify-between text-[11px] text-gray-600">
      <span>
        Last ingested: <span className="text-gray-500">{dateLabel}</span>
        <span className="ml-2 text-gray-700">({summary.total} tickers)</span>
      </span>
      <a href="/history" className="hover:text-emerald-400 transition-colors">
        Command Center →
      </a>
    </div>
  )
}
