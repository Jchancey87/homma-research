'use client'
import { useEffect, useState, useCallback, useMemo, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  getGainersSummary, getPipeScan, getGainersByDate,
  PipeScanResult, Gainer, getLiveGainers, LiveGainerRow,
  GainerSummary,
} from '@/lib/api'
import MiniSessionChart from '@/components/MiniSessionChart'
import { BarChart2, RefreshCw, ChevronLeft, ChevronRight, Search, Radio, Wifi } from 'lucide-react'
import { addDays, todayET } from '@/lib/format'

// Normalise raw `/api/gainers?date=...` rows into the unified summary shape.
function mapDbRowsToSummary(rows: Gainer[], date: string): GainerSummary | null {
  if (!rows || rows.length === 0) return null
  return {
    date,
    total: rows.length,
    source: 'db',
    gainers: rows.map((g) => ({
      ticker:              g.ticker,
      gap_pct:             g.gap_pct,
      extended_change_pct: g.extended_change_pct,
      float_shares:        g.float_shares,
      rvol_15m:            g.rvol_15m,
      sector:              g.sector,
      news_headline:       g.news_headline,
      news_fresh:          g.news_fresh,
      close_price:         g.close_price,
      open_price:          g.open_price,
      mom_2m:              null,
    })),
  }
}

// Normalise live screener rows into the unified summary shape. Live rows
// don't carry extended_change_pct; we map last_price → close_price so the
// downstream sort/filter can use the same field.
function mapLiveRowsToSummary(rows: LiveGainerRow[], date: string): GainerSummary {
  return {
    date,
    total: rows.length,
    source: 'live',
    gainers: rows.map((g) => ({
      ticker:              g.ticker,
      gap_pct:             g.gap_pct,
      extended_change_pct: null,
      float_shares:        g.float_shares ?? null,
      rvol_15m:            g.rvol_15m ?? null,
      sector:              g.sector ?? null,
      news_headline:       g.news_headline ?? null,
      news_fresh:          g.news_fresh ?? null,
      close_price:         g.last_price ?? null,
      open_price:          g.open_price ?? null,
      mom_2m:              g.mom_2m ?? null,
    })),
  }
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
  // True when the displayed list is the live screener (today, in-session).
  // Drives the header badges, subtitle, and the 30s ticker-list-rotation
  // timer. Separate from `summary.source` so the page-level effect doesn't
  // need to reach into the summary object.
  const [isLiveMode, setIsLiveMode] = useState(false)

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

  // ── Initial load — dispatches live vs DB vs past-date ─────────────────────
  const loadSummary = useCallback(async () => {
    setLoading(true)
    try {
      const today = todayET()
      const isToday = !activeDate || activeDate === today
      const targetDate = activeDate || today

      if (isToday) {
        // Today: try live screener first.
        const snapshot = await getLiveGainers()
        if (snapshot?.gainers?.length) {
          setSummary(mapLiveRowsToSummary(snapshot.gainers, today))
          setIsLiveMode(true)
          if (!activeDate) setActiveDate(today)
          return
        }
        // Defensive: live screener empty (closed session, pre-4 AM, backend
        // down) — one-shot fallback to the most recent DB ingest. The 30s
        // ticker-rotation timer must NOT re-trigger this path; it's only
        // meant to fire on initial mount / manual refresh.
        const s = await getGainersSummary()
        const dbDate = s.date || today
        const rows = await getGainersByDate(dbDate)
        const mapped = mapDbRowsToSummary(rows, dbDate)
        if (mapped) {
          setSummary(mapped)
          setIsLiveMode(false)
          if (!activeDate) setActiveDate(dbDate)
        } else {
          setSummary({ date: null, total: 0, source: null, gainers: [] })
          setIsLiveMode(false)
        }
        return
      }

      // Past date: static DB ingest (no live data for closed sessions).
      const rows = await getGainersByDate(targetDate)
      const mapped = mapDbRowsToSummary(rows, targetDate)
      if (mapped) {
        setSummary(mapped)
        setIsLiveMode(false)
      } else {
        setSummary({ date: null, total: 0, source: null, gainers: [] })
        setIsLiveMode(false)
      }
    } catch {
      setSummary(null)
      setIsLiveMode(false)
    } finally {
      setLoading(false)
    }
  }, [activeDate])

  // ── 30s ticker list rotation (live mode only) ────────────────────────────
  // Sole job: pull the live screener so displayed tickers rotate as gaps
  // change. Does NOT re-run the DB fallback — that path is a one-shot for
  // closed-session / pre-4 AM, handled in loadSummary().
  const refreshLiveGainers = useCallback(async () => {
    try {
      const snapshot = await getLiveGainers()
      if (snapshot?.gainers?.length) {
        setSummary(mapLiveRowsToSummary(snapshot.gainers, todayET()))
      }
    } catch {
      // Best-effort: keep the last good summary on transient errors.
    }
  }, [])

  // Gainers to display — sort, price-filter, slice the unified array.
  const displayGainers = useMemo(() => {
    if (!summary?.gainers?.length) return []
    const list = [...summary.gainers]
    // Descending by aligned change % (extended hours close change if
    // available, else gap). Live rows always have extended_change_pct=null.
    list.sort((a, b) => {
      const valA = a.extended_change_pct ?? a.gap_pct ?? 0
      const valB = b.extended_change_pct ?? b.gap_pct ?? 0
      return valB - valA
    })
    const filtered = priceFilterEnabled
      ? list.filter(g => g.close_price != null && g.close_price >= 2.0 && g.close_price <= 25.0)
      : list
    return filtered.slice(0, 9)
  }, [summary, priceFilterEnabled])

  useEffect(() => { loadSummary() }, [loadSummary])

  // Live polling — keep the screener list and mom_2m values fresh. The live
  // screener's background refresh runs at 60s (live_screener.py CACHE_TTL_SECONDS)
  // but mom_2m is updated inline between refreshes, so 30s is a reasonable
  // cadence for ticker rotation.
  useEffect(() => {
    if (!isLiveMode) return
    const id = setInterval(() => {
      refreshLiveGainers()
    }, 30_000)
    return () => clearInterval(id)
  }, [isLiveMode, refreshLiveGainers])

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
            {isLiveMode && (
              <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-none text-[9px] font-bold bg-amber-950/30 border border-amber-500/40 text-amber-400 animate-pulse">
                <Radio size={9} />
                LIVE
              </span>
            )}
            {isLiveMode && (
              <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-none text-[9px] font-bold bg-emerald-950/20 border border-emerald-500/30 text-emerald-400">
                <Wifi size={9} />
                live · top 9 by gap %
              </span>
            )}
          </h1>
          <p className="text-gray-500 text-[10px] mt-0.5 uppercase">
            {isLiveMode
              ? 'bars 15s · tick 5s · list 30s · candlestick + volume + EMA 21, 50, 100'
              : 'Top 9 intraday sessions · candlestick + volume + EMA 21, 50, 100'}
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
            onClick={loadSummary}
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
          {isLiveMode ? (
            <span className="px-2 py-0.5 rounded-none text-[10px] bg-amber-950/20 text-amber-400 border border-amber-500/25 font-bold">
              live · {displayGainers.length} displayed
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded-none text-[10px] bg-emerald-950/20 text-[#00ff00] border border-[#00ff00]/25 font-bold">
              {summary.total} gainers ingested
            </span>
          )}
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
                mom_2m={g.mom_2m ?? null}
                autoRefreshMs={isLiveMode || summary.date === todayET() ? 15_000 : undefined}
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
