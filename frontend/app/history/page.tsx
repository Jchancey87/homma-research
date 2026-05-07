'use client'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import {
  getTickerHistory, getTickerAppearances, getSectors, getGainersExportUrl,
  TickerHistoryItem, TickerAppearance,
} from '@/lib/api'
import HeatMap from '@/components/HeatMap'
import {
  History, Search, ChevronDown, ChevronUp, ExternalLink,
  BarChart2, TrendingUp, RefreshCw, ArrowUpDown, LayoutGrid, Download,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────
type Period = 'week' | 'month' | 'year' | 'all'
type SortKey = 'last_seen' | 'appearances' | 'avg_gap' | 'first_seen'

// ── Helpers ───────────────────────────────────────────────────────────────────
const PERIOD_LABELS: Record<Period, string> = {
  week: 'This Week', month: 'This Month', year: 'This Year', all: 'All Time',
}

function fmt1(n: number | null, suffix = '') {
  if (n == null) return '—'
  return `${n.toFixed(1)}${suffix}`
}
function fmtFloat(n: number | null) {
  if (n == null) return '—'
  return n >= 1000 ? `${(n / 1000).toFixed(1)}B` : `${n.toFixed(1)}M`
}
function daysBetween(a: string, b: string) {
  return Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86400000)
}

// ── Appearance dot timeline ────────────────────────────────────────────────────
function DotTimeline({ appearances }: { appearances: TickerAppearance[] }) {
  const sorted = [...appearances].sort((a, b) => a.date.localeCompare(b.date))
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {sorted.map(a => (
        <span
          key={a.date}
          title={`${a.date}  gap +${a.gap_pct?.toFixed(1)}%`}
          className="w-2 h-2 rounded-full bg-emerald-400/60 hover:bg-emerald-400 hover:scale-150 transition-all cursor-default"
        />
      ))}
    </div>
  )
}

