'use client'
import { useState, useEffect } from 'react'
import { Download, RefreshCw } from 'lucide-react'
import { getGainers, getSectors, getGainersExportUrl, Gainer } from '@/lib/api'
import { fmtFloat } from '@/lib/format'

export default function GainersPage() {
  const [gainers, setGainers]   = useState<Gainer[]>([])
  const [sectors, setSectors]   = useState<string[]>([])
  const [loading, setLoading]   = useState(true)
  const [sortKey, setSortKey]   = useState<keyof Gainer | null>(null)
  const [sortDir, setSortDir]   = useState<'asc' | 'desc'>('desc')

  // Filter state
  const [date, setDate]         = useState('')
  const [minGap, setMinGap]     = useState('')
  const [maxFloat, setMaxFloat] = useState('')
  const [minRvol, setMinRvol]   = useState('')
  const [sector, setSector]     = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const params: Parameters<typeof getGainers>[0] = {}
      if (date)     params.date      = date
      if (minGap)   params.min_gap   = Number(minGap)
      if (maxFloat) params.max_float = Number(maxFloat)
      if (minRvol)  params.min_rvol  = Number(minRvol)
      if (sector)   params.sector    = sector
      const [g, s] = await Promise.all([getGainers(params), getSectors()])
      setGainers(g); setSectors(s)
    } finally { setLoading(false) }
  }

  useEffect(() => {
    const loadInitial = async () => {
      setLoading(true)
      try {
        const [g, s] = await Promise.all([getGainers({}), getSectors()])
        setGainers(g); setSectors(s)
      } finally {
        setLoading(false)
      }
    }
    loadInitial()
  }, [])

  const sorted = [...gainers].sort((a, b) => {
    if (!sortKey) return 0 // Respect backend order if no manual sort active
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const av = a[sortKey] as any, bv = b[sortKey] as any
    if (av === bv) {
      // Tie-break with gap_pct if sorting by date or other fields
      if (sortKey !== 'gap_pct') {
        return (b.gap_pct ?? 0) - (a.gap_pct ?? 0)
      }
      return 0
    }
    if (av == null) return 1; if (bv == null) return -1
    return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })

  const toggleSort = (k: keyof Gainer) => {
    if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(k); setSortDir('desc') }
  }

  const fmtCap   = (v: number | null) => v == null ? '—' : v >= 1e9 ? `$${(v/1e9).toFixed(1)}B` : `$${(v/1e6).toFixed(0)}M`

  const Th = ({ col, label }: { col: keyof Gainer; label: string }) => (
    <th onClick={() => toggleSort(col)}
      className="px-3 py-2 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider cursor-pointer hover:text-white select-none whitespace-nowrap">
      {label} {sortKey === col ? (sortDir === 'desc' ? '↓' : '↑') : ''}
    </th>
  )

  const exportUrl = getGainersExportUrl({ date, min_gap: minGap, max_float: maxFloat, min_rvol: minRvol, sector })

  return (
    <div className="space-y-2 p-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-[#050505] border border-[#262626]">
        <div>
          <h1 className="font-mono text-sm font-bold text-white uppercase">Daily Gainers</h1>
          <p className="font-mono text-[10px] text-gray-500">{gainers.length} records</p>
        </div>
        <div className="flex gap-1.5">
          <button onClick={load}
            className="flex items-center gap-1.5 px-2.5 py-1 border border-[#262626] bg-black text-gray-400 text-[11px] font-mono hover:text-white transition-colors rounded-none">
            <RefreshCw size={12} /> Refresh
          </button>
          <a href={exportUrl} download="gainers.csv"
            className="flex items-center gap-1.5 px-2.5 py-1 border border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00] text-[11px] font-mono hover:bg-emerald-950/30 transition-colors rounded-none">
            <Download size={12} /> Export CSV
          </a>
        </div>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-1.5 bg-[#0a0a0a] border border-[#262626] p-2">
        <input type="date" value={date} onChange={e => setDate(e.target.value)}
          className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark] w-full" />
        <input type="number" placeholder="Min Gap %" value={minGap} onChange={e => setMinGap(e.target.value)}
          className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark] w-full" />
        <input type="number" placeholder="Max Float (M)" value={maxFloat} onChange={e => setMaxFloat(e.target.value)}
          className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark] w-full" />
        <input type="number" placeholder="Min RVOL" value={minRvol} onChange={e => setMinRvol(e.target.value)}
          className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark] w-full" />
        <div className="flex gap-1.5">
          <select value={sector} onChange={e => setSector(e.target.value)}
            className="flex-1 bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark] w-full">
            <option value="">All sectors</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <button onClick={load}
            className="px-4 py-1.5 bg-black border border-[#00ff00]/40 text-[#00ff00] text-[11px] font-mono hover:bg-emerald-950/20 transition-colors rounded-none">
            Filter
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-black border border-[#262626] overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-600 text-xs font-mono animate-pulse">Loading…</div>
        ) : sorted.length === 0 ? (
          <div className="p-8 text-center text-gray-600 text-xs font-mono">No gainers found. Run the ingestion job or adjust filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#050505] border-b border-[#262626]">
                <tr>
                  <Th col="date"         label="Date" />
                  <Th col="ticker"       label="Ticker" />
                  <Th col="gap_pct"      label="Gap %" />
                  <Th col="float_shares" label="Float" />
                  <Th col="rvol_15m"     label="RVOL" />
                  <Th col="sector"       label="Sector" />
                  <Th col="market_cap"   label="Mkt Cap" />
                  <Th col="close_price"  label="Close" />
                  <th className="px-3 py-2 text-left text-[10px] font-mono text-gray-500 uppercase tracking-wider">News</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map(g => (
                  <tr key={g.id} className="border-b border-[#1a1a1a] hover:bg-[#0a0a0a] transition-colors">
                    <td className="px-3 py-2 font-mono text-xs text-gray-500">{g.date}</td>
                    <td className="px-3 py-2 font-mono text-xs font-bold text-white">{g.ticker}</td>
                    <td className="px-3 py-2 font-mono text-xs text-[#00ff00]">
                      {g.gap_pct != null ? `+${g.gap_pct}%` : '—'}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-400">{fmtFloat(g.float_shares)}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-400">{g.rvol_15m != null ? `${g.rvol_15m}x` : '—'}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-400">{g.sector ?? '—'}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-400">{fmtCap(g.market_cap)}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-400">{g.close_price != null ? `$${g.close_price}` : '—'}</td>
                    <td className="px-3 py-2">
                      {g.news_fresh == null ? '—' : g.news_fresh
                        ? <span className="text-[10px] bg-emerald-950/20 text-[#00ff00] border border-[#00ff00]/25 px-1.5 py-0.5 font-mono rounded-none">Fresh</span>
                        : <span className="text-[10px] bg-[#111] text-gray-500 border border-[#262626] px-1.5 py-0.5 font-mono rounded-none">Stale</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
