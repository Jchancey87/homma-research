'use client'
import { useEffect, useState, useCallback, useMemo, Suspense } from 'react'
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
  const [priceFilterEnabled, setPriceFilterEnabled] = useState(true)

  // Sync price filter with localStorage / main screener
  useEffect(() => {
    const val = localStorage.getItem('price-filter-enabled')
    if (val !== null) {
      setPriceFilterEnabled(val === 'true')
    }
    const handleSync = () => {
      const syncedVal = localStorage.getItem('price-filter-enabled')
      if (syncedVal !== null) {
        setPriceFilterEnabled(syncedVal === 'true')
      }
    }
    window.addEventListener('price-filter-changed', handleSync)
    return () => window.removeEventListener('price-filter-changed', handleSync)
  }, [])

  // ── Fetch summary for the active date ──────────────────────────────────────
  const load = useCallback(async () => {
    setLoading(true)
    try {
      // Discover the most recent ingest date
      const s = await getGainersSummary()
      if (!s.date) {
        setSummary({ date: null, total: 0, gainers: [] })
        return
      }

      const targetDate = activeDate || s.date
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5000'}/api/gainers?date=${targetDate}`
      )
      const rows = await res.json()

      setSummary({
        date:    targetDate,
        total:   rows.length,
        gainers: rows.map((g: Gainer) => ({
          ticker:       g.ticker,
          gap_pct:      g.gap_pct,
          extended_change_pct: g.extended_change_pct,
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
    } catch {
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }, [activeDate])

  // Filter gainers by price and grab the top 9
  const displayGainers = useMemo(() => {
    if (!summary?.gainers) return []
    const list = [...summary.gainers]
    // Guarantee descending sort by aligned change % (extended hours close change if available, else gap)
    list.sort((a, b) => {
      const valA = a.extended_change_pct ?? a.gap_pct ?? 0
      const valB = b.extended_change_pct ?? b.gap_pct ?? 0
      return valB - valA
    })
    if (!priceFilterEnabled) return list.slice(0, 9)
    return list
      .filter(g => g.close_price != null && g.close_price >= 2.0 && g.close_price <= 25.0)
      .slice(0, 9)
  }, [summary, priceFilterEnabled])

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
    <div className="space-y-2 p-2 bg-black min-h-screen text-gray-400 font-mono text-xs">
      {/* ── Header ── */}
      <div className="flex items-center justify-between gap-4 px-3 py-2 bg-[#050505] border border-[#262626] rounded-none">
        <div>
          <h1 className="text-sm font-bold text-white flex items-center gap-1.5 uppercase">
            <BarChart2 className="text-[#00ff00]" size={16} />
            Daily Chart Overview
          </h1>
          <p className="text-gray-500 text-[10px] mt-0.5 uppercase">
            Top 9 intraday sessions · candlestick + volume + EMA 21, 50, 100
          </p>
        </div>

        {/* Date controls */}
        <div className="flex items-center gap-1.5 shrink-0 select-none">
          <button
            onClick={() => {
              const newValue = !priceFilterEnabled
              setPriceFilterEnabled(newValue)
              localStorage.setItem('price-filter-enabled', String(newValue))
              window.dispatchEvent(new Event('price-filter-changed'))
            }}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-none text-[10px] font-bold border transition-all ${
              priceFilterEnabled
                ? 'bg-emerald-950/20 border-[#00ff00]/40 text-[#00ff00] hover:bg-emerald-950/40'
                : 'bg-black border-[#262626] text-gray-500 hover:text-gray-300'
            }`}
          >
            <span>$2-$25 Filter</span>
            {priceFilterEnabled ? (
              <span className="w-1.5 h-1.5 bg-[#00ff00] animate-pulse" />
            ) : (
              <span className="w-1.5 h-1.5 bg-gray-700" />
            )}
          </button>

          <button
            id="prev-day"
            onClick={() => activeDate && goDate(addDays(activeDate, -1))}
            disabled={!activeDate}
            className="p-1.5 rounded-none border border-[#262626] text-gray-400 hover:text-white bg-black disabled:opacity-30 transition-colors"
          >
            <ChevronLeft size={14} />
          </button>

          <input
            id="date-picker"
            type="date"
            value={activeDate}
            max={todayET()}
            onChange={e => e.target.value && goDate(e.target.value)}
            className="bg-black border border-[#262626] rounded-none px-2 py-1 text-white text-[11px] font-mono
                       focus:outline-none focus:border-[#00ff00] [color-scheme:dark]"
          />

          <button
            id="next-day"
            onClick={() => activeDate && activeDate < todayET() && goDate(addDays(activeDate, 1))}
            disabled={!activeDate || activeDate >= todayET()}
            className="p-1.5 rounded-none border border-[#262626] text-gray-400 hover:text-white bg-black disabled:opacity-30 transition-colors"
          >
            <ChevronRight size={14} />
          </button>

          <button
            id="refresh-charts"
            onClick={load}
            className="p-1.5 rounded-none border border-[#262626] text-gray-400 hover:text-white bg-black transition-colors"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* ── Date label + stats bar ── */}
      {!loading && summary?.date && (
        <div className="flex items-center gap-4 px-3 py-1.5 bg-[#0a0a0a] border border-[#262626] rounded-none text-[11px]">
          <span className="font-bold text-gray-300 uppercase">{dateLabel}</span>
          <span className="px-2 py-0.5 rounded-none text-[10px] bg-emerald-950/20 text-[#00ff00] border border-[#00ff00]/25 font-bold">
            {summary.total} gainers ingested
          </span>
          <span className="text-gray-500">
            Showing top {displayGainers.length} by gap % {priceFilterEnabled ? '(filtered $2-$25)' : ''}
          </span>
          <span className="ml-auto text-gray-650 text-[10px] uppercase">
            Click any chart to open full research panel
          </span>
        </div>
      )}

      {/* ── State: loading ── */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-[1px] bg-[#262626] border border-[#262626] rounded-none">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="bg-black h-[250px] rounded-none animate-pulse" />
          ))}
        </div>
      )}

      {/* ── State: no data ── */}
      {!loading && (!summary || !summary.date || displayGainers.length === 0) && (
        <div className="flex flex-col items-center justify-center py-24 gap-3 bg-[#050505] border border-[#262626] rounded-none">
          <Search size={32} className="text-gray-700" />
          <p className="text-gray-500 text-xs uppercase tracking-wider font-bold">No ingest data found for this date.</p>
          <p className="text-gray-600 text-[10px] uppercase">Try a different date or run the ingestion job first.</p>
        </div>
      )}

      {/* ── Chart grid ── */}
      {!loading && summary && displayGainers.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-[1px] bg-[#262626] border border-[#262626] rounded-none">
          {displayGainers.map((g, idx) => {
            const pipe = pipeMap[g.ticker]
            return (
              <MiniSessionChart
                key={g.ticker}
                ticker={g.ticker}
                date={summary.date!}
                gapPct={g.extended_change_pct ?? g.gap_pct}
                float={g.float_shares}
                rvol={g.rvol_15m}
                rank={idx + 1}
                pipe={pipe}
                onExpand={handleExpand}
              />
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

