'use client'
import { useState, useEffect } from 'react'
import { Download, RefreshCw } from 'lucide-react'
import { getGainers, getSectors, getGainersExportUrl, Gainer } from '@/lib/api'

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

  const fmtFloat = (v: number | null) => v == null ? '—' : `${(v / 1e6).toFixed(1)}M`
  const fmtCap   = (v: number | null) => v == null ? '—' : v >= 1e9 ? `$${(v/1e9).toFixed(1)}B` : `$${(v/1e6).toFixed(0)}M`

  const Th = ({ col, label }: { col: keyof Gainer; label: string }) => (
    <th onClick={() => toggleSort(col)}
      className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wide cursor-pointer hover:text-white select-none whitespace-nowrap">
      {label} {sortKey === col ? (sortDir === 'desc' ? '↓' : '↑') : ''}
    </th>
  )

  const exportUrl = getGainersExportUrl({ date, min_gap: minGap, max_float: maxFloat, min_rvol: minRvol, sector })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Daily Gainers</h1>
          <p className="text-gray-400 text-sm mt-1">{gainers.length} records</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load}
            className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-300 hover:border-gray-500 transition-colors">
            <RefreshCw size={14} /> Refresh
          </button>
          <a href={exportUrl} download="gainers.csv"
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600/20 border border-emerald-500/40 text-emerald-300 rounded-lg text-sm hover:bg-emerald-600/30 transition-colors">
            <Download size={14} /> Export CSV
          </a>
        </div>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 bg-gray-900 border border-gray-800 rounded-xl p-4">
        <input type="date" value={date} onChange={e => setDate(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <input type="number" placeholder="Min Gap %" value={minGap} onChange={e => setMinGap(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <input type="number" placeholder="Max Float (M)" value={maxFloat} onChange={e => setMaxFloat(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <input type="number" placeholder="Min RVOL" value={minRvol} onChange={e => setMinRvol(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <div className="flex gap-2">
          <select value={sector} onChange={e => setSector(e.target.value)}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500">
            <option value="">All sectors</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <button onClick={load}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors">
            Filter
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-500 text-sm">Loading…</div>
        ) : sorted.length === 0 ? (
          <div className="p-12 text-center text-gray-500 text-sm">No gainers found. Run the ingestion job or adjust filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-800/60 border-b border-gray-700">
                <tr>
                  <Th col="date"         label="Date" />
                  <Th col="ticker"       label="Ticker" />
                  <Th col="gap_pct"      label="Gap %" />
                  <Th col="float_shares" label="Float" />
                  <Th col="rvol_15m"     label="RVOL" />
                  <Th col="sector"       label="Sector" />
                  <Th col="market_cap"   label="Mkt Cap" />
                  <Th col="close_price"  label="Close" />
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">News</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {sorted.map(g => (
                  <tr key={g.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="px-4 py-3 text-gray-400">{g.date}</td>
                    <td className="px-4 py-3 font-semibold text-white">{g.ticker}</td>
                    <td className="px-4 py-3">
                      <span className={`font-medium ${(g.gap_pct ?? 0) >= 10 ? 'text-emerald-400' : 'text-emerald-300'}`}>
                        {g.gap_pct != null ? `+${g.gap_pct}%` : '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-300">{fmtFloat(g.float_shares)}</td>
                    <td className="px-4 py-3 text-gray-300">{g.rvol_15m != null ? `${g.rvol_15m}x` : '—'}</td>
                    <td className="px-4 py-3 text-gray-400">{g.sector ?? '—'}</td>
                    <td className="px-4 py-3 text-gray-400">{fmtCap(g.market_cap)}</td>
                    <td className="px-4 py-3 text-gray-300">{g.close_price != null ? `$${g.close_price}` : '—'}</td>
                    <td className="px-4 py-3">
                      {g.news_fresh == null ? '—' : g.news_fresh
                        ? <span className="text-xs bg-emerald-500/15 text-emerald-300 px-2 py-0.5 rounded-full">Fresh</span>
                        : <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded-full">Stale</span>}
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
