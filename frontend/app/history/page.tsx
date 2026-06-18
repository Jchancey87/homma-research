'use client'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import {
  getTickerHistory, getTickerAppearances, getSectors, getGainersExportUrl,
  TickerHistoryItem, TickerAppearance,
} from '@/lib/api'
import HeatMap from '@/components/HeatMap'
import {
  Search, ChevronDown, ChevronUp, ExternalLink,
  BarChart2, RefreshCw, ArrowUpDown, LayoutGrid, Download,
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
    <div className="px-3 py-4 text-gray-600 text-xs font-mono animate-pulse">Loading appearances…</div>
  )

  return (
    <div className="px-4 pb-3">
      <div className="bg-[#050505] border border-[#262626] overflow-hidden w-full rounded-none">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[#262626]">
              <th className="px-3 py-2 text-left text-[10px] font-mono text-gray-600 uppercase tracking-wider">Date</th>
              <th className="px-3 py-2 text-right text-[10px] font-mono text-gray-600 uppercase tracking-wider">Gap %</th>
              <th className="px-3 py-2 text-right text-[10px] font-mono text-gray-600 uppercase tracking-wider">Float</th>
              <th className="px-3 py-2 text-right text-[10px] font-mono text-gray-600 uppercase tracking-wider">RVOL</th>
              <th className="px-3 py-2 text-left text-[10px] font-mono text-gray-600 uppercase tracking-wider">Catalyst</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.date} className="border-b border-[#1a1a1a] hover:bg-[#0a0a0a] transition-colors">
                <td className="px-3 py-2 font-mono text-xs text-gray-400">{r.date}</td>
                <td className="px-3 py-2 text-right font-mono text-xs text-[#00ff00] font-bold">
                  +{fmt1(r.gap_pct)}%
                </td>
                <td className="px-3 py-2 text-right font-mono text-xs text-gray-500">
                  {fmtFloat(r.float_shares != null ? r.float_shares / 1e6 : null)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-xs">
                  <span className={r.rvol_15m != null && r.rvol_15m >= 5 ? 'text-amber-400' : 'text-gray-500'}>
                    {fmt1(r.rvol_15m)}x
                  </span>
                </td>
                <td className="px-3 py-2 max-w-xs">
                  {r.news_fresh != null && (
                    <span className={`mr-2 px-1.5 py-0.5 font-mono text-[10px] border rounded-none ${
                      r.news_fresh
                        ? 'bg-emerald-950/20 text-[#00ff00] border-[#00ff00]/25'
                        : 'bg-[#111] text-gray-500 border-[#262626]'
                    }`}>
                      {r.news_fresh ? '🗞 Fresh' : 'Stale'}
                    </span>
                  )}
                  <span className="font-mono text-[10px] px-1.5 py-0.5 border border-[#262626] bg-[#111] text-gray-500 rounded-none">
                    {r.news_headline || '—'}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1.5 justify-end">
                    <button
                      id={`research-${ticker}-${r.date}`}
                      onClick={() => onResearch(ticker, r.date)}
                      className="font-mono text-[10px] text-[#00f0ff] border border-[#00f0ff]/30 px-1.5 py-0.5 hover:bg-[#00f0ff]/5 transition-colors rounded-none flex items-center gap-1"
                      title="Open Research"
                    >
                      <ExternalLink size={11} />
                      <span>Research</span>
                    </button>
                    <button
                      id={`chart-${ticker}-${r.date}`}
                      onClick={() => window.open(`/daily-charts?date=${r.date}`, '_blank')}
                      className="font-mono text-[10px] text-gray-600 border border-[#262626] px-1.5 py-0.5 hover:text-white transition-colors rounded-none flex items-center gap-1"
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
        className="border-b border-[#1a1a1a] hover:bg-[#0a0a0a] transition-colors cursor-pointer group"
        onClick={() => setExpanded(v => !v)}
      >
        <td className="px-3 py-2">
          <div className="font-mono font-bold text-white text-xs flex items-center gap-1.5">
            {expanded
              ? <ChevronUp size={13} className="text-gray-600 shrink-0" />
              : <ChevronDown size={13} className="text-gray-600 group-hover:text-gray-400 shrink-0" />
            }
            <span>{item.ticker}</span>
            {item.sector && (
              <span className="text-[10px] text-gray-600 hidden sm:block">{item.sector}</span>
            )}
          </div>
        </td>
        <td className="px-3 py-2 text-center">
          <span className={`px-2 py-0.5 text-[10px] font-mono font-bold border rounded-none ${
            item.appearances >= 5
              ? 'bg-emerald-950/20 text-[#00ff00] border-[#00ff00]/25'
              : item.appearances >= 2
              ? 'bg-[#111] text-gray-400 border-[#262626]'
              : 'bg-[#111] text-gray-500 border-[#262626]'
          }`}>
            {item.appearances}
          </span>
        </td>
        <td className="px-3 py-2 font-mono text-xs text-gray-500 hidden md:table-cell">
          {item.first_seen}
          {spanDays > 0 && (
            <span className="text-gray-600 ml-1">→ {spanDays}d span</span>
          )}
        </td>
        <td className="px-3 py-2 font-mono text-xs text-gray-500">{item.last_seen}</td>
        <td className="px-3 py-2 text-right font-mono text-xs text-[#00ff00] font-bold">
          +{fmt1(item.avg_gap_pct)}%
        </td>
        <td className="px-3 py-2 text-right font-mono text-xs text-gray-400 hidden lg:table-cell">
          {fmt1(item.max_gap_pct)}%
        </td>
        <td className="px-3 py-2 text-right font-mono text-xs text-gray-400 hidden lg:table-cell">
          {fmt1(item.avg_rvol)}x
        </td>
        <td className="px-3 py-2 text-right font-mono text-xs text-gray-500 hidden xl:table-cell">
          {fmtFloat(item.avg_float_m)}
        </td>
        <td className="px-3 py-2 text-right font-mono text-xs text-gray-400">
          {item.last_close ? `$${item.last_close.toFixed(2)}` : '—'}
        </td>
        <td className="px-3 py-2 text-right font-mono text-xs text-gray-500 hidden sm:table-cell">
          {item.last_market_cap ? (item.last_market_cap >= 1e9 ? `$${(item.last_market_cap/1e9).toFixed(1)}B` : `$${(item.last_market_cap/1e6).toFixed(0)}M`) : '—'}
        </td>
        <td className="px-3 py-2">
          <button
            id={`research-latest-${item.ticker}`}
            onClick={e => { e.stopPropagation(); onResearch(item.ticker, item.last_seen) }}
            className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-[#00f0ff] transition-colors flex items-center gap-1"
          >
            <ExternalLink size={11} />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={9} className="p-0 bg-[#0a0a0a] border-b border-[#262626]">
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
      className={`px-3 py-2 text-[10px] font-mono uppercase tracking-wider cursor-pointer hover:text-white select-none whitespace-nowrap transition-colors ${active ? 'text-[#00ff00]' : 'text-gray-500'}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="flex items-center gap-1">
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
  const [period,   setPeriod]   = useState<Period>('week')
  const [sort,     setSort]     = useState<SortKey>('last_seen')
  const [search,   setSearch]   = useState('')

  const [date,      setDate]     = useState('')
  const [minGap,    setMinGap]   = useState('')
  const [maxFloat,  setMaxFloat] = useState('200')
  const [minRvol,   setMinRvol]  = useState('2')
  const [minPrice,  setMinPrice] = useState('2')
  const [maxPrice,  setMaxPrice] = useState('20')
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
          min_price: minPrice ? Number(minPrice) : undefined,
          max_price: maxPrice ? Number(maxPrice) : undefined,
        }),
        getSectors()
      ])
      setItems(data)
      setSectors(s)
    } finally {
      setLoading(false)
    }
  }, [period, sort, search, date, minGap, maxFloat, minRvol, sector, minPrice, maxPrice])

  useEffect(() => { load() }, [load])

  const handleResearch = (ticker: string, date: string) => {
    router.push(`/research?ticker=${ticker}&date=${date}`)
  }

  const handleSort = (key: SortKey) => {
    setSort(key)
  }

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-[#050505] border border-[#262626]">
        <div>
          <h1 className="font-mono text-sm font-bold text-white uppercase flex items-center gap-1.5">
            <LayoutGrid size={14} className="text-[#00ff00]" />
            Command Center
          </h1>
          <p className="font-mono text-[10px] text-gray-500">
            {!loading && `${items.length} ticker${items.length !== 1 ? 's' : ''}${date ? ` on ${date}` : period !== 'all' ? ` · ${PERIOD_LABELS[period].toLowerCase()}` : ''}`}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <a
            href={getGainersExportUrl({ date, min_gap: minGap, max_float: maxFloat, min_rvol: minRvol, sector, min_price: minPrice, max_price: maxPrice })}
            download="history_export.csv"
            className="flex items-center gap-1 px-2.5 py-1 border border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00] text-[11px] font-mono hover:bg-emerald-950/30 transition-colors rounded-none"
          >
            <Download size={11} />
            <span>Export CSV</span>
          </a>
          <button
            id="refresh-history"
            onClick={load}
            className="p-1.5 border border-[#262626] bg-black text-gray-400 hover:text-white transition-colors rounded-none"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {/* Filter/Search Bar */}
      <div className="flex flex-wrap items-center gap-1.5 p-2 bg-[#0a0a0a] border border-[#262626]">
        {/* Search */}
        <div className="relative">
          <Search size={11} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            id="history-search"
            ref={searchRef}
            placeholder="Search ticker…"
            value={search}
            onChange={e => setSearch(e.target.value.toUpperCase())}
            className="bg-black border border-[#262626] text-white font-mono text-[11px] focus:outline-none focus:border-[#00ff00] rounded-none pl-6 pr-2 py-1 w-36 [color-scheme:dark]"
          />
        </div>

        {/* Period tabs (hidden if date filter is active) */}
        {!date && (
          <div className="flex bg-black border border-[#262626]">
            {(Object.keys(PERIOD_LABELS) as Period[]).map(p => (
              <button
                key={p}
                id={`period-${p}`}
                onClick={() => setPeriod(p)}
                className={`px-2.5 py-1 text-[11px] font-mono border-r border-[#262626] last:border-r-0 transition-colors rounded-none ${
                  period === p
                    ? 'border-b-2 border-b-[#00ff00] text-[#00ff00] bg-emerald-950/10'
                    : 'text-gray-500 hover:text-white'
                }`}
              >
                {PERIOD_LABELS[p]}
              </button>
            ))}
          </div>
        )}

        <div className="flex items-center gap-1 ml-auto">
          {/* Specific Date */}
          <input
            type="date"
            value={date}
            onChange={e => setDate(e.target.value)}
            className="bg-black border border-[#262626] text-white font-mono text-[11px] focus:outline-none focus:border-[#00ff00] rounded-none px-2 py-1 [color-scheme:dark]"
          />
          {/* Price Min */}
          <input
            type="number"
            placeholder="$Min"
            value={minPrice}
            onChange={e => setMinPrice(e.target.value)}
            className="bg-black border border-[#262626] text-white font-mono text-[11px] focus:outline-none focus:border-[#00ff00] rounded-none px-2 py-1 w-16 [color-scheme:dark]"
          />
          {/* Price Max */}
          <input
            type="number"
            placeholder="$Max"
            value={maxPrice}
            onChange={e => setMaxPrice(e.target.value)}
            className="bg-black border border-[#262626] text-white font-mono text-[11px] focus:outline-none focus:border-[#00ff00] rounded-none px-2 py-1 w-16 [color-scheme:dark]"
          />
          {/* Max Float */}
          <input
            type="number"
            placeholder="Float≤"
            value={maxFloat}
            onChange={e => setMaxFloat(e.target.value)}
            className="bg-black border border-[#262626] text-white font-mono text-[11px] focus:outline-none focus:border-[#00ff00] rounded-none px-2 py-1 w-16 [color-scheme:dark]"
          />
          {/* Min RVOL */}
          <input
            type="number"
            placeholder="RVOL≥"
            value={minRvol}
            onChange={e => setMinRvol(e.target.value)}
            className="bg-black border border-[#262626] text-white font-mono text-[11px] focus:outline-none focus:border-[#00ff00] rounded-none px-2 py-1 w-16 [color-scheme:dark]"
          />
          {/* Sector */}
          <select
            value={sector}
            onChange={e => setSector(e.target.value)}
            className="bg-black border border-[#262626] text-white font-mono text-[11px] focus:outline-none focus:border-[#00ff00] rounded-none px-2 py-1 [color-scheme:dark]"
          >
            <option value="">All Sectors</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          {/* Reset */}
          {(date || minGap || maxFloat || minRvol || sector || minPrice || maxPrice) && (
            <button
              onClick={() => { setDate(''); setMinGap(''); setMaxFloat(''); setMinRvol(''); setSector(''); setMinPrice(''); setMaxPrice('') }}
              className="px-2.5 py-1 border border-[#262626] bg-black text-gray-500 hover:text-white font-mono text-[11px] transition-colors rounded-none"
            >
              RESET
            </button>
          )}
        </div>
      </div>

      {/* Heatmap — period-reactive */}
      <details className="bg-[#050505] border border-[#262626] group" open>
        <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer list-none select-none
                            font-mono text-[11px] font-bold text-gray-400 uppercase tracking-widest hover:text-gray-200 transition-colors">
          <LayoutGrid size={12} className="text-[#00ff00] shrink-0" />
          Float × RVOL Heatmap
          <span className="text-[10px] font-normal text-gray-600 ml-1 normal-case tracking-normal">
            — {PERIOD_LABELS[period].toLowerCase()} avg gap %
          </span>
          <ChevronDown size={12} className="ml-auto text-gray-600 group-open:rotate-180 transition-transform" />
        </summary>
        <div className="px-3 pb-3 border-t border-[#262626] pt-2">
          <HeatMap
            period={date ? undefined : period}
            date={date || undefined}
            minGap={minGap ? Number(minGap) : undefined}
            maxFloat={maxFloat ? Number(maxFloat) : undefined}
            minRvol={minRvol ? Number(minRvol) : undefined}
            sector={sector || undefined}
            height={300}
          />
          <p className="text-[10px] font-mono text-gray-700 mt-2">
            Each cell = average gap % for gainers in that float + RVOL bucket · hover for sample count
          </p>
        </div>
      </details>

      {/* Table */}
      <div className="bg-black border border-[#262626] overflow-hidden">
        <table className="w-full">
          <thead className="bg-[#050505] border-b border-[#262626]">
            <tr>
              <th className="px-3 py-2 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">Ticker</th>
              <SortTh label="×" sortKey="appearances" current={sort} onSort={handleSort} />
              <th className="px-3 py-2 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider hidden md:table-cell">
                First Seen
              </th>
              <SortTh label="Last Seen"  sortKey="last_seen"    current={sort} onSort={handleSort} />
              <SortTh label="Avg Gap"    sortKey="avg_gap"      current={sort} onSort={handleSort} />
              <th className="px-3 py-2 text-right text-[10px] font-mono text-gray-500 uppercase tracking-wider hidden lg:table-cell">
                Best Gap
              </th>
              <th className="px-3 py-2 text-right text-[10px] font-mono text-gray-500 uppercase tracking-wider hidden lg:table-cell">
                Avg RVOL
              </th>
              <th className="px-3 py-2 text-right text-[10px] font-mono text-gray-500 uppercase tracking-wider hidden xl:table-cell">
                Avg Float
              </th>
              <th className="px-3 py-2 text-right text-[10px] font-mono text-gray-500 uppercase tracking-wider">
                Close
              </th>
              <th className="px-3 py-2 text-right text-[10px] font-mono text-gray-500 uppercase tracking-wider hidden sm:table-cell">
                Mkt Cap
              </th>
              <th className="px-3 py-2 w-8" />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 12 }).map((_, i) => (
                <tr key={i} className="border-b border-[#1a1a1a]">
                  {Array.from({ length: 9 }).map((_, j) => (
                    <td key={j} className="px-3 py-2">
                      <div className="animate-pulse bg-[#111] h-3 w-16 rounded-none" />
                    </td>
                  ))}
                </tr>
              ))
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={9}>
                  <div className="flex flex-col items-center justify-center py-16 gap-2 bg-[#050505]">
                    <BarChart2 size={24} className="text-gray-700" />
                    <span className="text-gray-500 text-xs uppercase tracking-wider font-mono">
                      No tickers found{search ? ` matching "${search}"` : ' for this period'}
                    </span>
                  </div>
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
      <div className="flex items-center gap-4 px-1 font-mono text-[10px] text-gray-600">
        <span className="flex items-center gap-1.5">
          <span className="px-1.5 py-0.5 bg-emerald-950/20 text-[#00ff00] border border-[#00ff00]/25 font-bold rounded-none">5+</span>
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
