'use client'

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import Link from 'next/link'
import { MTFInPlayItem, MTFScannerData, MTFFilters, getMTFScanner } from '@/lib/api'
import { fmtFloat, fmtVol } from '@/lib/format'
import { Sparkline } from '@/components/Sparkline'
import { useSharedWebSocket } from '@/components/live-gainers/useAlertStream'
import {
  Flame,
  Zap,
  SlidersHorizontal,
  RefreshCw,
  LayoutGrid,
  Table as TableIcon,
  Search,
  ArrowUpRight,
  Shield,
  Layers,
  Crosshair,
  ChevronDown,
  ChevronUp,
  Volume2,
  VolumeX,
  ExternalLink,
  RotateCcw
} from 'lucide-react'

export interface MTFScannerWidgetProps {
  items?: MTFInPlayItem[]
  initialData?: MTFScannerData
  onSelectTicker?: (ticker: string) => void
}

type PresetType = 'warrior' | 'high_conviction' | 'coincident' | 'nano_float' | 'all' | 'custom'
type SortField = 'score' | 'rvol' | 'float' | 'gap_pct' | 'price' | 'sr_dist'
type SortDir = 'asc' | 'desc'
type ViewMode = 'grid' | 'table'

export const MTFScannerWidget: React.FC<MTFScannerWidgetProps> = ({
  items: propItems,
  initialData,
  onSelectTicker
}) => {
  // State
  const [dataItems, setDataItems] = useState<MTFInPlayItem[]>(
    propItems ?? initialData?.in_play ?? []
  )
  const [loading, setLoading] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<string>(
    initialData?.timestamp ? new Date(initialData.timestamp).toLocaleTimeString() : 'Just now'
  )
  const [totalScanned, setTotalScanned] = useState<number>(
    initialData?.total_scanned ?? dataItems.length
  )

  // Preset & Filters State
  const [preset, setPreset] = useState<PresetType>('warrior')
  const [minPrice, setMinPrice] = useState<number>(1.0)
  const [maxPrice, setMaxPrice] = useState<number>(20.0)
  const [minRvol, setMinRvol] = useState<number>(5.0)
  const [maxFloatM, setMaxFloatM] = useState<number | null>(20.0) // in millions
  const [minScore, setMinScore] = useState<number>(50)
  const [coincidentOnly, setCoincidentOnly] = useState<boolean>(false)
  const [searchQuery, setSearchQuery] = useState<string>('')

  // Display & UI state
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false)
  const [sortBy, setSortBy] = useState<SortField>('score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [audioAlerts, setAudioAlerts] = useState<boolean>(false)

  // Shared WebSocket connection
  const { connected: wsConnected, subscribe } = useSharedWebSocket()

  // Fetch updated MTF scanner data from backend
  const fetchScannerData = useCallback(async (forceRefresh = false) => {
    setLoading(true)
    try {
      const filters: MTFFilters = {
        min_price: minPrice,
        max_price: maxPrice,
        min_rvol: minRvol,
        max_float: maxFloatM !== null ? maxFloatM * 1_000_000 : undefined,
        min_score: minScore,
        coincident_only: coincidentOnly,
        sort_by: sortBy,
        force_refresh: forceRefresh,
      }
      const res = await getMTFScanner(filters)
      if (res && res.in_play) {
        setDataItems(res.in_play)
        setTotalScanned(res.total_scanned ?? res.in_play.length)
        setLastUpdated(new Date().toLocaleTimeString())
      }
    } catch (err) {
      console.error('Failed to fetch MTF scanner data:', err)
    } finally {
      setLoading(false)
    }
  }, [minPrice, maxPrice, minRvol, maxFloatM, minScore, coincidentOnly, sortBy])

  // Sync prop changes
  useEffect(() => {
    if (propItems && propItems.length > 0) {
      setDataItems(propItems)
    }
  }, [propItems])

  // WebSocket listener for live MTF scanner broadcasts
  useEffect(() => {
    const unsubscribe = subscribe((msg: Record<string, unknown>) => {
      if (msg && msg.type === 'MTF_SCANNER_UPDATE' && Array.isArray(msg.in_play)) {
        setDataItems(msg.in_play as MTFInPlayItem[])
        setLastUpdated(new Date().toLocaleTimeString())
      }
    })
    return () => {
      unsubscribe()
    }
  }, [subscribe])

  // Periodic fallback refresh (every 30s)
  useEffect(() => {
    const timer = setInterval(() => {
      fetchScannerData(false)
    }, 30000)
    return () => clearInterval(timer)
  }, [fetchScannerData])

  // Apply preset logic
  const handleSelectPreset = (newPreset: PresetType) => {
    setPreset(newPreset)
    if (newPreset === 'warrior') {
      setMinPrice(1.0)
      setMaxPrice(20.0)
      setMinRvol(5.0)
      setMaxFloatM(20.0)
      setMinScore(50)
      setCoincidentOnly(false)
    } else if (newPreset === 'high_conviction') {
      setMinPrice(1.0)
      setMaxPrice(50.0)
      setMinRvol(3.0)
      setMaxFloatM(null)
      setMinScore(75)
      setCoincidentOnly(false)
    } else if (newPreset === 'coincident') {
      setMinPrice(1.0)
      setMaxPrice(50.0)
      setMinRvol(3.0)
      setMaxFloatM(null)
      setMinScore(50)
      setCoincidentOnly(true)
    } else if (newPreset === 'nano_float') {
      setMinPrice(1.0)
      setMaxPrice(15.0)
      setMinRvol(5.0)
      setMaxFloatM(10.0)
      setMinScore(50)
      setCoincidentOnly(false)
    } else if (newPreset === 'all') {
      setMinPrice(0.5)
      setMaxPrice(200.0)
      setMinRvol(1.0)
      setMaxFloatM(null)
      setMinScore(40)
      setCoincidentOnly(false)
    }
  }

  // Filtered and sorted items on client
  const filteredItems = useMemo(() => {
    return dataItems
      .filter((item) => {
        // Price filter
        if (item.price < minPrice || item.price > maxPrice) return false

        // RVOL filter
        const effectiveRvol = item.rvol ?? item.rvol_1m ?? 1.0
        if (effectiveRvol < minRvol) return false

        // Float filter
        if (maxFloatM !== null && item.float_shares != null) {
          if (item.float_shares > maxFloatM * 1_000_000) return false
        }

        // Score filter
        if (item.score < minScore) return false

        // Coincident only
        if (coincidentOnly && !item.is_coincident) return false

        // Search query
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase()
          const tickerMatch = item.ticker.toLowerCase().includes(q)
          const companyMatch = (item.company_name ?? '').toLowerCase().includes(q)
          const sectorMatch = (item.sector ?? '').toLowerCase().includes(q)
          if (!tickerMatch && !companyMatch && !sectorMatch) return false
        }

        return true
      })
      .sort((a, b) => {
        let diff = 0
        if (sortBy === 'score') {
          diff = (a.score ?? 0) - (b.score ?? 0)
        } else if (sortBy === 'rvol') {
          const rA = a.rvol ?? a.rvol_1m ?? 0
          const rB = b.rvol ?? b.rvol_1m ?? 0
          diff = rA - rB
        } else if (sortBy === 'float') {
          const fA = a.float_shares ?? 999999999
          const fB = b.float_shares ?? 999999999
          diff = fA - fB
        } else if (sortBy === 'gap_pct') {
          diff = (a.gap_pct ?? 0) - (b.gap_pct ?? 0)
        } else if (sortBy === 'price') {
          diff = a.price - b.price
        } else if (sortBy === 'sr_dist') {
          const dA = Math.abs(a.sr_dist_pct ?? 0)
          const dB = Math.abs(b.sr_dist_pct ?? 0)
          diff = dA - dB
        }
        return sortDir === 'desc' ? -diff : diff
      })
  }, [dataItems, minPrice, maxPrice, minRvol, maxFloatM, minScore, coincidentOnly, searchQuery, sortBy, sortDir])

  // Summary statistics
  const stats = useMemo(() => {
    if (filteredItems.length === 0) {
      return { avgRvol: '0.0', highConvictionCount: 0, coincidentCount: 0, topScore: 0, topTicker: '—' }
    }
    const rvols = filteredItems.map((i) => i.rvol ?? i.rvol_1m ?? 1.0)
    const avgRvol = rvols.reduce((acc, v) => acc + v, 0) / rvols.length
    const highConvictionCount = filteredItems.filter((i) => i.score >= 75).length
    const coincidentCount = filteredItems.filter((i) => i.is_coincident).length
    const topItem = [...filteredItems].sort((a, b) => b.score - a.score)[0]
    return {
      avgRvol: avgRvol.toFixed(1),
      highConvictionCount,
      coincidentCount,
      topScore: topItem ? topItem.score : 0,
      topTicker: topItem ? topItem.ticker : '—',
    }
  }, [filteredItems])

  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(field)
      setSortDir('desc')
    }
  }

  // Helper badge color
  const getScoreBadge = (score: number, isCoincident: boolean) => {
    if (score >= 75) {
      return {
        bg: 'bg-rose-500/20 text-rose-300 border-rose-500/50',
        text: 'text-rose-400',
        ring: 'border-rose-500/60 shadow-[0_0_12px_rgba(244,63,94,0.25)]',
        label: 'HIGH CONVICTION',
      }
    }
    if (isCoincident) {
      return {
        bg: 'bg-purple-500/20 text-purple-300 border-purple-500/50',
        text: 'text-purple-400',
        ring: 'border-purple-500/60 shadow-[0_0_12px_rgba(168,85,247,0.25)]',
        label: 'COINCIDENT S/R',
      }
    }
    return {
      bg: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
      text: 'text-amber-400',
      ring: 'border-slate-700/80',
      label: 'IN PLAY',
    }
  }

  return (
    <div className="bg-[#0b0f19] border border-slate-800/90 rounded-xl overflow-hidden shadow-2xl space-y-0 transition-all">
      {/* ── Main Header ──────────────────────────────────────────────────────── */}
      <div className="bg-gradient-to-r from-slate-900 via-[#101726] to-slate-900 px-4 py-3.5 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="relative flex items-center justify-center">
            <span className={`w-3 h-3 rounded-full ${wsConnected ? 'bg-emerald-400' : 'bg-amber-400'} animate-pulse`} />
            <span className={`absolute w-5 h-5 rounded-full ${wsConnected ? 'bg-emerald-400/30' : 'bg-amber-400/30'} animate-ping`} />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-extrabold text-slate-100 tracking-tight flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-sky-400" />
                MTF S/R Momentum Scanner
              </h3>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-300 border border-sky-500/30 font-semibold">
                {filteredItems.length} In-Play
              </span>
            </div>
            <p className="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5 font-mono">
              <span>Warrior Filter: <strong className="text-slate-300">$1–$20 · ≥5x RVOL · &lt;20M Float</strong></span>
              <span>•</span>
              <span>Synced {lastUpdated}</span>
            </p>
          </div>
        </div>

        {/* Quick Toolbar */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setFilterDrawerOpen((v) => !v)}
            className={`flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              filterDrawerOpen
                ? 'bg-sky-500/20 text-sky-300 border-sky-500/40 shadow-sm'
                : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-700/80'
            }`}
            title="Toggle Filter Controls"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>Filters</span>
            {filterDrawerOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>

          <div className="flex items-center bg-slate-800/90 rounded-lg p-0.5 border border-slate-700">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-md text-xs transition-colors ${
                viewMode === 'grid' ? 'bg-sky-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Cards Grid View"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`p-1.5 rounded-md text-xs transition-colors ${
                viewMode === 'table' ? 'bg-sky-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Dense Table View"
            >
              <TableIcon className="w-3.5 h-3.5" />
            </button>
          </div>

          <button
            onClick={() => setAudioAlerts((v) => !v)}
            className={`p-1.5 rounded-lg text-xs border transition-colors ${
              audioAlerts
                ? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                : 'bg-slate-800/80 text-slate-400 border-slate-700 hover:text-slate-200'
            }`}
            title={audioAlerts ? 'Audio Alerts Enabled' : 'Audio Alerts Disabled'}
          >
            {audioAlerts ? <Volume2 className="w-4 h-4 text-purple-400" /> : <VolumeX className="w-4 h-4" />}
          </button>

          <button
            onClick={() => fetchScannerData(true)}
            disabled={loading}
            className="flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/80 text-slate-300 border border-slate-700 hover:bg-slate-700/80 hover:text-white transition-all disabled:opacity-50"
            title="Force Scan Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-sky-400' : ''}`} />
            <span>Scan</span>
          </button>
        </div>
      </div>

      {/* ── Preset Selector Bar ──────────────────────────────────────────────── */}
      <div className="bg-[#0e1320] px-4 py-2.5 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mr-1">Presets:</span>

          <button
            onClick={() => handleSelectPreset('warrior')}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-semibold border transition-all ${
              preset === 'warrior'
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-sm'
                : 'bg-slate-800/50 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
            }`}
          >
            <Flame className="w-3.5 h-3.5 text-amber-400" />
            <span>Warrior Low-Float</span>
            <span className="text-[10px] text-amber-400/80 font-mono">($1-$20 | ≥5x | &lt;20M)</span>
          </button>

          <button
            onClick={() => handleSelectPreset('high_conviction')}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-semibold border transition-all ${
              preset === 'high_conviction'
                ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 shadow-sm'
                : 'bg-slate-800/50 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
            }`}
          >
            <Zap className="w-3.5 h-3.5 text-rose-400" />
            <span>High Conviction</span>
            <span className="text-[10px] text-rose-400/80 font-mono">(≥75 pts)</span>
          </button>

          <button
            onClick={() => handleSelectPreset('coincident')}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-semibold border transition-all ${
              preset === 'coincident'
                ? 'bg-purple-500/20 text-purple-300 border-purple-500/50 shadow-sm'
                : 'bg-slate-800/50 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
            }`}
          >
            <Shield className="w-3.5 h-3.5 text-purple-400" />
            <span>Coincident S/R</span>
            <span className="text-[10px] text-purple-400/80 font-mono">(Daily + 5m)</span>
          </button>

          <button
            onClick={() => handleSelectPreset('nano_float')}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-md text-xs font-semibold border transition-all ${
              preset === 'nano_float'
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-sm'
                : 'bg-slate-800/50 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
            }`}
          >
            <span>💧 Nano Float</span>
            <span className="text-[10px] text-cyan-400/80 font-mono">(&lt;10M)</span>
          </button>

          <button
            onClick={() => handleSelectPreset('all')}
            className={`px-2.5 py-1 rounded-md text-xs font-semibold border transition-all ${
              preset === 'all'
                ? 'bg-slate-700 text-slate-100 border-slate-600 shadow-sm'
                : 'bg-slate-800/50 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
            }`}
          >
            All In-Play
          </button>
        </div>

        {/* Search Box */}
        <div className="relative min-w-[160px]">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search symbol / sector..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-2.5 py-1 bg-slate-900/90 text-xs text-slate-200 border border-slate-700/80 rounded-md placeholder-slate-500 focus:outline-none focus:border-sky-500"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="text-slate-400 hover:text-slate-200 text-xs absolute right-2 top-1/2 -translate-y-1/2 font-bold"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* ── Expandable Filter Drawer ────────────────────────────────────────── */}
      {filterDrawerOpen && (
        <div className="bg-[#0d121f] px-4 py-3.5 border-b border-slate-800 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5 text-xs text-slate-300">
          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
              Price Range ($)
            </label>
            <div className="flex items-center space-x-1.5 font-mono">
              <input
                type="number"
                step="0.5"
                min="0.1"
                value={minPrice}
                onChange={(e) => {
                  setMinPrice(parseFloat(e.target.value) || 0)
                  setPreset('custom')
                }}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
                placeholder="Min"
              />
              <span className="text-slate-500">–</span>
              <input
                type="number"
                step="1"
                min="1"
                value={maxPrice}
                onChange={(e) => {
                  setMaxPrice(parseFloat(e.target.value) || 100)
                  setPreset('custom')
                }}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
                placeholder="Max"
              />
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
              Min Relative Vol (RVOL)
            </label>
            <select
              value={minRvol}
              onChange={(e) => {
                setMinRvol(parseFloat(e.target.value))
                setPreset('custom')
              }}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
            >
              <option value="1">≥ 1.0x</option>
              <option value="3">≥ 3.0x</option>
              <option value="5">≥ 5.0x (Warrior Default)</option>
              <option value="8">≥ 8.0x (Extreme Volume)</option>
              <option value="10">≥ 10.0x (Hyper Surge)</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
              Max Float Shares
            </label>
            <select
              value={maxFloatM === null ? 'any' : maxFloatM}
              onChange={(e) => {
                setMaxFloatM(e.target.value === 'any' ? null : parseFloat(e.target.value))
                setPreset('custom')
              }}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
            >
              <option value="5">Under 5M (Super Nano)</option>
              <option value="10">Under 10M (Nano Float)</option>
              <option value="20">Under 20M (Warrior Default)</option>
              <option value="50">Under 50M (Low Float)</option>
              <option value="any">Any Float</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
              Min Confluence Score
            </label>
            <select
              value={minScore}
              onChange={(e) => {
                setMinScore(parseInt(e.target.value))
                setPreset('custom')
              }}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs font-mono"
            >
              <option value="40">≥ 40 pts (Approaching)</option>
              <option value="50">≥ 50 pts (In-Play Standard)</option>
              <option value="65">≥ 65 pts (Strong Setup)</option>
              <option value="75">≥ 75 pts (High Conviction)</option>
              <option value="85">≥ 85 pts (Ultra Confluence)</option>
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
              Confluence Type
            </label>
            <label className="flex items-center space-x-2 mt-1 cursor-pointer">
              <input
                type="checkbox"
                checked={coincidentOnly}
                onChange={(e) => {
                  setCoincidentOnly(e.target.checked)
                  setPreset('custom')
                }}
                className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-sky-500 w-3.5 h-3.5"
              />
              <span className="text-xs text-slate-300">Coincident S/R Only</span>
            </label>
          </div>

          <div className="flex items-end">
            <button
              onClick={() => handleSelectPreset('warrior')}
              className="flex items-center justify-center space-x-1 w-full py-1.5 px-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors"
            >
              <RotateCcw className="w-3 h-3 text-slate-400" />
              <span>Reset to Defaults</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Summary Stats Banner ────────────────────────────────────────────── */}
      <div className="bg-[#090d16] px-4 py-2 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-4 text-slate-400">
          <div>
            <span>Qualified: </span>
            <strong className="text-slate-100">{filteredItems.length}</strong>
            <span className="text-slate-500 text-[11px]"> / {totalScanned} scanned</span>
          </div>
          <div>
            <span>Avg RVOL: </span>
            <strong className="text-amber-400 font-bold">{stats.avgRvol}x</strong>
          </div>
          <div>
            <span>High Conviction (≥75): </span>
            <strong className="text-rose-400 font-bold">{stats.highConvictionCount}</strong>
          </div>
          <div>
            <span>Coincident S/R: </span>
            <strong className="text-purple-400 font-bold">{stats.coincidentCount}</strong>
          </div>
          {stats.topScore > 0 && (
            <div>
              <span>Top Confluence: </span>
              <strong className="text-sky-300 font-bold">{stats.topTicker}</strong>
              <span className="text-slate-500"> ({stats.topScore} pts)</span>
            </div>
          )}
        </div>

        {/* Sort selector */}
        <div className="flex items-center space-x-2 text-[11px]">
          <span className="text-slate-500 uppercase tracking-wider font-sans font-semibold">Sort:</span>
          <div className="flex items-center space-x-1">
            <button
              onClick={() => handleSort('score')}
              className={`px-2 py-0.5 rounded ${
                sortBy === 'score' ? 'bg-sky-600/30 text-sky-300 border border-sky-500/40 font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Score {sortBy === 'score' && (sortDir === 'desc' ? '↓' : '↑')}
            </button>
            <button
              onClick={() => handleSort('rvol')}
              className={`px-2 py-0.5 rounded ${
                sortBy === 'rvol' ? 'bg-sky-600/30 text-sky-300 border border-sky-500/40 font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              RVOL {sortBy === 'rvol' && (sortDir === 'desc' ? '↓' : '↑')}
            </button>
            <button
              onClick={() => handleSort('float')}
              className={`px-2 py-0.5 rounded ${
                sortBy === 'float' ? 'bg-sky-600/30 text-sky-300 border border-sky-500/40 font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Float {sortBy === 'float' && (sortDir === 'desc' ? '↓' : '↑')}
            </button>
            <button
              onClick={() => handleSort('gap_pct')}
              className={`px-2 py-0.5 rounded ${
                sortBy === 'gap_pct' ? 'bg-sky-600/30 text-sky-300 border border-sky-500/40 font-bold' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Gain% {sortBy === 'gap_pct' && (sortDir === 'desc' ? '↓' : '↑')}
            </button>
          </div>
        </div>
      </div>

      {/* ── Content Body: Empty State or Grid / Table ────────────────────────── */}
      {filteredItems.length === 0 ? (
        <div className="p-10 text-center space-y-3">
          <div className="inline-flex items-center justify-center p-3 rounded-full bg-slate-800/80 border border-slate-700 text-slate-400">
            <Crosshair className="w-6 h-6" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-200">No stocks match active momentum filters</h4>
            <p className="text-xs text-slate-400 max-w-md mx-auto mt-1">
              Currently no tickers priced between ${minPrice}–${maxPrice} with RVOL ≥ {minRvol}x and confluence score ≥ {minScore} are actively testing Multi-Timeframe S/R levels.
            </p>
          </div>
          <button
            onClick={() => handleSelectPreset('all')}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow transition-all"
          >
            <span>Show All In-Play Stocks</span>
          </button>
        </div>
      ) : viewMode === 'grid' ? (
        /* ── Pro Grid Card View ────────────────────────────────────────────── */
        <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {filteredItems.map((item) => {
            const isHighConviction = item.score >= 75
            const isCoincident = item.is_coincident
            const badge = getScoreBadge(item.score, isCoincident)
            const effectiveRvol = item.rvol ?? item.rvol_1m ?? 1.0
            const isPositiveGap = (item.gap_pct ?? 0) >= 0

            return (
              <div
                key={item.ticker}
                onClick={() => onSelectTicker?.(item.ticker)}
                className={`group cursor-pointer rounded-xl border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl ${
                  isHighConviction
                    ? 'bg-gradient-to-b from-rose-950/25 via-[#16111f] to-slate-900/90 border-rose-700/50 hover:border-rose-500'
                    : isCoincident
                    ? 'bg-gradient-to-b from-purple-950/25 via-[#131124] to-slate-900/90 border-purple-700/50 hover:border-purple-500'
                    : 'bg-gradient-to-b from-slate-800/40 via-slate-900/60 to-[#0b0f19] border-slate-700/60 hover:border-sky-500/60'
                }`}
              >
                {/* Header: Ticker, Price, Gain, Score Gauge */}
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-baseline space-x-2">
                      <span className="font-mono font-black text-slate-100 text-base tracking-wide group-hover:text-sky-300 transition-colors">
                        {item.ticker}
                      </span>
                      <span className="text-xs font-mono font-bold text-slate-200">
                        ${item.price.toFixed(2)}
                      </span>
                      {item.gap_pct !== undefined && (
                        <span
                          className={`text-[11px] font-mono font-bold px-1.5 py-0.2 rounded ${
                            isPositiveGap ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'
                          }`}
                        >
                          {isPositiveGap ? '+' : ''}
                          {item.gap_pct.toFixed(1)}%
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400 truncate max-w-[180px] mt-0.5">
                      {item.company_name || item.sector || 'Equities'}
                    </div>
                  </div>

                  {/* Confluence Score Dial */}
                  <div className="flex flex-col items-end">
                    <div className="flex items-center space-x-1">
                      {isCoincident && (
                        <span
                          title="Coincident S/R: 5m S/R aligns with Daily S/R"
                          className="text-[9px] font-extrabold px-1.5 py-0.5 rounded bg-purple-500/25 text-purple-300 border border-purple-500/40 animate-pulse"
                        >
                          ⚡ CONFLUENCE
                        </span>
                      )}
                      <span className={`text-xs font-mono font-black px-2 py-0.5 rounded border ${badge.bg}`}>
                        {item.score} <span className="text-[10px] font-normal opacity-80">pts</span>
                      </span>
                    </div>
                    <span className="text-[9px] font-bold tracking-wider uppercase text-slate-400 mt-0.5">
                      {badge.label}
                    </span>
                  </div>
                </div>

                {/* Warrior Metric Pills (2x2 Grid) */}
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs font-mono">
                  {/* RVOL */}
                  <div className={`flex items-center justify-between p-2 rounded-lg border ${
                    effectiveRvol >= 5.0 ? 'bg-amber-500/10 border-amber-500/30' : 'bg-slate-800/40 border-slate-700/50'
                  }`}>
                    <span className="text-slate-400 text-[10px] flex items-center gap-1 font-sans">
                      <Flame className={`w-3 h-3 ${effectiveRvol >= 5.0 ? 'text-amber-400' : 'text-slate-400'}`} />
                      RVOL
                    </span>
                    <span className={`font-bold ${effectiveRvol >= 5.0 ? 'text-amber-300' : 'text-slate-200'}`}>
                      {effectiveRvol.toFixed(1)}x
                    </span>
                  </div>

                  {/* Float */}
                  <div className={`flex items-center justify-between p-2 rounded-lg border ${
                    item.float_shares && item.float_shares < 10_000_000
                      ? 'bg-purple-500/10 border-purple-500/30'
                      : item.float_shares && item.float_shares <= 20_000_000
                      ? 'bg-sky-500/10 border-sky-500/30'
                      : 'bg-slate-800/40 border-slate-700/50'
                  }`}>
                    <span className="text-slate-400 text-[10px] font-sans">FLOAT</span>
                    <span className={`font-bold ${
                      item.float_shares && item.float_shares < 10_000_000 ? 'text-purple-300' : 'text-sky-300'
                    }`}>
                      {fmtFloat(item.float_shares)}
                    </span>
                  </div>

                  {/* Volume */}
                  <div className="flex items-center justify-between p-2 rounded-lg bg-slate-800/40 border border-slate-700/50">
                    <span className="text-slate-400 text-[10px] font-sans">VOLUME</span>
                    <span className="text-slate-200 font-bold">
                      {fmtVol(item.volume)}
                    </span>
                  </div>

                  {/* VWAP */}
                  <div className="flex items-center justify-between p-2 rounded-lg bg-slate-800/40 border border-slate-700/50">
                    <span className="text-slate-400 text-[10px] font-sans">VWAP</span>
                    <span className="text-slate-200 font-bold">
                      ${(item.vwap ?? item.price).toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* S/R Proximity & Breakout Meter */}
                {item.sr_price && (
                  <div className="mt-3 p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 text-xs font-mono space-y-1.5">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-400 font-sans flex items-center gap-1 font-semibold">
                        <Crosshair className="w-3 h-3 text-sky-400" />
                        {item.sr_type} LEVEL:
                      </span>
                      <span className="font-bold text-slate-100">${item.sr_price.toFixed(2)}</span>
                    </div>

                    <div className="flex items-center justify-between text-[10px]">
                      <span className="text-slate-400 font-sans">Proximity:</span>
                      <span className={`font-bold ${
                        (item.sr_dist_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        {item.sr_dist_pct !== undefined ? `${item.sr_dist_pct > 0 ? '+' : ''}${item.sr_dist_pct.toFixed(2)}%` : 'At Level'}
                        <span className="text-slate-500 font-normal ml-1">
                          ({item.breakout_status?.replace(/_/g, ' ')})
                        </span>
                      </span>
                    </div>

                    {/* Proximity visual bar */}
                    <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          isHighConviction ? 'bg-rose-500' : isCoincident ? 'bg-purple-500' : 'bg-emerald-400'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(15, item.score))}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Sparkline & Active Signals */}
                <div className="mt-3 flex items-center justify-between pt-2 border-t border-slate-800/80">
                  <div className="flex flex-wrap gap-1 max-w-[70%]">
                    {item.signals.slice(0, 4).map((sig) => (
                      <span
                        key={sig}
                        className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700/80"
                      >
                        {sig.replace(/_/g, ' ')}
                      </span>
                    ))}
                    {item.signals.length > 4 && (
                      <span className="text-[9px] font-mono px-1 py-0.5 text-slate-400">
                        +{item.signals.length - 4}
                      </span>
                    )}
                  </div>

                  {item.sparkline && item.sparkline.length > 1 ? (
                    <div className="w-16 h-5">
                      <Sparkline points={item.sparkline} width={64} height={20} />
                    </div>
                  ) : (
                    <Link
                      href={`/alerts?symbol=${item.ticker}`}
                      className="text-[11px] text-sky-400 hover:text-sky-300 flex items-center gap-1 font-semibold group-hover:underline"
                    >
                      Chart <ExternalLink className="w-3 h-3" />
                    </Link>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        /* ── Dense Pro Table View ──────────────────────────────────────────── */
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse font-mono">
            <thead>
              <tr className="bg-slate-900/90 text-[10px] text-slate-400 uppercase tracking-wider border-b border-slate-800 font-sans font-bold">
                <th className="py-2.5 px-3">Symbol</th>
                <th className="py-2.5 px-3 cursor-pointer hover:text-slate-200" onClick={() => handleSort('price')}>
                  Price {sortBy === 'price' && (sortDir === 'desc' ? '↓' : '↑')}
                </th>
                <th className="py-2.5 px-3 cursor-pointer hover:text-slate-200" onClick={() => handleSort('gap_pct')}>
                  Gain% {sortBy === 'gap_pct' && (sortDir === 'desc' ? '↓' : '↑')}
                </th>
                <th className="py-2.5 px-3 cursor-pointer hover:text-slate-200" onClick={() => handleSort('score')}>
                  Score {sortBy === 'score' && (sortDir === 'desc' ? '↓' : '↑')}
                </th>
                <th className="py-2.5 px-3 cursor-pointer hover:text-slate-200" onClick={() => handleSort('rvol')}>
                  RVOL {sortBy === 'rvol' && (sortDir === 'desc' ? '↓' : '↑')}
                </th>
                <th className="py-2.5 px-3 cursor-pointer hover:text-slate-200" onClick={() => handleSort('float')}>
                  Float {sortBy === 'float' && (sortDir === 'desc' ? '↓' : '↑')}
                </th>
                <th className="py-2.5 px-3">Volume</th>
                <th className="py-2.5 px-3">VWAP</th>
                <th className="py-2.5 px-3 cursor-pointer hover:text-slate-200" onClick={() => handleSort('sr_dist')}>
                  Nearest S/R {sortBy === 'sr_dist' && (sortDir === 'desc' ? '↓' : '↑')}
                </th>
                <th className="py-2.5 px-3">Signals</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredItems.map((item) => {
                const isHighConviction = item.score >= 75
                const isCoincident = item.is_coincident
                const badge = getScoreBadge(item.score, isCoincident)
                const effectiveRvol = item.rvol ?? item.rvol_1m ?? 1.0
                const isPositiveGap = (item.gap_pct ?? 0) >= 0

                return (
                  <tr
                    key={item.ticker}
                    onClick={() => onSelectTicker?.(item.ticker)}
                    className={`cursor-pointer transition-colors ${
                      isHighConviction
                        ? 'bg-rose-950/15 hover:bg-rose-900/25'
                        : isCoincident
                        ? 'bg-purple-950/15 hover:bg-purple-900/25'
                        : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <td className="py-2.5 px-3">
                      <div className="flex items-center space-x-1.5">
                        <span className="font-bold text-slate-100 text-sm hover:text-sky-300">{item.ticker}</span>
                        {isCoincident && (
                          <span className="text-[9px] font-bold px-1 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40">
                            ⚡
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-400 font-sans truncate max-w-[120px]">
                        {item.company_name || item.sector || 'Equities'}
                      </div>
                    </td>

                    <td className="py-2.5 px-3 font-bold text-slate-200">
                      ${item.price.toFixed(2)}
                    </td>

                    <td className="py-2.5 px-3">
                      {item.gap_pct !== undefined ? (
                        <span className={`font-bold ${isPositiveGap ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isPositiveGap ? '+' : ''}{item.gap_pct.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>

                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded font-bold border text-xs ${badge.bg}`}>
                        {item.score} pts
                      </span>
                    </td>

                    <td className="py-2.5 px-3">
                      <span className={`font-bold ${effectiveRvol >= 5.0 ? 'text-amber-400' : 'text-slate-300'}`}>
                        {effectiveRvol.toFixed(1)}x
                      </span>
                    </td>

                    <td className="py-2.5 px-3">
                      <span className={`font-bold ${
                        item.float_shares && item.float_shares < 10_000_000
                          ? 'text-purple-300'
                          : item.float_shares && item.float_shares <= 20_000_000
                          ? 'text-sky-300'
                          : 'text-slate-300'
                      }`}>
                        {fmtFloat(item.float_shares)}
                      </span>
                    </td>

                    <td className="py-2.5 px-3 text-slate-300">
                      {fmtVol(item.volume)}
                    </td>

                    <td className="py-2.5 px-3 text-slate-300">
                      ${(item.vwap ?? item.price).toFixed(2)}
                    </td>

                    <td className="py-2.5 px-3">
                      {item.sr_price ? (
                        <div>
                          <span className="text-slate-200 font-bold">${item.sr_price.toFixed(2)}</span>
                          <span className="text-[10px] text-slate-400 ml-1">({item.sr_type})</span>
                          <div className="text-[10px] text-slate-500">
                            {item.breakout_status?.replace(/_/g, ' ')}
                          </div>
                        </div>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>

                    <td className="py-2.5 px-3">
                      <div className="flex flex-wrap gap-1 max-w-[200px]">
                        {item.signals.slice(0, 3).map((s) => (
                          <span
                            key={s}
                            className="text-[9px] px-1 py-0.2 rounded bg-slate-800 text-slate-300 border border-slate-700/60"
                          >
                            {s.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    </td>

                    <td className="py-2.5 px-3 text-right">
                      <Link
                        href={`/alerts?symbol=${item.ticker}`}
                        className="inline-flex items-center space-x-1 px-2 py-1 rounded bg-sky-600/20 hover:bg-sky-600/40 text-sky-300 text-xs font-semibold border border-sky-500/30 transition-colors"
                      >
                        <span>Alerts</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
