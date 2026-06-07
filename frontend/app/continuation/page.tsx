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
  Zap, RefreshCw, TrendingUp, BarChart2, AlertCircle, Calendar,
  Layers, Search, ChevronDown, ChevronUp, ExternalLink,
  Info, ShieldAlert, Award, FileText, XCircle, CheckCircle
} from 'lucide-react'

export default function ContinuationPage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<'journal' | 'performance'>('journal')
  const [picks, setPicks] = useState<ContinuationPick[]>([])
  const [performance, setPerformance] = useState<ContinuationPerformanceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [search, setSearch] = useState('')
  const [showHistory, setShowHistory] = useState(true)
  const [expandedPickId, setExpandedPickId] = useState<number | null>(null)

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

  const filteredPicks = picks.filter(p => {
    if (!search) return true
    const s = search.toUpperCase()
    return (
      p.ticker.includes(s) ||
      (p.sector && p.sector.toUpperCase().includes(s)) ||
      (p.reason && p.reason.toUpperCase().includes(s))
    )
  })

  const formatLargeNum = (n: number | null | undefined) => {
    if (n == null) return '—'
    const m = n / 1_000_000
    return m >= 1000 ? `${(m / 1000).toFixed(1)}B` : `${m.toFixed(1)}M`
  }

  const formatPercent = (val: number | null | undefined) => {
    if (val == null) return '—'
    return `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`
  }

  const getPerformanceBadge = (maxExt: number | null | undefined) => {
    if (maxExt == null) return <span className="text-gray-400">—</span>
    if (maxExt >= 30.0) return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">🏆 D3 Runner ({maxExt.toFixed(1)}%)</span>
    if (maxExt >= 10.0) return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-green-500/10 text-green-400 border border-green-500/20">🟢 Win ({maxExt.toFixed(1)}%)</span>
    if (maxExt >= 0.0) return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">🟡 Flat ({maxExt.toFixed(1)}%)</span>
    return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/10 text-red-400 border border-red-500/20">🔴 Fade ({maxExt.toFixed(1)}%)</span>
  }

  return (
    <main className="max-w-screen-2xl mx-auto px-4 py-6 text-gray-900 dark:text-gray-100 min-h-screen">
      {/* ── Header ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 dark:border-gray-800 pb-5 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <Zap className="text-emerald-500 dark:text-emerald-400 h-6 w-6" />
            <h1 className="text-3xl font-bold tracking-tight">Continuation Play Journal</h1>
          </div>
          <p className="text-base text-gray-500 dark:text-gray-400 mt-1">
            Track multi-day runners, fundamental triggers, and study historical play statistics.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Tab Toggles */}
          <div className="bg-gray-100 dark:bg-gray-800 p-0.5 rounded-lg flex items-center border border-gray-200 dark:border-gray-700">
            <button
              onClick={() => setActiveTab('journal')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-semibold transition-all ${
                activeTab === 'journal'
                  ? 'bg-white dark:bg-gray-900 shadow-sm text-gray-900 dark:text-white'
                  : 'text-gray-500 hover:text-gray-950 dark:hover:text-white'
              }`}
            >
              <Calendar size={13} />
              Journal
            </button>
            <button
              onClick={() => setActiveTab('performance')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-semibold transition-all ${
                activeTab === 'performance'
                  ? 'bg-white dark:bg-gray-900 shadow-sm text-gray-900 dark:text-white'
                  : 'text-gray-500 hover:text-gray-950 dark:hover:text-white'
              }`}
            >
              <BarChart2 size={13} />
              Performance Stats
            </button>
          </div>

          {/* Sync Button */}
          <button
            onClick={handleRefresh}
            disabled={refreshing || loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 text-sm font-medium bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/80 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin text-emerald-500' : ''} />
            {refreshing ? 'Syncing...' : 'Sync Play Performance'}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <RefreshCw className="animate-spin text-emerald-500 h-8 w-8" />
          <span className="text-base text-gray-500">Loading continuation journal details...</span>
        </div>
      ) : (
        <>
          {/* ── Tab Content: JOURNAL ─────────────────────────────────────────── */}
          {activeTab === 'journal' && (
            <div className="space-y-4">
              {/* Filters Panel */}
              <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
                <div className="relative w-full sm:max-w-xs">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search ticker, sector, catalyst..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 rounded-lg border border-gray-200 dark:border-gray-850 bg-white dark:bg-gray-900 text-sm focus:ring-1 focus:ring-emerald-500 focus:outline-none"
                  />
                </div>

                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showHistory}
                      onChange={e => setShowHistory(e.target.checked)}
                      className="rounded border-gray-300 dark:border-gray-800 text-emerald-500 focus:ring-emerald-500 h-4 w-4 bg-white dark:bg-gray-900"
                    />
                    Include expired picks (older than 3 days)
                  </label>
                </div>
              </div>

              {/* Journal Table */}
              <div className="bg-white dark:bg-gray-950/40 border border-gray-200 dark:border-gray-850/60 rounded-xl overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-left">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-850 bg-gray-50/50 dark:bg-gray-900/30 text-gray-500 text-[10px] uppercase font-bold tracking-wider">
                        <th className="px-4 py-3 text-center w-12">Rank</th>
                        <th className="px-4 py-3 w-28">Ticker</th>
                        <th className="px-4 py-3 w-24 text-center">Day 0</th>
                        <th className="px-4 py-3">LLM Continuation Rationale</th>
                        <th className="px-4 py-3 text-center w-24">Float</th>
                        <th className="px-4 py-3 text-center w-24">Sector</th>
                        <th className="px-4 py-3 text-center w-36">Max 3-Day Run</th>
                        <th className="px-4 py-3 text-right w-16"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredPicks.length === 0 ? (
                        <tr>
                          <td colSpan={8} className="text-center py-10 text-sm text-gray-500">
                            No continuation picks matching query.
                          </td>
                        </tr>
                      ) : (
                        filteredPicks.map(p => {
                          const isExpanded = expandedPickId === p.id
                          
                          // Calculate max extension over the 3 days
                          const highs = [p.d1_high, p.d2_high, p.d3_high].filter((h): h is number => h != null)
                          const maxHigh = highs.length > 0 ? Math.max(...highs) : null
                          const maxExt = (maxHigh && p.close_d0 && p.close_d0 > 0)
                            ? ((maxHigh - p.close_d0) / p.close_d0) * 100
                            : null

                          return (
                            <>
                              {/* Parent Row */}
                              <tr
                                key={p.id}
                                onClick={() => toggleExpand(p.id)}
                                className={`cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900/40 transition-colors border-b border-gray-200 dark:border-gray-850/60 last:border-0 ${
                                  isExpanded ? 'bg-gray-50/50 dark:bg-gray-900/20' : ''
                                }`}
                              >
                                <td className="px-4 py-4.5 text-center font-bold">
                                  <span className={`inline-flex items-center justify-center h-6 w-6 rounded-full text-sm ${
                                    p.rank === 1 ? 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20' :
                                    p.rank === 2 ? 'bg-slate-300/10 text-slate-400 border border-slate-300/20' :
                                    'bg-amber-600/10 text-amber-500 border border-amber-600/20'
                                  }`}>
                                    {p.rank}
                                  </span>
                                </td>
                                <td className="px-4 py-4.5 font-mono">
                                  <div className="font-bold text-base text-gray-900 dark:text-white">{p.ticker}</div>
                                  <div className="text-[10px] text-gray-500 mt-0.5">
                                    {new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                                  </div>
                                </td>
                                <td className="px-4 py-4.5 text-center font-mono text-sm">
                                  {p.close_d0 ? `$${p.close_d0.toFixed(2)}` : '—'}
                                </td>
                                <td className="px-4 py-4.5 text-sm text-gray-600 dark:text-gray-400 leading-relaxed max-w-md">
                                  <div className="line-clamp-2">{p.reason || 'No description recorded'}</div>
                                </td>
                                <td className="px-4 py-4.5 text-center text-sm font-mono text-blue-500 dark:text-blue-400">
                                  {formatLargeNum(p.float_shares)}
                                </td>
                                <td className="px-4 py-4.5 text-center text-sm text-gray-600 dark:text-gray-400 truncate max-w-[120px]">
                                  {p.sector || '—'}
                                </td>
                                <td className="px-4 py-4.5 text-center font-mono text-sm">
                                  {getPerformanceBadge(maxExt)}
                                </td>
                                <td className="px-4 py-4.5 text-right">
                                  {isExpanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
                                </td>
                              </tr>

                              {/* Expanded Panel */}
                              {isExpanded && (
                                <tr className="bg-gray-50/30 dark:bg-gray-900/10 border-b border-gray-200 dark:border-gray-850/60">
                                  <td colSpan={8} className="px-6 py-5">
                                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                                      {/* Left Column: Fundamentals */}
                                      <div className="lg:col-span-5 space-y-4">
                                        <div className="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wider text-gray-400">
                                          <Info size={13} />
                                          Company Fundamentals
                                        </div>

                                        <div className="grid grid-cols-2 gap-3 bg-white dark:bg-gray-900/50 p-4 rounded-xl border border-gray-200 dark:border-gray-850 shadow-sm">
                                          <div>
                                            <span className="text-[10px] text-gray-400 block font-semibold">MARKET CAP</span>
                                            <span className="text-sm font-mono font-bold">{formatLargeNum(p.market_cap)}</span>
                                          </div>
                                          <div>
                                            <span className="text-[10px] text-gray-400 block font-semibold">CASH POSITION</span>
                                            <span className="text-sm font-mono font-bold">{formatLargeNum(p.cash)}</span>
                                          </div>
                                          <div>
                                            <span className="text-[10px] text-gray-400 block font-semibold">RUNWAY (MONTHS)</span>
                                            <span className={`text-sm font-mono font-bold ${
                                              p.runway_months != null && p.runway_months < 6 ? 'text-red-500' :
                                              p.runway_months != null && p.runway_months < 12 ? 'text-yellow-500' :
                                              'text-emerald-500'
                                            }`}>
                                              {p.runway_months != null ? `${p.runway_months} mo` : '—'}
                                            </span>
                                          </div>
                                          <div>
                                            <span className="text-[10px] text-gray-400 block font-semibold">DILUTION RISK</span>
                                            <span className={`inline-flex items-center gap-1 text-[10px] font-bold ${
                                              p.dilution_risk === 'High' ? 'text-red-500' :
                                              p.dilution_risk === 'Medium' ? 'text-yellow-500' :
                                              'text-emerald-500'
                                            }`}>
                                              <ShieldAlert size={10} />
                                              {p.dilution_risk || 'Low'}
                                            </span>
                                          </div>
                                        </div>

                                        {p.news_headline && (
                                          <div className="bg-white dark:bg-gray-900/50 p-4 rounded-xl border border-gray-200 dark:border-gray-850 shadow-sm">
                                            <span className="text-[10px] text-gray-400 block font-semibold uppercase mb-1">
                                              Catalyst News {p.news_fresh && <span className="text-emerald-500 font-bold ml-1">(Fresh)</span>}
                                            </span>
                                            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 leading-relaxed">
                                              {p.news_headline}
                                            </p>
                                          </div>
                                        )}

                                        <div className="flex items-center gap-2">
                                          <button
                                            onClick={() => router.push(`/research?ticker=${p.ticker}`)}
                                            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20 text-sm font-semibold transition-all"
                                          >
                                            <ExternalLink size={12} />
                                            Deep Research Ticker
                                          </button>
                                          {p.is_active && (
                                            <button
                                              onClick={(e) => { e.stopPropagation(); handleDeactivate(p.id) }}
                                              className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-red-500/20 text-red-500 hover:bg-red-500/10 text-sm font-semibold transition-all"
                                            >
                                              <XCircle size={12} />
                                              Deactivate Pick
                                            </button>
                                          )}
                                        </div>
                                      </div>

                                      {/* Right Column: Performance Breakdown */}
                                      <div className="lg:col-span-7 space-y-4">
                                        <div className="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wider text-gray-400">
                                          <Award size={13} />
                                          Subsequent 3-Day Performance Tracking
                                        </div>

                                        <div className="bg-white dark:bg-gray-900/50 rounded-xl border border-gray-200 dark:border-gray-850 overflow-hidden shadow-sm">
                                          <table className="w-full text-left text-sm border-collapse">
                                            <thead>
                                              <tr className="border-b border-gray-200 dark:border-gray-850 bg-gray-50/50 dark:bg-gray-900/30 text-gray-500 text-[10px] font-bold uppercase tracking-wider">
                                                <th className="px-4 py-2">Day</th>
                                                <th className="px-4 py-2 text-right">Open</th>
                                                <th className="px-4 py-2 text-right">High / Run</th>
                                                <th className="px-4 py-2 text-right">Low</th>
                                                <th className="px-4 py-2 text-right">Close / Chg</th>
                                                <th className="px-4 py-2 text-right">Volume</th>
                                              </tr>
                                            </thead>
                                            <tbody className="font-mono">
                                              {/* Day 1 */}
                                              <tr className="border-b border-gray-150 dark:border-gray-850/50 last:border-0 hover:bg-gray-100/10">
                                                <td className="px-4 py-2.5 font-sans font-semibold text-gray-700 dark:text-gray-300">Day 1</td>
                                                <td className="px-4 py-2.5 text-right">{p.d1_open ? `$${p.d1_open.toFixed(2)}` : '—'}</td>
                                                <td className="px-4 py-2.5 text-right">
                                                  {p.d1_high ? (
                                                    <div className="flex flex-col items-end">
                                                      <span>${p.d1_high.toFixed(2)}</span>
                                                      <span className="text-[10px] text-emerald-500 font-bold">
                                                        +{p.close_d0 ? (((p.d1_high - p.close_d0) / p.close_d0) * 100).toFixed(1) : 0}%
                                                      </span>
                                                    </div>
                                                  ) : '—'}
                                                </td>
                                                <td className="px-4 py-2.5 text-right">{p.d1_low ? `$${p.d1_low.toFixed(2)}` : '—'}</td>
                                                <td className="px-4 py-2.5 text-right">
                                                  {p.d1_close ? (
                                                    <div className="flex flex-col items-end">
                                                      <span>${p.d1_close.toFixed(2)}</span>
                                                      <span className={`text-[10px] font-bold ${
                                                        p.d1_close >= (p.close_d0 || 0) ? 'text-emerald-500' : 'text-red-500'
                                                      }`}>
                                                        {formatPercent(p.close_d0 ? ((p.d1_close - p.close_d0) / p.close_d0) * 100 : null)}
                                                      </span>
                                                    </div>
                                                  ) : '—'}
                                                </td>
                                                <td className="px-4 py-2.5 text-right text-gray-400">{p.d1_volume ? p.d1_volume.toLocaleString() : '—'}</td>
                                              </tr>

                                              {/* Day 2 */}
                                              <tr className="border-b border-gray-150 dark:border-gray-850/50 last:border-0 hover:bg-gray-100/10">
                                                <td className="px-4 py-2.5 font-sans font-semibold text-gray-700 dark:text-gray-300">Day 2</td>
                                                <td className="px-4 py-2.5 text-right">{p.d2_open ? `$${p.d2_open.toFixed(2)}` : '—'}</td>
                                                <td className="px-4 py-2.5 text-right">
                                                  {p.d2_high ? (
                                                    <div className="flex flex-col items-end">
                                                      <span>${p.d2_high.toFixed(2)}</span>
                                                      <span className="text-[10px] text-emerald-500 font-bold">
                                                        +{p.close_d0 ? (((p.d2_high - p.close_d0) / p.close_d0) * 100).toFixed(1) : 0}%
                                                      </span>
                                                    </div>
                                                  ) : '—'}
                                                </td>
                                                <td className="px-4 py-2.5 text-right">{p.d2_low ? `$${p.d2_low.toFixed(2)}` : '—'}</td>
                                                <td className="px-4 py-2.5 text-right">
                                                  {p.d2_close ? (
                                                    <div className="flex flex-col items-end">
                                                      <span>${p.d2_close.toFixed(2)}</span>
                                                      <span className={`text-[10px] font-bold ${
                                                        p.d2_close >= (p.close_d0 || 0) ? 'text-emerald-500' : 'text-red-500'
                                                      }`}>
                                                        {formatPercent(p.close_d0 ? ((p.d2_close - p.close_d0) / p.close_d0) * 100 : null)}
                                                      </span>
                                                    </div>
                                                  ) : '—'}
                                                </td>
                                                <td className="px-4 py-2.5 text-right text-gray-400">{p.d2_volume ? p.d2_volume.toLocaleString() : '—'}</td>
                                              </tr>

                                              {/* Day 3 */}
                                              <tr className="border-b border-gray-150 dark:border-gray-850/50 last:border-0 hover:bg-gray-100/10">
                                                <td className="px-4 py-2.5 font-sans font-semibold text-gray-700 dark:text-gray-300">Day 3</td>
                                                <td className="px-4 py-2.5 text-right">{p.d3_open ? `$${p.d3_open.toFixed(2)}` : '—'}</td>
                                                <td className="px-4 py-2.5 text-right">
                                                  {p.d3_high ? (
                                                    <div className="flex flex-col items-end">
                                                      <span>${p.d3_high.toFixed(2)}</span>
                                                      <span className="text-[10px] text-emerald-500 font-bold">
                                                        +{p.close_d0 ? (((p.d3_high - p.close_d0) / p.close_d0) * 100).toFixed(1) : 0}%
                                                      </span>
                                                    </div>
                                                  ) : '—'}
                                                </td>
                                                <td className="px-4 py-2.5 text-right">{p.d3_low ? `$${p.d3_low.toFixed(2)}` : '—'}</td>
                                                <td className="px-4 py-2.5 text-right">
                                                  {p.d3_close ? (
                                                    <div className="flex flex-col items-end">
                                                      <span>${p.d3_close.toFixed(2)}</span>
                                                      <span className={`text-[10px] font-bold ${
                                                        p.d3_close >= (p.close_d0 || 0) ? 'text-emerald-500' : 'text-red-500'
                                                      }`}>
                                                        {formatPercent(p.close_d0 ? ((p.d3_close - p.close_d0) / p.close_d0) * 100 : null)}
                                                      </span>
                                                    </div>
                                                  ) : '—'}
                                                </td>
                                                <td className="px-4 py-2.5 text-right text-gray-400">{p.d3_volume ? p.d3_volume.toLocaleString() : '—'}</td>
                                              </tr>
                                            </tbody>
                                          </table>
                                        </div>
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </>
                          )
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ── Tab Content: PERFORMANCE STATS ──────────────────────────────── */}
          {activeTab === 'performance' && performance && (
            <div className="space-y-6">
              {/* Summary Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <div className="bg-white dark:bg-gray-900 border border-gray-250/50 dark:border-gray-800 p-4.5 rounded-xl shadow-sm">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1">Total Studies</span>
                  <span className="text-2xl font-bold font-mono">{performance.summary.total_picks || 0}</span>
                </div>
                <div className="bg-white dark:bg-gray-900 border border-gray-250/50 dark:border-gray-800 p-4.5 rounded-xl shadow-sm">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1">Win Rate (≥10%)</span>
                  <span className="text-2xl font-bold font-mono text-green-500">{performance.summary.win_rate || 0}%</span>
                </div>
                <div className="bg-white dark:bg-gray-900 border border-gray-250/50 dark:border-gray-800 p-4.5 rounded-xl shadow-sm">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1">Super Rate (≥30%)</span>
                  <span className="text-2xl font-bold font-mono text-emerald-500">{performance.summary.super_win_rate || 0}%</span>
                </div>
                <div className="bg-white dark:bg-gray-900 border border-gray-250/50 dark:border-gray-800 p-4.5 rounded-xl shadow-sm">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1">Avg Max Extension</span>
                  <span className="text-2xl font-bold font-mono text-emerald-400">+{performance.summary.avg_max_ext || 0}%</span>
                </div>
                <div className="bg-white dark:bg-gray-900 border border-gray-250/50 dark:border-gray-800 p-4.5 rounded-xl shadow-sm">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1">Avg Day 1 Close</span>
                  <span className={`text-2xl font-bold font-mono ${performance.summary.avg_d1_ret >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                    {performance.summary.avg_d1_ret >= 0 ? '+' : ''}{performance.summary.avg_d1_ret || 0}%
                  </span>
                </div>
                <div className="bg-white dark:bg-gray-900 border border-gray-250/50 dark:border-gray-800 p-4.5 rounded-xl shadow-sm">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-1">Avg Day 3 Close</span>
                  <span className={`text-2xl font-bold font-mono ${performance.summary.avg_d3_ret >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                    {performance.summary.avg_d3_ret >= 0 ? '+' : ''}{performance.summary.avg_d3_ret || 0}%
                  </span>
                </div>
              </div>

              {/* Categorized Scorecards */}
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {/* Float Category Scorecard */}
                <div className="bg-white dark:bg-gray-950/40 border border-gray-250/50 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm">
                  <div className="px-4 py-3 bg-gray-50/50 dark:bg-gray-900/30 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
                    <span className="text-sm font-bold uppercase tracking-wider text-gray-400">Breakdown by Ticker Float</span>
                    <Layers size={14} className="text-gray-400" />
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-gray-250/50 dark:border-gray-850 text-gray-500 font-bold text-[10px] uppercase">
                          <th className="px-4 py-2">Float range</th>
                          <th className="px-4 py-2 text-center">Sample Size</th>
                          <th className="px-4 py-2 text-center">Win Rate (≥10%)</th>
                          <th className="px-4 py-2 text-center">Super Win (≥30%)</th>
                          <th className="px-4 py-2 text-right">Avg Max Run</th>
                        </tr>
                      </thead>
                      <tbody>
                        {performance.groups.float_category.map(row => (
                          <tr key={row.group_value} className="border-b border-gray-150 dark:border-gray-850/50 last:border-0 hover:bg-gray-100/10">
                            <td className="px-4 py-2.5 font-medium">{row.group_value}</td>
                            <td className="px-4 py-2.5 text-center font-mono">{row.count}</td>
                            <td className="px-4 py-2.5 text-center font-mono font-bold text-green-500">{row.win_rate}%</td>
                            <td className="px-4 py-2.5 text-center font-mono font-bold text-emerald-500">{row.super_win_rate}%</td>
                            <td className="px-4 py-2.5 text-right font-mono font-bold text-emerald-400">+{row.avg_max_ext}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Gap Category Scorecard */}
                <div className="bg-white dark:bg-gray-950/40 border border-gray-250/50 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm">
                  <div className="px-4 py-3 bg-gray-50/50 dark:bg-gray-900/30 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
                    <span className="text-sm font-bold uppercase tracking-wider text-gray-400">Breakdown by Day 0 Gap %</span>
                    <TrendingUp size={14} className="text-gray-400" />
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-gray-250/50 dark:border-gray-850 text-gray-500 font-bold text-[10px] uppercase">
                          <th className="px-4 py-2">Gap range</th>
                          <th className="px-4 py-2 text-center">Sample Size</th>
                          <th className="px-4 py-2 text-center">Win Rate (≥10%)</th>
                          <th className="px-4 py-2 text-center">Super Win (≥30%)</th>
                          <th className="px-4 py-2 text-right">Avg Max Run</th>
                        </tr>
                      </thead>
                      <tbody>
                        {performance.groups.gap_category.map(row => (
                          <tr key={row.group_value} className="border-b border-gray-150 dark:border-gray-850/50 last:border-0 hover:bg-gray-100/10">
                            <td className="px-4 py-2.5 font-medium">{row.group_value}</td>
                            <td className="px-4 py-2.5 text-center font-mono">{row.count}</td>
                            <td className="px-4 py-2.5 text-center font-mono font-bold text-green-500">{row.win_rate}%</td>
                            <td className="px-4 py-2.5 text-center font-mono font-bold text-emerald-500">{row.super_win_rate}%</td>
                            <td className="px-4 py-2.5 text-right font-mono font-bold text-emerald-400">+{row.avg_max_ext}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* News Catalyst Freshness Scorecard */}
                <div className="bg-white dark:bg-gray-950/40 border border-gray-250/50 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm">
                  <div className="px-4 py-3 bg-gray-50/50 dark:bg-gray-900/30 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
                    <span className="text-sm font-bold uppercase tracking-wider text-gray-400">Fresh News Catalyst vs Stale</span>
                    <FileText size={14} className="text-gray-400" />
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-gray-250/50 dark:border-gray-850 text-gray-500 font-bold text-[10px] uppercase">
                          <th className="px-4 py-2">Catalyst status</th>
                          <th className="px-4 py-2 text-center">Sample Size</th>
                          <th className="px-4 py-2 text-center">Win Rate (≥10%)</th>
                          <th className="px-4 py-2 text-center">Super Win (≥30%)</th>
                          <th className="px-4 py-2 text-right">Avg Max Run</th>
                        </tr>
                      </thead>
                      <tbody>
                        {performance.groups.news_freshness.map(row => (
                          <tr key={row.group_value} className="border-b border-gray-150 dark:border-gray-850/50 last:border-0 hover:bg-gray-100/10">
                            <td className="px-4 py-2.5 font-medium">
                              {row.group_value === 'true' ? (
                                <span className="flex items-center gap-1 text-emerald-500 font-bold">
                                  <CheckCircle size={12} /> Fresh Catalyst
                                </span>
                              ) : (
                                <span className="flex items-center gap-1 text-gray-400">
                                  <XCircle size={12} /> Stale/No Catalyst
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2.5 text-center font-mono">{row.count}</td>
                            <td className="px-4 py-2.5 text-center font-mono font-bold text-green-500">{row.win_rate}%</td>
                            <td className="px-4 py-2.5 text-center font-mono font-bold text-emerald-500">{row.super_win_rate}%</td>
                            <td className="px-4 py-2.5 text-right font-mono font-bold text-emerald-400">+{row.avg_max_ext}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Dilution Risk Scorecard */}
                <div className="bg-white dark:bg-gray-950/40 border border-gray-250/50 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm">
                  <div className="px-4 py-3 bg-gray-50/50 dark:bg-gray-900/30 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
                    <span className="text-sm font-bold uppercase tracking-wider text-gray-400">Breakdown by Dilution Risk</span>
                    <ShieldAlert size={14} className="text-gray-400" />
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-gray-250/50 dark:border-gray-850 text-gray-500 font-bold text-[10px] uppercase">
                          <th className="px-4 py-2">Risk category</th>
                          <th className="px-4 py-2 text-center">Sample Size</th>
                          <th className="px-4 py-2 text-center">Win Rate (≥10%)</th>
                          <th className="px-4 py-2 text-center">Super Win (≥30%)</th>
                          <th className="px-4 py-2 text-right">Avg Max Run</th>
                        </tr>
                      </thead>
                      <tbody>
                        {performance.groups.dilution_risk.map(row => (
                          <tr key={row.group_value} className="border-b border-gray-150 dark:border-gray-850/50 last:border-0 hover:bg-gray-100/10">
                            <td className="px-4 py-2.5 font-medium">
                              <span className={`inline-flex items-center gap-1 ${
                                row.group_value === 'High' ? 'text-red-500 font-bold' :
                                row.group_value === 'Medium' ? 'text-yellow-500' :
                                'text-emerald-500'
                              }`}>
                                {row.group_value} Risk
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-center font-mono">{row.count}</td>
                            <td className="px-4 py-2.5 text-center font-mono font-bold text-green-500">{row.win_rate}%</td>
                            <td className="px-4 py-2.5 text-center font-mono font-bold text-emerald-500">{row.super_win_rate}%</td>
                            <td className="px-4 py-2.5 text-right font-mono font-bold text-emerald-400">+{row.avg_max_ext}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Sector Scorecard */}
                <div className="bg-white dark:bg-gray-950/40 border border-gray-250/50 dark:border-gray-800 rounded-xl overflow-hidden shadow-sm xl:col-span-2">
                  <div className="px-4 py-3 bg-gray-50/50 dark:bg-gray-900/30 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
                    <span className="text-sm font-bold uppercase tracking-wider text-gray-400">Breakdown by Industry Sector</span>
                    <BarChart2 size={14} className="text-gray-400" />
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-gray-250/50 dark:border-gray-850 text-gray-500 font-bold text-[10px] uppercase">
                          <th className="px-4 py-2">Sector</th>
                          <th className="px-4 py-2 text-center">Sample Size</th>
                          <th className="px-4 py-2 text-center">Win Rate (≥10%)</th>
                          <th className="px-4 py-2 text-center">Super Win (≥30%)</th>
                          <th className="px-4 py-2 text-right">Avg Max Run</th>
                        </tr>
                      </thead>
                      <tbody>
                        {performance.groups.sector.map(row => (
                          <tr key={row.group_value} className="border-b border-gray-150 dark:border-gray-850/50 last:border-0 hover:bg-gray-100/10">
                            <td className="px-4 py-2.5 font-medium">{row.group_value}</td>
                            <td className="px-4 py-2.5 text-center font-mono">{row.count}</td>
                            <td className="px-4 py-2.5 text-center font-mono font-bold text-green-500">{row.win_rate}%</td>
                            <td className="px-4 py-2.5 text-center font-mono font-bold text-emerald-500">{row.super_win_rate}%</td>
                            <td className="px-4 py-2.5 text-right font-mono font-bold text-emerald-400">+{row.avg_max_ext}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </main>
  )
}