// ── Expanded detail row ────────────────────────────────────────────────────────
function TickerDetail({
  ticker, period, onResearch,
}: {
  ticker: string
  period: Period
  onResearch: (ticker: string, date: string) => void
}) {
  const [rows, setRows] = useState<TickerAppearance[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTickerAppearances(ticker, period === 'all' ? undefined : period)
      .then(setRows)
      .finally(() => setLoading(false))
  }, [ticker, period])

  if (loading) return (
    <div className="px-6 py-4 text-gray-600 text-sm animate-pulse">Loading appearances…</div>
  )

  return (
    <div className="px-4 pb-4">
      <div className="bg-gray-950 rounded-xl border border-gray-800/60 overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="px-4 py-2 text-left font-medium">Date</th>
              <th className="px-4 py-2 text-right font-medium">Gap %</th>
              <th className="px-4 py-2 text-right font-medium">Float</th>
              <th className="px-4 py-2 text-right font-medium">RVOL</th>
              <th className="px-4 py-2 text-left font-medium">Catalyst</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {rows.map(r => (
              <tr key={r.date} className="hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-2 font-mono text-gray-300">{r.date}</td>
                <td className="px-4 py-2 text-right font-mono text-emerald-400 font-semibold">
                  +{fmt1(r.gap_pct)}%
                </td>
                <td className="px-4 py-2 text-right font-mono text-gray-400">
                  {fmtFloat(r.float_shares != null ? r.float_shares / 1e6 : null)}
                </td>
                <td className="px-4 py-2 text-right font-mono">
                  <span className={r.rvol_15m != null && r.rvol_15m >= 5 ? 'text-amber-400' : 'text-gray-400'}>
                    {fmt1(r.rvol_15m)}x
                  </span>
                </td>
                <td className="px-4 py-2 max-w-xs">
                  {r.news_fresh != null && (
                    <span className={`mr-2 px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      r.news_fresh ? 'bg-emerald-500/20 text-emerald-400' : 'bg-gray-700 text-gray-500'
                    }`}>
                      {r.news_fresh ? '🗞 Fresh' : 'Stale'}
                    </span>
                  )}
                  <span className="text-gray-500 truncate">
                    {r.news_headline || '—'}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <div className="flex items-center gap-1.5 justify-end">
                    <button
                      id={`research-${ticker}-${r.date}`}
                      onClick={() => onResearch(ticker, r.date)}
                      className="flex items-center gap-1 text-gray-600 hover:text-emerald-400 transition-colors"
                      title="Open Research"
                    >
                      <ExternalLink size={11} />
                      <span>Research</span>
                    </button>
                    <button
                      id={`chart-${ticker}-${r.date}`}
                      onClick={() => window.open(`/daily-charts?date=${r.date}`, '_blank')}
                      className="flex items-center gap-1 text-gray-600 hover:text-sky-400 transition-colors"
                      title="Open Daily Charts"
                    >
                      <BarChart2 size={11} />
                      <span>Chart</span>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Ticker row ────────────────────────────────────────────────────────────────
function TickerRow({
  item, period, onResearch,
}: {
  item: TickerHistoryItem
  period: Period
  onResearch: (ticker: string, date: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const spanDays = daysBetween(item.first_seen, item.last_seen)

  return (
    <>
      <tr
        className="hover:bg-gray-800/40 transition-colors cursor-pointer group"
        onClick={() => setExpanded(v => !v)}
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {expanded
              ? <ChevronUp size={13} className="text-emerald-400 shrink-0" />
              : <ChevronDown size={13} className="text-gray-600 group-hover:text-gray-400 shrink-0" />
            }
            <span className="font-bold text-white font-mono text-sm">{item.ticker}</span>
            {item.sector && (
              <span className="text-xs text-gray-600 hidden sm:block">{item.sector}</span>
            )}
          </div>
        </td>
        <td className="px-4 py-3 text-center">
          <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
            item.appearances >= 5 ? 'bg-emerald-500/20 text-emerald-400' :
            item.appearances >= 2 ? 'bg-sky-500/20 text-sky-400' :
            'bg-gray-800 text-gray-400'
          }`}>
            {item.appearances}
          </span>
        </td>
        <td className="px-4 py-3 font-mono text-xs text-gray-400 hidden md:table-cell">
          {item.first_seen}
          {spanDays > 0 && (
            <span className="text-gray-600 ml-1">→ {spanDays}d span</span>
          )}
        </td>
        <td className="px-4 py-3 font-mono text-xs text-gray-300">{item.last_seen}</td>
        <td className="px-4 py-3 text-right font-mono text-emerald-400 font-semibold text-sm">
          +{fmt1(item.avg_gap_pct)}%
        </td>
        <td className="px-4 py-3 text-right font-mono text-xs text-gray-400 hidden lg:table-cell">
          {fmt1(item.max_gap_pct)}%
        </td>
        <td className="px-4 py-3 text-right font-mono text-xs text-gray-400 hidden lg:table-cell">
          {fmt1(item.avg_rvol)}x
        </td>
        <td className="px-4 py-3 text-right font-mono text-xs text-gray-500 hidden xl:table-cell">
          {fmtFloat(item.avg_float_m)}
        </td>
        <td className="px-4 py-3 text-right font-mono text-xs text-gray-400">
          {item.last_close ? `$${item.last_close.toFixed(2)}` : '—'}
        </td>
        <td className="px-4 py-3 text-right font-mono text-xs text-gray-500 hidden sm:table-cell">
          {item.last_market_cap ? (item.last_market_cap >= 1e9 ? `$${(item.last_market_cap/1e9).toFixed(1)}B` : `$${(item.last_market_cap/1e6).toFixed(0)}M`) : '—'}
        </td>
        <td className="px-4 py-3">
          <button
            id={`research-latest-${item.ticker}`}
            onClick={e => { e.stopPropagation(); onResearch(item.ticker, item.last_seen) }}
            className="opacity-0 group-hover:opacity-100 flex items-center gap-1 text-xs text-gray-500 hover:text-emerald-400 transition-all"
          >
            <ExternalLink size={11} />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={9} className="p-0 bg-gray-900/60">
            <TickerDetail ticker={item.ticker} period={period} onResearch={onResearch} />
          </td>
        </tr>
      )}
    </>
  )
}

// ── Sort header ───────────────────────────────────────────────────────────────
function SortTh({
  label, sortKey, current, onSort,
}: {
  label: string
  sortKey: SortKey
  current: SortKey
  onSort: (k: SortKey) => void
}) {
  const active = current === sortKey
  return (
    <th
      className="px-4 py-3 text-xs font-medium text-gray-500 cursor-pointer hover:text-gray-300 transition-colors select-none"
      onClick={() => onSort(sortKey)}
    >
      <span className={`flex items-center gap-1 ${active ? 'text-emerald-400' : ''}`}>
        {label}
        <ArrowUpDown size={10} />
      </span>
    </th>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function HistoryPage() {
  const router = useRouter()

  const [items,    setItems]    = useState<TickerHistoryItem[]>([])
  const [sectors,  setSectors]  = useState<string[]>([])
  const [loading,  setLoading]  = useState(true)
  const [period,   setPeriod]   = useState<Period>('all')
  const [sort,     setSort]     = useState<SortKey>('last_seen')
  const [search,   setSearch]   = useState('')

  // Gainer-style filters
  const [date,      setDate]     = useState('')
  const [minGap,    setMinGap]   = useState('')
  const [maxFloat,  setMaxFloat] = useState('')
  const [minRvol,   setMinRvol]  = useState('')
  const [sector,    setSector]   = useState('')

  const searchRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [data, s] = await Promise.all([
        getTickerHistory({
          period: date ? undefined : period,
          sort,
          search:    search || undefined,
          date:      date || undefined,
          min_gap:   minGap ? Number(minGap) : undefined,
          max_float: maxFloat ? Number(maxFloat) : undefined,
          min_rvol:  minRvol ? Number(minRvol) : undefined,
          sector:    sector || undefined,
          limit:     300,
        }),
        getSectors()
      ])
      setItems(data)
      setSectors(s)
    } finally {
      setLoading(false)
    }
  }, [period, sort, search, date, minGap, maxFloat, minRvol, sector])

  useEffect(() => { load() }, [load])

  const handleResearch = (ticker: string, date: string) => {
    router.push(`/research?ticker=${ticker}&date=${date}`)
  }

  const handleSort = (key: SortKey) => {
    setSort(key)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <LayoutGrid className="text-emerald-400" size={22} />
            Command Center
          </h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Real-time gainers, heatmaps, and full ticker history
          </p>
        </div>
        <div className="flex gap-2 mt-1">
          <a
            href={getGainersExportUrl({ date, min_gap: minGap, max_float: maxFloat, min_rvol: minRvol, sector })}
            download="history_export.csv"
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600/10 border border-emerald-500/30 text-emerald-400 rounded-lg text-xs hover:bg-emerald-600/20 transition-colors"
          >
            <Download size={13} />
            <span>Export CSV</span>
          </a>
          <button
            id="refresh-history"
            onClick={load}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="space-y-4">
        <div className="flex flex-col lg:flex-row items-start lg:items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              id="history-search"
              ref={searchRef}
              placeholder="Search ticker…"
              value={search}
              onChange={e => setSearch(e.target.value.toUpperCase())}
              className="bg-gray-800 border border-gray-700 rounded-lg pl-8 pr-3 py-2 text-white text-sm
                         placeholder-gray-500 focus:outline-none focus:border-emerald-500 w-40 font-mono"
            />
          </div>

          {/* Period tabs (hidden if date filter is active) */}
          {!date && (
            <div className="flex items-center bg-gray-800/60 border border-gray-700 rounded-lg p-0.5 gap-0.5">
              {(Object.keys(PERIOD_LABELS) as Period[]).map(p => (
                <button
                  key={p}
                  id={`period-${p}`}
                  onClick={() => setPeriod(p)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    period === p
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {PERIOD_LABELS[p]}
                </button>
              ))}
            </div>
          )}

          {/* Result count */}
          {!loading && (
            <span className="text-xs text-gray-600 lg:ml-auto">
              {items.length} ticker{items.length !== 1 ? 's' : ''}
              {date ? ` on ${date}` : period !== 'all' ? ` in ${PERIOD_LABELS[period].toLowerCase()}` : ''}
            </span>
          )}
        </div>

        {/* Multi-Filter Bar */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 bg-gray-900/50 border border-gray-800 rounded-xl p-3">
          <div className="space-y-1">
            <label className="text-[10px] uppercase font-bold text-gray-500 ml-1">Specific Date</label>
            <input
              type="date"
              value={date}
              onChange={e => setDate(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] uppercase font-bold text-gray-500 ml-1">Min Gap %</label>
            <input
              type="number"
              placeholder="e.g. 20"
              value={minGap}
              onChange={e => setMinGap(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] uppercase font-bold text-gray-500 ml-1">Max Float (M)</label>
            <input
              type="number"
              placeholder="e.g. 10"
              value={maxFloat}
              onChange={e => setMaxFloat(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] uppercase font-bold text-gray-500 ml-1">Min RVOL</label>
            <input
              type="number"
              placeholder="e.g. 5"
              value={minRvol}
              onChange={e => setMinRvol(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] uppercase font-bold text-gray-500 ml-1">Sector</label>
            <div className="flex gap-2">
              <select
                value={sector}
                onChange={e => setSector(e.target.value)}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500"
              >
                <option value="">All Sectors</option>
                {sectors.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              {(date || minGap || maxFloat || minRvol || sector) && (
                <button
                  onClick={() => { setDate(''); setMinGap(''); setMaxFloat(''); setMinRvol(''); setSector('') }}
                  className="px-2 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-[10px] text-gray-400 hover:text-white"
                >
                  RESET
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Heatmap — period-reactive */}
      <details className="bg-gray-900 border border-gray-800 rounded-2xl group" open>
        <summary className="flex items-center gap-2 px-5 py-3.5 cursor-pointer list-none select-none
                            text-sm font-semibold text-gray-400 hover:text-gray-200 transition-colors">
          <LayoutGrid size={14} className="text-emerald-400 shrink-0" />
          Float × RVOL Heatmap
          <span className="text-xs font-normal text-gray-600 ml-1">
            — {PERIOD_LABELS[period].toLowerCase()} avg gap %
          </span>
          <ChevronDown size={13} className="ml-auto text-gray-600 group-open:rotate-180 transition-transform" />
        </summary>
        <div className="px-5 pb-5 border-t border-gray-800/60 pt-3">
          <HeatMap
            period={date ? undefined : period}
            date={date || undefined}
            minGap={minGap ? Number(minGap) : undefined}
            maxFloat={maxFloat ? Number(maxFloat) : undefined}
            minRvol={minRvol ? Number(minRvol) : undefined}
            sector={sector || undefined}
            height={300}
          />
          <p className="text-[11px] text-gray-700 mt-2">
            Each cell = average gap % for gainers in that float + RVOL bucket · hover for sample count
          </p>
        </div>
      </details>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        <table className="w-full">
          <thead className="border-b border-gray-800 bg-gray-900/80">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Ticker</th>
              <SortTh label="×" sortKey="appearances" current={sort} onSort={handleSort} />
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 hidden md:table-cell">
                First Seen
              </th>
              <SortTh label="Last Seen"  sortKey="last_seen"    current={sort} onSort={handleSort} />
              <SortTh label="Avg Gap"    sortKey="avg_gap"      current={sort} onSort={handleSort} />
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 hidden lg:table-cell">
                Best Gap
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 hidden lg:table-cell">
                Avg RVOL
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 hidden xl:table-cell">
                Avg Float
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">
                Close
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 hidden sm:table-cell">
                Mkt Cap
              </th>
              <th className="px-4 py-3 w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {loading ? (
              Array.from({ length: 12 }).map((_, i) => (
                <tr key={i} className="animate-pulse">
                  {Array.from({ length: 9 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-3 bg-gray-800 rounded w-16" />
                    </td>
                  ))}
                </tr>
              ))
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-16 text-center text-gray-600 text-sm">
                  No tickers found for this period
                  {search ? ` matching "${search}"` : ''}.
                </td>
              </tr>
            ) : (
              items.map(item => (
                <TickerRow
                  key={item.ticker}
                  item={item}
                  period={period}
                  onResearch={handleResearch}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-gray-600">
        <span className="flex items-center gap-1.5">
          <span className="w-5 h-5 rounded-full bg-emerald-500/20 inline-flex items-center justify-center text-emerald-400 font-bold text-[10px]">5</span>
          5+ appearances
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-5 h-5 rounded-full bg-sky-500/20 inline-flex items-center justify-center text-sky-400 font-bold text-[10px]">2</span>
          2–4 appearances
        </span>
        <span>Click any row to expand individual appearances · click Research to open full analysis</span>
      </div>
    </div>
  )
}
