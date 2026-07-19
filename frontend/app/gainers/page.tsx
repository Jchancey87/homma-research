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
      className="px-3 py-2 text-left text-[10px] font-mono text-text-muted uppercase tracking-wider cursor-pointer hover:text-text-primary select-none whitespace-nowrap">
      {label} {sortKey === col ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
    </th>
  )

  const exportUrl = getGainersExportUrl({ date, min_gap: minGap, max_float: maxFloat, min_rvol: minRvol, sector })

  return (
    <div className="space-y-2 p-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-panel border border-border-subtle shadow-sm">
        <div>
          <h1 className="font-mono text-sm font-bold text-text-primary uppercase">Daily Gainers</h1>
          <p className="font-mono text-[10px] text-text-muted">{gainers.length} records</p>
        </div>
        <div className="flex gap-1.5">
          <button onClick={load}
            className="flex items-center gap-1.5 px-2.5 py-1 border border-border-subtle bg-raised text-text-secondary text-[11px] font-mono hover:text-text-primary hover:bg-hover hover:border-border-strong transition-all duration-150 rounded-none shadow-sm active:translate-y-[1px]">
            <RefreshCw size={12} /> Refresh
          </button>
          <a href={exportUrl} download="gainers.csv"
            className="flex items-center gap-1.5 px-2.5 py-1 border border-green-custom/30 bg-green-custom/10 text-green-custom text-[11px] font-mono hover:bg-green-custom/20 transition-all duration-150 rounded-none shadow-sm active:translate-y-[1px]">
            <Download size={12} /> Export CSV
          </a>
        </div>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-1.5 bg-panel border border-border-subtle p-2 shadow-sm">
        <input type="date" value={date} onChange={e => setDate(e.target.value)}
          className="bg-app border border-border-subtle text-text-primary font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-info-custom rounded-none [color-scheme:dark] w-full" />
        <input type="number" placeholder="Min Gap %" value={minGap} onChange={e => setMinGap(e.target.value)}
          className="bg-app border border-border-subtle text-text-primary font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-info-custom rounded-none [color-scheme:dark] w-full" />
        <input type="number" placeholder="Max Float (M)" value={maxFloat} onChange={e => setMaxFloat(e.target.value)}
          className="bg-app border border-border-subtle text-text-primary font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-info-custom rounded-none [color-scheme:dark] w-full" />
        <input type="number" placeholder="Min RVOL" value={minRvol} onChange={e => setMinRvol(e.target.value)}
          className="bg-app border border-border-subtle text-text-primary font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-info-custom rounded-none [color-scheme:dark] w-full" />
        <div className="flex gap-1.5">
          <select value={sector} onChange={e => setSector(e.target.value)}
            className="flex-1 bg-app border border-border-subtle text-text-primary font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-info-custom rounded-none [color-scheme:dark] w-full">
            <option value="">All sectors</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <button onClick={load}
            className="px-4 py-1.5 bg-raised border border-green-custom/40 text-green-custom text-[11px] font-mono hover:bg-green-custom/10 transition-all duration-150 rounded-none shadow-sm active:translate-y-[1px]">
            Filter
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-panel border border-border-subtle shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-text-muted text-xs font-mono animate-pulse">Loading…</div>
        ) : sorted.length === 0 ? (
          <div className="p-8 text-center text-text-muted text-xs font-mono">No gainers found. Run the ingestion job or adjust filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-raised border-b-2 border-border-strong">
                <tr>
                  <Th col="date"         label="Date" />
                  <Th col="ticker"       label="Ticker" />
                  <Th col="gap_pct"      label="Gap %" />
                  <Th col="float_shares" label="Float" />
                  <Th col="rvol_15m"     label="RVOL" />
                  <Th col="sector"       label="Sector" />
                  <Th col="market_cap"   label="Mkt Cap" />
                  <Th col="close_price"  label="Close" />
                  <th className="px-3 py-2 text-left text-[10px] font-mono text-text-muted uppercase tracking-wider">News</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {sorted.map(g => (
                  <tr key={g.id} className="border-b border-border-subtle hover:bg-hover even:bg-raised/20 transition-all duration-150">
                    <td className="px-3 py-2 font-mono text-xs text-text-muted tabular-nums">{g.date}</td>
                    <td className="px-3 py-2 font-mono text-xs font-bold text-text-primary">{g.ticker}</td>
                    <td className="px-3 py-2 font-mono text-xs text-green-custom font-bold tabular-nums">
                      {g.gap_pct != null ? `+${g.gap_pct}%` : '—'}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-text-secondary tabular-nums">{fmtFloat(g.float_shares)}</td>
                    <td className="px-3 py-2 font-mono text-xs text-text-secondary tabular-nums">{g.rvol_15m != null ? `${g.rvol_15m}x` : '—'}</td>
                    <td className="px-3 py-2 font-mono text-xs text-text-secondary">{g.sector ?? '—'}</td>
                    <td className="px-3 py-2 font-mono text-xs text-text-secondary tabular-nums">{fmtCap(g.market_cap)}</td>
                    <td className="px-3 py-2 font-mono text-xs text-text-primary font-bold tabular-nums">{g.close_price != null ? `$${g.close_price}` : '—'}</td>
                    <td className="px-3 py-2">
                      {g.news_fresh == null ? '—' : g.news_fresh
                        ? <span className="text-[10px] bg-green-custom/10 text-green-custom border border-green-custom/25 px-1.5 py-0.5 font-mono rounded-none font-bold">Fresh</span>
                        : <span className="text-[10px] bg-raised text-text-muted border border-border-subtle px-1.5 py-0.5 font-mono rounded-none">Stale</span>}
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
