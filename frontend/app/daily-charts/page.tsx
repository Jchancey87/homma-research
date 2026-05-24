'use client'
import { useEffect, useState, useCallback, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { getGainersSummary, GainerSummary, getPipeScan, PipeScanResult, Gainer } from '@/lib/api'
import MiniSessionChart from '@/components/MiniSessionChart'
import { BarChart2, RefreshCw, ChevronLeft, ChevronRight, Search } from 'lucide-react'

// ── Helpers ──────────────────────────────────────────────────────────────────

function addDays(dateStr: string, n: number): string {
  const d = new Date(dateStr + 'T12:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().split('T')[0]
}

function todayET(): string {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
}

// ── Page ─────────────────────────────────────────────────────────────────────

function DailyChartsContent() {
  const router       = useRouter()
  const searchParams = useSearchParams()

  const [summary, setSummary]   = useState<GainerSummary | null>(null)
  const [loading, setLoading]   = useState(true)
  const [activeDate, setActiveDate] = useState<string>(
    searchParams.get('date') || ''
  )
  const [pipeMap, setPipeMap]   = useState<Record<string, PipeScanResult>>({})

  // ── Fetch summary for the active date ──────────────────────────────────────
  const load = useCallback(async () => {
    setLoading(true)
    try {
      // Always fetch latest first to discover the most recent ingest date
      const s = await getGainersSummary()
      if (!s.date) { setSummary(s); return }

      // If a specific date was requested via URL param, use that date's gainers
      const targetDate = activeDate || s.date
      if (targetDate !== s.date) {
        // Fetch gainers for specific date via the standard gainers endpoint
        const res  = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5000'}/api/gainers?date=${targetDate}`
        )
        const rows = await res.json()
        setSummary({
          date:    targetDate,
          total:   rows.length,
          gainers: rows.slice(0, 9).map((g: Gainer) => ({
            ticker:       g.ticker,
            gap_pct:      g.gap_pct,
            float_shares: g.float_shares,
            rvol_15m:     g.rvol_15m,
            sector:       g.sector,
            news_headline: g.news_headline,
            news_fresh:   g.news_fresh,
            close_price:  g.close_price,
            open_price:   g.open_price,
          })),
        })
        if (!activeDate) setActiveDate(s.date)
      } else {
        setSummary(s)
        if (!activeDate) setActiveDate(s.date)
      }
    } catch {
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }, [activeDate])

  useEffect(() => { load() }, [load])

  // Auto-scan for PIPE activity whenever the date and gainers are loaded
  useEffect(() => {
    if (!activeDate || loading) return
    getPipeScan(activeDate)
      .then(results => {
        const map: Record<string, PipeScanResult> = {}
        results.forEach(r => { map[r.ticker] = r })
        setPipeMap(map)
      })
      .catch(() => {/* silent — PIPE badges are non-critical */})
  }, [activeDate, loading])

  // ── Date navigation ────────────────────────────────────────────────────────
  const goDate = (date: string) => {
    setActiveDate(date)
    router.replace(`/daily-charts?date=${date}`, { scroll: false })
  }

  // ── Expand → Research ─────────────────────────────────────────────────────
  const handleExpand = (ticker: string) => {
    router.push(`/research?ticker=${ticker}&date=${activeDate}`)
  }

  const dateLabel = activeDate
    ? new Date(activeDate + 'T12:00:00').toLocaleDateString('en-US', {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
      })
    : ''

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart2 className="text-emerald-400" size={22} />
            Daily Chart Overview
          </h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Top 9 intraday sessions · candlestick + volume + EMA 21
          </p>
        </div>

        {/* Date controls */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            id="prev-day"
            onClick={() => activeDate && goDate(addDays(activeDate, -1))}
            disabled={!activeDate}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors"
          >
            <ChevronLeft size={16} />
          </button>

          <input
            id="date-picker"
            type="date"
            value={activeDate}
            max={todayET()}
            onChange={e => e.target.value && goDate(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-white text-sm
                       focus:outline-none focus:border-emerald-500 [color-scheme:dark]"
          />

          <button
            id="next-day"
            onClick={() => activeDate && activeDate < todayET() && goDate(addDays(activeDate, 1))}
            disabled={!activeDate || activeDate >= todayET()}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors"
          >
            <ChevronRight size={16} />
          </button>

          <button
            id="refresh-charts"
            onClick={load}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {/* ── Date label + stats bar ── */}
      {!loading && summary?.date && (
        <div className="flex items-center gap-4 px-4 py-3 bg-gray-900 border border-gray-800 rounded-xl">
          <span className="text-sm font-semibold text-gray-200">{dateLabel}</span>
          <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-500/15 text-emerald-400 font-medium">
            {summary.total} gainers ingested
          </span>
          <span className="text-xs text-gray-500">
            Showing top {summary.gainers.length} by gap %
          </span>
          <span className="ml-auto text-xs text-gray-600">
            Click any chart to open full research panel
          </span>
        </div>
      )}

      {/* ── State: loading ── */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden animate-pulse">
              <div className="h-8 bg-gray-800 border-b border-gray-700" />
              <div className="h-[200px] bg-[#0d0d14]" />
              <div className="h-6 bg-gray-900 border-t border-gray-900" />
            </div>
          ))}
        </div>
      )}

      {/* ── State: no data ── */}
      {!loading && (!summary || !summary.date || summary.gainers.length === 0) && (
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <Search size={36} className="text-gray-700" />
          <p className="text-gray-500 text-sm">No ingest data found for this date.</p>
          <p className="text-gray-600 text-xs">Try a different date or run the ingestion job first.</p>
        </div>
      )}

      {/* ── Chart grid ── */}
      {!loading && summary && summary.gainers.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {summary.gainers.map((g, idx) => {
            const pipe = pipeMap[g.ticker]
            const pipeColor =
              !pipe || !pipe.is_pipe ? null
              : (pipe.deal_score ?? 0) >= 4 ? 'bg-emerald-500 text-white'
              : (pipe.deal_score ?? 0) <= 2 ? 'bg-red-500 text-white'
              : 'bg-yellow-500 text-black'

            return (
              <div key={g.ticker} className="relative">
                {/* Rank badge */}
                <span className="absolute top-2.5 left-[52px] z-10 text-[10px] text-gray-600 font-mono">
                  #{idx + 1}
                </span>
                {/* PIPE badge */}
                {pipe?.is_pipe && pipeColor && (
                  <span
                    className={`absolute top-2.5 right-2 z-10 text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-wider ${pipeColor}`}
                    title={`PIPE detected · score ${pipe.deal_score}/5 · ${pipe.pricing_type ?? 'unknown'} pricing`}
                  >
                    PIPE {pipe.deal_score}/5
                  </span>
                )}
                <MiniSessionChart
                  ticker={g.ticker}
                  date={summary.date!}
                  gapPct={g.gap_pct}
                  float={g.float_shares}
                  rvol={g.rvol_15m}
                  onExpand={handleExpand}
                />
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function DailyChartsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center py-24 text-gray-500">
        Loading charts...
      </div>
    }>
      <DailyChartsContent />
    </Suspense>
  )
}

