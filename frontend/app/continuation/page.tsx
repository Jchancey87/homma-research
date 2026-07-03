'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  getContinuationPicks,
  getContinuationPerformance,
  refreshContinuationPerformance,
  deactivateContinuationPick,
  ContinuationPick,
  ContinuationPerformanceData
} from '@/lib/api'
import {
  Zap, RefreshCw, TrendingUp, BarChart2, Calendar,
  Layers, Search, ExternalLink, ShieldAlert, FileText, XCircle
} from 'lucide-react'

// ── Sparkline component (pure visualization helper) ─────────────────────────
function Sparkline({ pick }: { pick: ContinuationPick }) {
  const c0 = pick.close_d0
  if (!c0) return <div className="text-[10px] text-gray-550 font-mono tracking-tight uppercase">NO DATA</div>

  const points: { day: number; val: number }[] = [{ day: 0, val: c0 }]
  if (pick.d1_close != null) points.push({ day: 1, val: pick.d1_close })
  if (pick.d2_close != null) points.push({ day: 2, val: pick.d2_close })
  if (pick.d3_close != null) points.push({ day: 3, val: pick.d3_close })

  if (points.length < 2) {
    return <div className="text-[10px] text-[#00e5ff] font-mono tracking-tight uppercase">TRACKING...</div>
  }

  const values = points.map(p => p.val)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min === 0 ? 1 : max - min
  
  const width = 80
  const height = 20
  const padding = 2
  
  const coords = points.map((p) => {
    const x = (p.day / 3) * (width - padding * 2) + padding
    const y = height - ((p.val - min) / range) * (height - padding * 2) - padding
    return { x, y }
  })
  
  const pathData = coords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x} ${c.y}`).join(' ')
  const areaData = `${pathData} L ${coords[coords.length - 1].x} ${height} L ${coords[0].x} ${height} Z`
  
  const isUp = (points[points.length - 1].val >= c0)
  const strokeColor = isUp ? '#00ff00' : '#ff003c'
  const fillColor = isUp ? 'rgba(0, 255, 0, 0.04)' : 'rgba(255, 0, 60, 0.04)'
  
  return (
    <div className="flex items-center gap-2">
      <svg width={width} height={height} className="overflow-visible">
        <path d={areaData} fill={fillColor} />
        <path d={pathData} fill="none" stroke={strokeColor} strokeWidth={1.2} />
        {coords.map((c, i) => (
          <circle key={i} cx={c.x} cy={c.y} r={1.5} fill={strokeColor} />
        ))}
      </svg>
      <div className="flex flex-col text-[10px] font-mono leading-none items-end min-w-[44px]">
        <span className={isUp ? 'text-[#00ff00]' : 'text-[#ff003c]'}>
          {isUp ? '+' : ''}{(((points[points.length - 1].val - c0) / c0) * 100).toFixed(1)}%
        </span>
        <span className="text-gray-500 mt-0.5">D{points.length - 1} CLOSE</span>
      </div>
    </div>
  )
}

// ── ScorecardBar component (visual bar stats helper) ────────────────────────
function ScorecardBar({ label, count, winRate, superWinRate, avgMaxExt }: {
  label: string
  count: number
  winRate: number
  superWinRate: number
  avgMaxExt: number
}) {
  const normalWinRate = Math.max(0, winRate - superWinRate)
  const remainder = Math.max(0, 100 - winRate)

  return (
    <div className="bg-[#050505] border border-[#262626] p-3 space-y-2">
      <div className="flex items-center justify-between text-xs font-mono">
        <span className="text-white font-bold">{label}</span>
        <span className="text-gray-500">{count} SAMPLES</span>
      </div>
      
      <div className="w-full h-3.5 bg-[#141414] flex border border-[#262626]">
        {superWinRate > 0 && (
          <div
            style={{ width: `${superWinRate}%` }}
            className="bg-emerald-500 h-full border-r border-[#262626]/40"
            title={`Super Win (≥30%): ${superWinRate}%`}
          />
        )}
        {normalWinRate > 0 && (
          <div
            style={{ width: `${normalWinRate}%` }}
            className="bg-green-600 h-full border-r border-[#262626]/40"
            title={`Normal Win (10%-30%): ${normalWinRate}%`}
          />
        )}
        {remainder > 0 && (
          <div
            style={{ width: `${remainder}%` }}
            className="bg-zinc-850 h-full"
            title={`Flat/Fade (<10%): ${remainder}%`}
          />
        )}
      </div>

      <div className="flex items-center justify-between text-[10px] font-mono text-gray-550">
        <div className="flex gap-3">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-emerald-500" /> SUPER: {superWinRate}%
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-green-600" /> WIN: {winRate}%
          </span>
        </div>
        <span className="text-[#00ff00] font-bold">AVG MAX RUN: +{avgMaxExt}%</span>
      </div>
    </div>
  )
}

// ── PickCard Component ───────────────────────────────────────────────────────
interface PickCardProps {
  pick: ContinuationPick
  isExpanded: boolean
  onToggle: () => void
  onDeactivate: (id: number) => void
  formatLargeNum: (n: number | null | undefined) => string
  formatPercent: (val: number | null | undefined) => string
}

function PickCard({
  pick,
  isExpanded,
  onToggle,
  onDeactivate,
  formatLargeNum,
  formatPercent
}: PickCardProps) {
  const router = useRouter()

  // Calculate outcome
  const highs = [pick.d1_high, pick.d2_high, pick.d3_high].filter((h): h is number => h != null)
  const maxHigh = highs.length > 0 ? Math.max(...highs) : null
  const maxExt = (maxHigh && pick.close_d0 && pick.close_d0 > 0)
    ? ((maxHigh - pick.close_d0) / pick.close_d0) * 100
    : null

  const outcome = maxExt == null ? 'ACTIVE' :
                  maxExt >= 30.0 ? 'RUNNER' :
                  maxExt >= 10.0 ? 'WIN' :
                  maxExt >= 0.0 ? 'FLAT' : 'FADE'

  const borderStyles = {
    ACTIVE: 'border-l-4 border-l-[#00e5ff]',
    RUNNER: 'border-l-4 border-l-[#00ff00]',
    WIN: 'border-l-4 border-l-green-500',
    FLAT: 'border-l-4 border-l-yellow-500',
    FADE: 'border-l-4 border-l-[#ff003c]'
  }[outcome]

  const badgeStyles = {
    ACTIVE: 'bg-[#00e5ff]/10 text-[#00e5ff] border border-[#00e5ff]/20',
    RUNNER: 'bg-[#00ff00]/10 text-[#00ff00] border border-[#00ff00]/20',
    WIN: 'bg-green-500/10 text-green-400 border border-green-500/20',
    FLAT: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
    FADE: 'bg-[#ff003c]/10 text-[#ff003c] border border-[#ff003c]/20'
  }[outcome]

  return (
    <div
      onClick={onToggle}
      className={`bg-[#0a0a0a] border border-[#262626] p-4 cursor-pointer hover:border-gray-600 transition-all ${borderStyles} ${
        isExpanded ? 'ring-1 ring-[#262626] border-gray-600' : ''
      }`}
    >
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center font-mono font-bold text-xs h-5 w-5 bg-zinc-900 text-gray-400 border border-[#262626]">
              #{pick.rank}
            </span>
            <span className="text-base font-bold font-mono text-white tracking-tight">{pick.ticker}</span>
          </div>
          <span className={`px-2 py-0.5 text-[9px] font-mono font-bold uppercase ${badgeStyles}`}>
            {outcome === 'ACTIVE' ? 'ACTIVE' : outcome}
          </span>
        </div>

        {/* Live / Tracking Price Strip */}
        <div className="flex items-center justify-between gap-4 py-2 border-y border-[#262626]/50">
          <div className="flex flex-col">
            <span className="text-[9px] text-gray-500 font-mono uppercase">D0 Close</span>
            <span className="text-white font-mono font-bold text-sm">
              {pick.close_d0 ? `$${pick.close_d0.toFixed(2)}` : '—'}
            </span>
          </div>
          
          {pick.is_active && pick.today_last != null ? (
            <div className="flex flex-col items-end">
              <span className="text-[9px] text-[#00e5ff] font-mono uppercase">LIVE LAST</span>
              <div className="flex items-center gap-1.5 font-mono text-xs">
                <span className="text-white font-bold">${pick.today_last.toFixed(2)}</span>
                <span className={pick.today_change_pct && pick.today_change_pct >= 0 ? 'text-[#00ff00]' : 'text-[#ff003c]'}>
                  {formatPercent(pick.today_change_pct)}
                </span>
              </div>
            </div>
          ) : (
            <Sparkline pick={pick} />
          )}
        </div>

        {/* Metric Grid */}
        <div className="grid grid-cols-2 gap-2 text-xs font-mono">
          <div>
            <span className="text-[9px] text-gray-550 uppercase block">FLOAT:</span>
            <span className="text-blue-400 font-bold">{formatLargeNum(pick.float_shares)}</span>
          </div>
          <div>
            <span className="text-[9px] text-gray-550 uppercase block">DAY 0 GAP:</span>
            <span className="text-white font-bold">{formatPercent(pick.gap_pct)}</span>
          </div>
        </div>

        {/* Snippet / News */}
        {pick.reason && (
          <p className="text-[11px] font-mono text-gray-400 line-clamp-2 leading-relaxed border-t border-[#262626]/30 pt-2">
            {pick.reason}
          </p>
        )}

        {/* Expanded Panel */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-[#262626] space-y-4 text-xs font-mono" onClick={e => e.stopPropagation()}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Fundamentals */}
              <div className="space-y-2">
                <div className="text-[9px] text-gray-550 uppercase font-bold tracking-wider">{"// COMPANY FUNDAMENTALS"}</div>
                <div className="grid grid-cols-2 gap-2 bg-[#050505] p-3 border border-[#262626]">
                  <div>
                    <span className="text-[9px] text-gray-500 block">MARKET CAP</span>
                    <span className="text-white font-bold">{formatLargeNum(pick.market_cap)}</span>
                  </div>
                  <div>
                    <span className="text-[9px] text-gray-500 block">CASH</span>
                    <span className="text-white font-bold">{formatLargeNum(pick.cash)}</span>
                  </div>
                  <div>
                    <span className="text-[9px] text-gray-500 block">RUNWAY</span>
                    <span className={`font-bold ${pick.runway_months != null && pick.runway_months < 6 ? 'text-[#ff003c]' : pick.runway_months != null && pick.runway_months < 12 ? 'text-yellow-500' : 'text-[#00ff00]'}`}>
                      {pick.runway_months != null ? `${pick.runway_months} mo` : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-[9px] text-gray-500 block">DILUTION RISK</span>
                    <span className={`font-bold ${pick.dilution_risk === 'High' ? 'text-[#ff003c]' : pick.dilution_risk === 'Medium' ? 'text-yellow-500' : 'text-[#00ff00]'}`}>
                      {pick.dilution_risk || 'Low'}
                    </span>
                  </div>
                </div>
                
                {pick.news_headline && (
                  <div className="bg-[#050505] p-3 border border-[#262626]">
                    <span className="text-[9px] text-gray-500 block mb-1">
                      CATALYST NEWS {pick.news_fresh && <span className="text-[#00ff00] font-bold ml-1">(FRESH)</span>}
                    </span>
                    <p className="text-white text-[11px] leading-snug">{pick.news_headline}</p>
                  </div>
                )}
              </div>

              {/* 3-Day Table */}
              <div className="space-y-2">
                <div className="text-[9px] text-gray-550 uppercase font-bold tracking-wider">{"// 3-DAY PERFORMANCE DETAILS"}</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[11px] text-left border-collapse border border-[#262626]">
                    <thead>
                      <tr className="bg-[#050505] border-b border-[#262626] text-gray-500 text-[9px] uppercase font-bold">
                        <th className="p-1.5">DAY</th>
                        <th className="p-1.5 text-right">HIGH (RUN)</th>
                        <th className="p-1.5 text-right">CLOSE (CHG)</th>
                        <th className="p-1.5 text-right">VOLUME</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { label: 'D1', high: pick.d1_high, close: pick.d1_close, volume: pick.d1_volume },
                        { label: 'D2', high: pick.d2_high, close: pick.d2_close, volume: pick.d2_volume },
                        { label: 'D3', high: pick.d3_high, close: pick.d3_close, volume: pick.d3_volume }
                      ].map(day => (
                        <tr key={day.label} className="border-b border-[#262626] last:border-0 hover:bg-[#080808]">
                          <td className="p-1.5 font-bold text-gray-400">{day.label}</td>
                          <td className="p-1.5 text-right">
                            {day.high ? (
                              <div className="flex flex-col items-end leading-none">
                                <span>${day.high.toFixed(2)}</span>
                                <span className="text-[9px] text-[#00ff00] font-bold mt-0.5">
                                  +{pick.close_d0 ? (((day.high - pick.close_d0) / pick.close_d0) * 100).toFixed(1) : 0}%
                                </span>
                              </div>
                            ) : '—'}
                          </td>
                          <td className="p-1.5 text-right">
                            {day.close ? (
                              <div className="flex flex-col items-end leading-none">
                                <span>${day.close.toFixed(2)}</span>
                                <span className={`text-[9px] font-bold mt-0.5 ${day.close >= (pick.close_d0 || 0) ? 'text-[#00ff00]' : 'text-[#ff003c]'}`}>
                                  {formatPercent(pick.close_d0 ? ((day.close - pick.close_d0) / pick.close_d0) * 100 : null)}
                                </span>
                              </div>
                            ) : '—'}
                          </td>
                          <td className="p-1.5 text-right text-gray-500 font-mono">
                            {day.volume ? formatLargeNum(day.volume) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2 pt-2">
              <button
                onClick={() => router.push(`/research?ticker=${pick.ticker}`)}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-emerald-500/30 bg-emerald-950/10 text-emerald-400 hover:bg-emerald-950/20 transition-all font-semibold font-mono uppercase text-[10px]"
              >
                <ExternalLink size={11} />
                Research Ticker
              </button>
              {pick.is_active && (
                <button
                  onClick={() => onDeactivate(pick.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 border border-[#ff003c]/30 bg-red-950/10 text-[#ff003c] hover:bg-red-950/20 transition-all font-semibold font-mono uppercase text-[10px]"
                >
                  <XCircle size={11} />
                  Deactivate Pick
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function ContinuationPage() {
  const [activeTab, setActiveTab] = useState<'journal' | 'performance'>('journal')
  const [picks, setPicks] = useState<ContinuationPick[]>([])
  const [performance, setPerformance] = useState<ContinuationPerformanceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [search, setSearch] = useState('')
  const [showHistory, setShowHistory] = useState(true)
  const [expandedPickId, setExpandedPickId] = useState<number | null>(null)

  // Filters & Sorting state
  const [outcomeFilter, setOutcomeFilter] = useState<'ALL' | 'RUNNER' | 'WIN' | 'FLAT' | 'FADE' | 'ACTIVE'>('ALL')
  const [floatFilter, setFloatFilter] = useState<'ALL' | 'MICRO' | 'SMALL' | 'MEDIUM' | 'LARGE'>('ALL')
  const [sortBy, setSortBy] = useState<'date' | 'maxExt' | 'gap' | 'float' | 'rank'>('date')
  const [groupByDate, setGroupByDate] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [p, perf] = await Promise.all([
        getContinuationPicks(showHistory),
        getContinuationPerformance()
      ])
      setPicks(p)
      setPerformance(perf)
    } catch (e) {
      console.error("Failed to load continuation data:", e)
    } finally {
      setLoading(false)
    }
  }, [showHistory])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await refreshContinuationPerformance()
      await loadData()
    } catch (e) {
      console.error("Failed to refresh performance:", e)
    } finally {
      setRefreshing(false)
    }
  }

  const handleDeactivate = async (id: number) => {
    if (!confirm("Deactivate this pick?")) return
    try {
      await deactivateContinuationPick(id, 'manually dismissed')
      await loadData()
    } catch (e) {
      console.error("Failed to deactivate pick:", e)
    }
  }

  const toggleExpand = (id: number) => {
    setExpandedPickId(prev => (prev === id ? null : id))
  }

  const formatLargeNum = (n: number | null | undefined) => {
    if (n == null) return '—'
    const m = n / 1_000_000
    return m >= 1000 ? `${(m / 1000).toFixed(1)}B` : `${m.toFixed(1)}M`
  }

  const formatPercent = (val: number | null | undefined) => {
    if (val == null) return '—'
    return `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`
  }

  const getPickOutcome = (p: ContinuationPick) => {
    const highs = [p.d1_high, p.d2_high, p.d3_high].filter((h): h is number => h != null)
    const maxHigh = highs.length > 0 ? Math.max(...highs) : null
    const maxExt = (maxHigh && p.close_d0 && p.close_d0 > 0)
      ? ((maxHigh - p.close_d0) / p.close_d0) * 100
      : null

    if (maxExt == null) return 'ACTIVE'
    if (maxExt >= 30.0) return 'RUNNER'
    if (maxExt >= 10.0) return 'WIN'
    if (maxExt >= 0.0) return 'FLAT'
    return 'FADE'
  }

  const getPickFloatCat = (p: ContinuationPick) => {
    const f = p.float_shares
    if (f == null) return 'UNKNOWN'
    if (f < 5_000_000) return 'MICRO'
    if (f < 10_000_000) return 'SMALL'
    if (f < 50_000_000) return 'MEDIUM'
    return 'LARGE'
  }

  // Filter and sort picks
  const processedPicks = picks.filter(p => {
    // 1. Search text
    if (search) {
      const s = search.toUpperCase()
      const matchesText = 
        p.ticker.includes(s) ||
        (p.sector && p.sector.toUpperCase().includes(s)) ||
        (p.reason && p.reason.toUpperCase().includes(s)) ||
        (p.news_headline && p.news_headline.toUpperCase().includes(s))
      if (!matchesText) return false
    }

    // 2. Outcome filter
    const outcome = getPickOutcome(p)
    if (outcomeFilter !== 'ALL' && outcome !== outcomeFilter) return false

    // 3. Float filter
    const floatCat = getPickFloatCat(p)
    if (floatFilter !== 'ALL' && floatCat !== floatFilter) return false

    return true
  })

  const sortedPicks = [...processedPicks].sort((a, b) => {
    if (sortBy === 'date') {
      return new Date(b.date).getTime() - new Date(a.date).getTime()
    }
    if (sortBy === 'maxExt') {
      const getExt = (p: ContinuationPick) => {
        const highs = [p.d1_high, p.d2_high, p.d3_high].filter((h): h is number => h != null)
        if (highs.length === 0) return -99999
        const maxHigh = Math.max(...highs)
        return p.close_d0 ? ((maxHigh - p.close_d0) / p.close_d0) * 100 : -99999
      }
      return getExt(b) - getExt(a)
    }
    if (sortBy === 'gap') {
      return (b.gap_pct || 0) - (a.gap_pct || 0)
    }
    if (sortBy === 'float') {
      return (a.float_shares || 0) - (b.float_shares || 0)
    }
    if (sortBy === 'rank') {
      return a.rank - b.rank
    }
    return 0
  })

  // Date grouping
  const groupedPicks: { [key: string]: ContinuationPick[] } = {}
  sortedPicks.forEach(p => {
    const d = p.date
    if (!groupedPicks[d]) {
      groupedPicks[d] = []
    }
    groupedPicks[d].push(p)
  })
  const sortedDates = Object.keys(groupedPicks).sort((a, b) => new Date(b).getTime() - new Date(a).getTime())

  return (
    <main className="max-w-screen-2xl mx-auto px-4 py-6 text-gray-100 min-h-screen font-mono">
      {/* ── Header ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#262626] pb-5 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <Zap className="text-[#00ff00] h-6 w-6 animate-pulse" />
            <h1 className="text-2xl font-bold tracking-tight text-white uppercase font-mono">Continuation Play Journal</h1>
          </div>
          <p className="text-xs text-gray-400 mt-1 font-mono uppercase">
            Track multi-day runners, fundamental triggers, and study historical play statistics.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Tab Toggles */}
          <div className="bg-black p-0.5 flex items-center border border-[#262626]">
            <button
              onClick={() => setActiveTab('journal')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase transition-all ${
                activeTab === 'journal'
                  ? 'bg-[#141414] text-white border border-[#262626]'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Calendar size={12} />
              Journal
            </button>
            <button
              onClick={() => setActiveTab('performance')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase transition-all ${
                activeTab === 'performance'
                  ? 'bg-[#141414] text-white border border-[#262626]'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <BarChart2 size={12} />
              Performance Stats
            </button>
          </div>

          {/* Sync Button */}
          <button
            onClick={handleRefresh}
            disabled={refreshing || loading}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[#262626] text-xs font-bold uppercase bg-black hover:bg-[#141414] transition-colors disabled:opacity-50 text-gray-300"
          >
            <RefreshCw size={12} className={refreshing ? 'animate-spin text-[#00ff00]' : ''} />
            {refreshing ? 'Syncing...' : 'Sync Play Performance'}
          </button>
        </div>
      </div>

      {/* ── Summary Stats Strip (Always visible for continuous system feedback) ─ */}
      {!loading && performance && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-1.5 mb-6 border-b border-[#262626] pb-6">
          <div className="bg-[#0a0a0a] border border-[#262626] p-3 rounded-none">
            <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500 block mb-0.5">Total Studies</span>
            <span className="text-lg font-bold text-white">{performance.summary.total_picks || 0}</span>
          </div>
          <div className="bg-[#0a0a0a] border border-[#262626] p-3 rounded-none">
            <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500 block mb-0.5">Win Rate (≥10%)</span>
            <span className="text-lg font-bold text-[#00ff00]">{performance.summary.win_rate || 0}%</span>
          </div>
          <div className="bg-[#0a0a0a] border border-[#262626] p-3 rounded-none">
            <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500 block mb-0.5">Super Rate (≥30%)</span>
            <span className="text-lg font-bold text-emerald-400">{performance.summary.super_win_rate || 0}%</span>
          </div>
          <div className="bg-[#0a0a0a] border border-[#262626] p-3 rounded-none">
            <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500 block mb-0.5">Avg Max Extension</span>
            <span className="text-lg font-bold text-[#00ff00]">+{performance.summary.avg_max_ext || 0}%</span>
          </div>
          <div className="bg-[#0a0a0a] border border-[#262626] p-3 rounded-none">
            <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500 block mb-0.5">Avg D1 Close</span>
            <span className={`text-lg font-bold ${performance.summary.avg_d1_ret >= 0 ? 'text-[#00ff00]' : 'text-[#ff003c]'}`}>
              {performance.summary.avg_d1_ret >= 0 ? '+' : ''}{performance.summary.avg_d1_ret || 0}%
            </span>
          </div>
          <div className="bg-[#0a0a0a] border border-[#262626] p-3 rounded-none">
            <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500 block mb-0.5">Avg D3 Close</span>
            <span className={`text-lg font-bold ${performance.summary.avg_d3_ret >= 0 ? 'text-[#00ff00]' : 'text-[#ff003c]'}`}>
              {performance.summary.avg_d3_ret >= 0 ? '+' : ''}{performance.summary.avg_d3_ret || 0}%
            </span>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-[#050505] border border-[#262626] gap-2">
          <RefreshCw className="animate-spin text-emerald-500 h-6 w-6" />
          <span className="text-xs text-gray-500 uppercase">Loading continuation journal details...</span>
        </div>
      ) : (
        <>
          {/* ── JOURNAL TAB ─────────────────────────────────────────────────── */}
          {activeTab === 'journal' && (
            <div className="space-y-6">
              {/* Filter Panel */}
              <div className="bg-[#0a0a0a] border border-[#262626] p-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="relative flex-grow max-w-md">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500" />
                    <input
                      type="text"
                      placeholder="SEARCH TICKERS, SECTORS, OR CATALYSTS..."
                      value={search}
                      onChange={e => setSearch(e.target.value)}
                      className="bg-black border border-[#262626] text-white font-mono text-[11px] pl-8 pr-2 py-2 focus:outline-none focus:border-[#00ff00] rounded-none w-full uppercase placeholder:text-gray-600"
                    />
                  </div>
                  
                  <div className="flex flex-wrap items-center gap-4">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-500 uppercase">SORT:</span>
                      <select
                        value={sortBy}
                        onChange={e => setSortBy(e.target.value as 'date' | 'maxExt' | 'gap' | 'float' | 'rank')}
                        className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1.5 focus:outline-none focus:border-[#00ff00] rounded-none cursor-pointer uppercase"
                      >
                        <option value="date">DATE (NEWEST)</option>
                        <option value="maxExt">MAX RUN %</option>
                        <option value="gap">GAP %</option>
                        <option value="float">FLOAT SIZE</option>
                        <option value="rank">RANK</option>
                      </select>
                    </div>

                    <label className="flex items-center gap-1.5 text-[11px] text-gray-500 uppercase cursor-pointer hover:text-white select-none">
                      <input
                        type="checkbox"
                        checked={groupByDate}
                        onChange={e => setGroupByDate(e.target.checked)}
                        className="rounded-none border-[#262626] bg-black text-[#00ff00] focus:ring-0 focus:ring-offset-0 h-3.5 w-3.5"
                      />
                      Group by Date
                    </label>

                    <label className="flex items-center gap-1.5 text-[11px] text-gray-500 uppercase cursor-pointer hover:text-white select-none">
                      <input
                        type="checkbox"
                        checked={showHistory}
                        onChange={e => setShowHistory(e.target.checked)}
                        className="rounded-none border-[#262626] bg-black text-[#00ff00] focus:ring-0 focus:ring-offset-0 h-3.5 w-3.5"
                      />
                      Expired (older than 3d)
                    </label>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-[#262626]/40">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[9px] text-gray-500 uppercase mr-1">OUTCOME:</span>
                    {(['ALL', 'RUNNER', 'WIN', 'FLAT', 'FADE', 'ACTIVE'] as const).map(opt => {
                      const active = outcomeFilter === opt
                      return (
                        <button
                          key={opt}
                          onClick={() => setOutcomeFilter(opt)}
                          className={`px-2 py-0.5 text-[10px] uppercase transition-all font-bold ${
                            active
                              ? 'bg-emerald-500 text-black border border-emerald-400'
                              : 'bg-black text-gray-400 border border-[#262626] hover:text-white hover:border-gray-500'
                          }`}
                        >
                          {opt === 'ALL' ? 'ALL OUTCOMES' : opt === 'ACTIVE' ? 'ACTIVE / PENDING' : opt}
                        </button>
                      )
                    })}
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-[9px] text-gray-500 uppercase mr-1">FLOAT:</span>
                    {(['ALL', 'MICRO', 'SMALL', 'MEDIUM', 'LARGE'] as const).map(opt => {
                      const active = floatFilter === opt
                      return (
                        <button
                          key={opt}
                          onClick={() => setFloatFilter(opt)}
                          className={`px-2 py-0.5 text-[10px] uppercase transition-all font-bold ${
                            active
                              ? 'bg-emerald-500 text-black border border-emerald-400'
                              : 'bg-black text-gray-400 border border-[#262626] hover:text-white hover:border-gray-500'
                          }`}
                        >
                          {opt === 'ALL' ? 'ALL FLOATS' : opt}
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>

              {/* Cards Grid */}
              {groupByDate ? (
                <div className="space-y-8">
                  {sortedDates.length === 0 ? (
                    <div className="text-center py-12 bg-[#050505] border border-[#262626] text-xs text-gray-500 uppercase">
                      No continuation picks matching query.
                    </div>
                  ) : (
                    sortedDates.map(dateStr => {
                      const datePicks = groupedPicks[dateStr]
                      const formattedDate = new Date(dateStr).toLocaleDateString('en-US', {
                        weekday: 'long',
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                      })
                      return (
                        <div key={dateStr} className="space-y-3">
                          <div className="flex items-center gap-4">
                            <span className="text-xs font-bold text-gray-400 whitespace-nowrap">
                              {"// "}{formattedDate.toUpperCase()}
                            </span>
                            <div className="w-full h-px bg-[#262626]" />
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                            {datePicks.map(p => (
                              <PickCard
                                key={p.id}
                                pick={p}
                                isExpanded={expandedPickId === p.id}
                                onToggle={() => toggleExpand(p.id)}
                                onDeactivate={handleDeactivate}
                                formatLargeNum={formatLargeNum}
                                formatPercent={formatPercent}
                              />
                            ))}
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {sortedPicks.length === 0 ? (
                    <div className="col-span-full text-center py-12 bg-[#050505] border border-[#262626] text-xs text-gray-500 uppercase">
                      No continuation picks matching query.
                    </div>
                  ) : (
                    sortedPicks.map(p => (
                      <PickCard
                        key={p.id}
                        pick={p}
                        isExpanded={expandedPickId === p.id}
                        onToggle={() => toggleExpand(p.id)}
                        onDeactivate={handleDeactivate}
                        formatLargeNum={formatLargeNum}
                        formatPercent={formatPercent}
                      />
                    ))
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── PERFORMANCE STATS TAB ───────────────────────────────────────── */}
          {activeTab === 'performance' && performance && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Float Category Breakdown */}
              <div className="bg-[#0a0a0a] border border-[#262626] p-4 space-y-4">
                <div className="flex items-center justify-between border-b border-[#262626]/60 pb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-gray-400">{"// BREAKDOWN BY TICKER FLOAT"}</span>
                  <Layers size={14} className="text-gray-400" />
                </div>
                <div className="grid grid-cols-1 gap-3">
                  {performance.groups.float_category.map(row => (
                    <ScorecardBar
                      key={row.group_value}
                      label={row.group_value}
                      count={row.count}
                      winRate={row.win_rate}
                      superWinRate={row.super_win_rate}
                      avgMaxExt={row.avg_max_ext}
                    />
                  ))}
                </div>
              </div>

              {/* Gap Category Breakdown */}
              <div className="bg-[#0a0a0a] border border-[#262626] p-4 space-y-4">
                <div className="flex items-center justify-between border-b border-[#262626]/60 pb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-gray-400">{"// BREAKDOWN BY DAY 0 GAP %"}</span>
                  <TrendingUp size={14} className="text-gray-400" />
                </div>
                <div className="grid grid-cols-1 gap-3">
                  {performance.groups.gap_category.map(row => (
                    <ScorecardBar
                      key={row.group_value}
                      label={row.group_value}
                      count={row.count}
                      winRate={row.win_rate}
                      superWinRate={row.super_win_rate}
                      avgMaxExt={row.avg_max_ext}
                    />
                  ))}
                </div>
              </div>

              {/* News freshness Breakdown */}
              <div className="bg-[#0a0a0a] border border-[#262626] p-4 space-y-4">
                <div className="flex items-center justify-between border-b border-[#262626]/60 pb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-gray-400">{"// CATALYST FRESHNESS VS STALE"}</span>
                  <FileText size={14} className="text-gray-400" />
                </div>
                <div className="grid grid-cols-1 gap-3">
                  {performance.groups.news_freshness.map(row => (
                    <ScorecardBar
                      key={row.group_value}
                      label={row.group_value === 'true' ? 'FRESH CATALYST' : 'STALE/NO CATALYST'}
                      count={row.count}
                      winRate={row.win_rate}
                      superWinRate={row.super_win_rate}
                      avgMaxExt={row.avg_max_ext}
                    />
                  ))}
                </div>
              </div>

              {/* Dilution Risk Breakdown */}
              <div className="bg-[#0a0a0a] border border-[#262626] p-4 space-y-4">
                <div className="flex items-center justify-between border-b border-[#262626]/60 pb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-gray-400">{"// BREAKDOWN BY DILUTION RISK"}</span>
                  <ShieldAlert size={14} className="text-gray-400" />
                </div>
                <div className="grid grid-cols-1 gap-3">
                  {performance.groups.dilution_risk.map(row => (
                    <ScorecardBar
                      key={row.group_value}
                      label={`${row.group_value.toUpperCase()} RISK`}
                      count={row.count}
                      winRate={row.win_rate}
                      superWinRate={row.super_win_rate}
                      avgMaxExt={row.avg_max_ext}
                    />
                  ))}
                </div>
              </div>

              {/* Industry Sector Breakdown */}
              <div className="bg-[#0a0a0a] border border-[#262626] p-4 space-y-4 md:col-span-2">
                <div className="flex items-center justify-between border-b border-[#262626]/60 pb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-gray-400 font-mono">{"// BREAKDOWN BY INDUSTRY SECTOR"}</span>
                  <BarChart2 size={14} className="text-gray-400" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                  {performance.groups.sector.map(row => (
                    <ScorecardBar
                      key={row.group_value}
                      label={row.group_value.toUpperCase()}
                      count={row.count}
                      winRate={row.win_rate}
                      superWinRate={row.super_win_rate}
                      avgMaxExt={row.avg_max_ext}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </main>
  )
}
