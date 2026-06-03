'use client'

import { useEffect, useState, useCallback, useRef, Fragment, useMemo } from 'react'
import {
  getLiveGainers,
  LiveGainerSnapshot,
  LiveGainerRow,
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  updateWatchlistItem,
  WatchlistItem
} from '@/lib/api'
import { useRouter } from 'next/navigation'
import {
  RefreshCw,
  TrendingUp,
  Clock,
  Wifi,
  WifiOff,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Bookmark,
  BookmarkCheck,
  ExternalLink,
  X,
  Sparkles,
  Pin,
  Info,
  Volume2,
  VolumeX,
  Bell,
  BellOff
} from 'lucide-react'
import MiniSessionChart from '@/components/MiniSessionChart'

// ── Helpers ────────────────────────────────────────────────────────────────────



function fmtVol(n: number | null) {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`
  return n.toLocaleString()
}

function MetricLabelWithTooltip({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <div className="flex items-center gap-1.5 text-gray-500 group/tooltip relative select-none">
      <span>{label}</span>
      <Info size={11} className="text-gray-650 hover:text-gray-400 cursor-help shrink-0" />
      <div className="pointer-events-none absolute bottom-full left-0 mb-2 hidden group-hover/tooltip:block bg-gray-950 border border-gray-800 text-white text-[10px] font-medium py-1.5 px-2.5 rounded-lg shadow-2xl w-60 leading-relaxed z-50 normal-case font-sans">
        {tooltip}
        <span className="absolute top-full left-3 border-4 border-transparent border-t-gray-950" />
      </div>
    </div>
  )
}

function fmtAge(isoUtc: string | null): string {
  if (!isoUtc) return ''
  const seconds = Math.floor((Date.now() - new Date(isoUtc).getTime()) / 1000)
  if (seconds < 60)  return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

function getTimeAgoBadge(tradeTimeMs: number | null) {
  if (!tradeTimeMs) return null
  const seconds = Math.floor((Date.now() - tradeTimeMs) / 1000)
  if (seconds < 300) { // < 5 min
    return { label: '⚡ Fresh', className: 'bg-violet-500/20 text-violet-300 border border-violet-500/30' }
  }
  if (seconds < 900) { // 5 - 15 min
    return { label: '🟢 Recent', className: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' }
  }
  if (seconds < 3600) { // 15 - 60 min
    return { label: '🟡 Stale', className: 'bg-amber-500/20 text-amber-300 border border-amber-500/30' }
  }
  return { label: '🔵 Old', className: 'bg-sky-500/20 text-sky-300 border border-sky-500/30' }
}

function getRvolBadgeStyle(rvol: number | null) {
  if (rvol == null) return { label: '—', className: 'bg-gray-500/10 text-gray-400 border border-gray-500/20' }
  const val = rvol
  if (val >= 1000) return { label: `${val.toFixed(1)}x (Extreme)`, className: 'bg-rose-500/20 text-rose-300 border border-rose-500/30' }
  if (val >= 200)  return { label: `${val.toFixed(1)}x (Mega)`, className: 'bg-emerald-600/30 text-emerald-200 border border-emerald-600/40' }
  if (val >= 50)   return { label: `${val.toFixed(1)}x (Strong)`, className: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold' }
  if (val >= 5)    return { label: `${val.toFixed(1)}x (Above Avg)`, className: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' }
  return { label: `${val.toFixed(1)}x`, className: 'bg-gray-500/10 text-gray-400 border border-gray-500/20' }
}

function getFloatBadgeStyle(floatShares: number | null) {
  if (floatShares == null) return { label: '—', className: 'bg-gray-500/10 text-gray-400 border border-gray-500/20' }
  const formatted = fmtVol(floatShares)
  if (floatShares < 1_000_000) {
    return { label: `${formatted} (Small)`, className: 'bg-rose-500/25 text-rose-300 border border-rose-500/40' }
  }
  if (floatShares < 10_000_000) {
    return { label: `${formatted} (Medium)`, className: 'bg-amber-500/25 text-amber-300 border border-amber-500/40' }
  }
  if (floatShares < 50_000_000) {
    return { label: `${formatted} (Normal)`, className: 'bg-emerald-500/25 text-emerald-300 border border-emerald-500/40' }
  }
  return { label: `${formatted} (Large)`, className: 'bg-blue-500/25 text-blue-300 border border-blue-500/40' }
}

function getSpreadBadgeStyle(spreadPct: number | null) {
  if (spreadPct == null) return { label: '—', className: 'text-gray-400 font-mono' }
  const formatted = `${spreadPct.toFixed(2)}%`
  if (spreadPct < 1) {
    return { label: formatted, className: 'text-gray-400 font-mono' }
  }
  if (spreadPct < 3) {
    return { label: `${formatted} (Elevated)`, className: 'bg-amber-500/10 text-amber-400 border border-amber-500/20 px-1.5 py-0.5 rounded text-[10px] font-mono' }
  }
  if (spreadPct < 5) {
    return { label: `${formatted} (High)`, className: 'bg-orange-500/10 text-orange-400 border border-orange-500/20 px-1.5 py-0.5 rounded text-[10px] font-mono' }
  }
  return { label: `${formatted} (Extreme)`, className: 'bg-rose-500/20 text-rose-300 border border-rose-500/30 px-1.5 py-0.5 rounded text-[10px] font-bold font-mono' }
}

function getMomStyle(mom: number | null | undefined) {
  if (mom == null) return 'text-slate-500'
  if (mom >= 4.0) return 'text-emerald-950 bg-emerald-400 font-extrabold shadow-sm shadow-emerald-400/50 animate-pulse px-1.5 py-0.5 rounded'
  if (mom <= -3.0) return 'text-red-100 bg-red-800 font-extrabold shadow-sm shadow-red-800/50 px-1.5 py-0.5 rounded'
  if (mom > 0) return 'text-emerald-400'
  if (mom < 0) return 'text-red-400'
  return 'text-slate-350'
}

function getAtrHodColor(val: number | null | undefined) {
  if (val == null) return 'text-slate-500'
  if (val === 0) return 'text-emerald-400 font-bold underline decoration-emerald-400/40'
  if (val < 0.2) return 'text-emerald-300 font-bold'
  if (val < 0.5) return 'text-emerald-400/70 font-semibold'
  if (val < 1.0) return 'text-slate-300'
  if (val < 2.0) return 'text-slate-400'
  return 'text-slate-500'
}

const getAtrSpreadStyle = (val: number | null | undefined) => {
  if (val == null) return { text: '—', className: 'text-slate-500' }
  if (val <= 0.3) return { text: `${val.toFixed(2)} (Tight / Clean)`, className: 'text-emerald-400 font-bold' }
  if (val > 1.0) return { text: `${val.toFixed(2)} (Dangerously Wide)`, className: 'text-rose-500 font-bold' }
  return { text: `${val.toFixed(2)} (Moderate)`, className: 'text-slate-300' }
}

const getAtrVwapStyle = (val: number | null | undefined) => {
  if (val == null) return { text: '—', className: 'text-slate-500' }
  if (val > 3.0) return { text: `+${val.toFixed(2)} (Overextended / Long)`, className: 'text-fuchsia-400 font-bold animate-pulse' }
  if (val < -3.0) return { text: `${val.toFixed(2)} (Heavily Short-Extended)`, className: 'text-orange-500 font-bold' }
  if (Math.abs(val) <= 1.0) return { text: `${val >= 0 ? '+' : ''}${val.toFixed(2)} (Mean Reversion Zone)`, className: 'text-emerald-400' }
  return { text: `${val >= 0 ? '+' : ''}${val.toFixed(2)} (Extending)`, className: 'text-slate-305' }
}

const getZenVStyle = (val: number | null | undefined) => {
  if (val == null) return { text: '—', className: 'text-slate-500' }
  if (val > 0) return { text: `▲ ${val.toFixed(2)}`, className: 'text-emerald-400 font-bold' }
  if (val < 0) return { text: `▼ ${val.toFixed(2)}`, className: 'text-rose-500 font-bold' }
  return { text: `▶ ${val.toFixed(2)}`, className: 'text-slate-400' }
}

// ── Session badge ──────────────────────────────────────────────────────────────

const SESSION_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  pre_market:   { bg: 'bg-sky-500/15',     text: 'text-sky-300',    dot: 'bg-sky-400'    },
  open:         { bg: 'bg-emerald-500/15', text: 'text-emerald-400', dot: 'bg-emerald-400' },
  after_hours:  { bg: 'bg-violet-500/15',  text: 'text-violet-300', dot: 'bg-violet-400' },
  closed:       { bg: 'bg-gray-700/40',    text: 'text-gray-500',   dot: 'bg-gray-600'   },
}

function SessionBadge({ session, label }: { session: string; label: string }) {
  const s = SESSION_STYLES[session] ?? SESSION_STYLES.closed
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${session === 'open' ? 'animate-pulse' : ''}`} />
      {label}
    </span>
  )
}

// ── Price change cell ─────────────────────────────────────────────────────────

function GapCell({ gap }: { gap: number }) {
  const color = gap >= 50 ? 'text-amber-400' : gap >= 20 ? 'text-emerald-400' : 'text-emerald-300'
  return (
    <td className="py-2.5 pr-4 text-right font-mono">
      <span className={`font-bold ${color}`}>+{gap.toFixed(1)}%</span>
    </td>
  )
}

// ── Price cell ────────────────────────────────────────────────────────────────

function PriceCell({ last, prev }: { last: number | null; prev: number | null }) {
  if (last == null) return <td className="py-2.5 pr-4 text-right font-mono text-gray-500">—</td>
  const up = prev == null || last >= prev
  return (
    <td className={`py-2.5 pr-4 text-right font-mono text-sm ${up ? 'text-white font-semibold' : 'text-red-400'}`}>
      ${last.toFixed(2)}
    </td>
  )
}

function Sparkline({ points, width = 64, height = 20 }: { points?: number[]; width?: number; height?: number }) {
  if (!points || points.length < 2) return <div style={{ width, height }} />
  
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min
  
  const padding = 2;
  
  const coords = points.map((p, idx) => {
    const x = (idx / (points.length - 1)) * (width - 2 * padding) + padding
    const y = range === 0 
      ? height / 2 
      : height - padding - ((p - min) / range) * (height - 2 * padding)
    return { x, y }
  })
  
  const pathD = coords.reduce((acc, c, idx) => {
    return acc + `${idx === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`
  }, '')
  
  const lastPoint = coords[coords.length - 1]
  const strokeColor = points[points.length - 1] >= points[0] ? '#10b981' : '#f43f5e'
  
  return (
    <svg width={width} height={height} className="overflow-visible inline-block">
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={lastPoint.x}
        cy={lastPoint.y}
        r="2"
        fill={strokeColor}
      />
    </svg>
  )
}

function SkeletonRows({ cols = 6 }: { cols?: number }) {
  return (
    <>
      {Array.from({ length: 10 }).map((_, i) => (
        <tr key={i} className="animate-pulse">
          {Array.from({ length: cols }).map((_, j) => (
            <td key={j} className="py-3 pr-4">
              <div className={`h-3 bg-gray-850 rounded ${j === 0 && cols === 6 ? 'w-8' : j === 1 ? 'w-16' : 'w-12'}`} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

// ── Reusable Gainer Table Component ───────────────────────────────────────────

interface GainerTableProps {
  gainers: LiveGainerRow[]
  fullList: LiveGainerRow[]
  title: string
  showRank?: boolean
  emptyMessage: string
  onOpenModal: (g: LiveGainerRow) => void
  handleResearch: (g: LiveGainerRow) => void
  loading?: boolean
  defaultSortKey?: 'rank' | 'ticker' | 'price' | 'change' | 'mom_2m' | 'atr_hod' | 'float'
  defaultSortDir?: 'asc' | 'desc'
  flashingTickers?: Record<string, boolean>
}

function GainerTable({
  gainers,
  fullList,
  title,
  showRank = true,
  emptyMessage,
  onOpenModal,
  handleResearch,
  loading = false,
  defaultSortKey = 'rank',
  defaultSortDir = 'asc',
  flashingTickers = {},
}: GainerTableProps) {
  const [lockedTicker, setLockedTicker] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<'rank' | 'ticker' | 'price' | 'change' | 'mom_2m' | 'atr_hod' | 'float'>(defaultSortKey)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(defaultSortDir)

  const handleRowClick = (ticker: string) => {
    setLockedTicker(prev => {
      if (prev === ticker) {
        return null
      }
      return ticker
    })
  }

  const handleSort = (key: typeof sortKey) => {
    if (sortKey === key) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  // Apply sorting
  const sortedGainers = [...gainers].sort((a, b) => {
    let valA: string | number = 0
    let valB: string | number = 0

    switch (sortKey) {
      case 'rank':
        valA = fullList.findIndex(x => x.ticker === a.ticker)
        valB = fullList.findIndex(x => x.ticker === b.ticker)
        break
      case 'ticker':
        valA = a.ticker
        valB = b.ticker
        break
      case 'price':
        valA = a.last_price ?? 0
        valB = b.last_price ?? 0
        break
      case 'change':
        valA = a.gap_pct ?? 0
        valB = b.gap_pct ?? 0
        break
      case 'mom_2m':
        valA = a.mom_2m ?? -9999
        valB = b.mom_2m ?? -9999
        break
      case 'atr_hod':
        valA = a.atr_hod ?? 9999
        valB = b.atr_hod ?? 9999
        break
      case 'float':
        valA = a.float_shares ?? 0
        valB = b.float_shares ?? 0
        break
    }

    if (valA < valB) return sortDir === 'asc' ? -1 : 1
    if (valA > valB) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  // Table header helper component to handle sorting UI
  const Th = ({ col, label, align = 'left', width }: { col: typeof sortKey; label: string; align?: 'left' | 'right' | 'center'; width?: string }) => {
    const isSorted = sortKey === col
    return (
      <th
        className={`pb-2 pr-4 font-semibold cursor-pointer select-none hover:text-white transition-colors group/th ${width || ''} ${
          align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'
        }`}
        onClick={() => handleSort(col)}
      >
        <div className={`inline-flex items-center gap-1 ${align === 'right' ? 'justify-end w-full' : align === 'center' ? 'justify-center w-full' : ''}`}>
          <span>{label}</span>
          <span className={`text-[10px] transition-opacity ${isSorted ? 'opacity-100 text-emerald-400' : 'opacity-0 group-hover/th:opacity-50'}`}>
            {isSorted ? (sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />) : <ChevronDown size={12} />}
          </span>
        </div>
      </th>
    )
  }

  const colSpanCount = showRank ? 7 : 6

  return (
    <div className="bg-[#0b0b0f]/30 dark:bg-gray-950/10 border border-gray-800/80 rounded-2xl p-5 shadow-sm space-y-4">
      <h3 className="text-xs font-bold text-gray-400 tracking-wider uppercase border-b border-gray-800/60 pb-3 flex items-center justify-between select-none">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          {title}
        </div>
        {!loading && (
          <span className="text-[10px] text-gray-500 font-mono font-semibold normal-case bg-gray-900/40 border border-gray-800/50 px-2.5 py-0.5 rounded-md">
            {gainers.length} Runners
          </span>
        )}
      </h3>

      <div className="overflow-x-auto overflow-y-hidden">
        <table className="w-full text-sm table-fixed min-w-[500px]">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
              {showRank && <Th col="rank" label="Rank" width="w-[8%]" />}
              <Th col="ticker" label="Ticker" width={showRank ? "w-[18%]" : "w-[24%]"} />
              <Th col="price" label="Price" align="right" width={showRank ? "w-[14%]" : "w-[16%]"} />
              <Th col="change" label="Change(%)" align="right" width={showRank ? "w-[14%]" : "w-[16%]"} />
              <Th col="mom_2m" label="Mom %" align="right" width={showRank ? "w-[14%]" : "w-[16%]"} />
              <Th col="atr_hod" label="AtrHoD" align="right" width={showRank ? "w-[14%]" : "w-[16%]"} />
              <Th col="float" label="Float" align="right" width={showRank ? "w-[18%]" : "w-[20%]"} />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/40">
            {loading ? (
              <SkeletonRows cols={colSpanCount} />
            ) : sortedGainers.length === 0 ? (
              <tr>
                <td colSpan={colSpanCount} className="py-10 text-center text-gray-600 text-xs">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              sortedGainers.map((g) => {
                const originalRank = fullList.findIndex(x => x.ticker === g.ticker) + 1
                const isExpanded = lockedTicker === g.ticker

                // Actionability Status Badge Calculations
                let playStatus = null
                const rvol = g.rvol_15m
                const mom = g.mom_2m
                if (rvol != null && mom != null) {
                  if (rvol >= 2.0 && mom >= 1.0) {
                    playStatus = { label: '🔥 Active In-Play', className: 'bg-orange-500/20 text-orange-400 border border-orange-500/35 animate-pulse' }
                  } else if (rvol >= 1.5 || mom >= 0.5) {
                    playStatus = { label: '⚡ Actionable', className: 'bg-amber-500/15 text-amber-300 border border-amber-500/25' }
                  } else if (mom < -1.5) {
                    playStatus = { label: '❄️ Fading', className: 'bg-rose-500/15 text-rose-355 border border-rose-500/25' }
                  } else {
                    playStatus = { label: '💤 Drifting / Cold', className: 'bg-gray-800/40 text-gray-400 border border-gray-800/60' }
                  }
                }

                let hodStatus = null
                const last = g.last_price
                const high = g.high_price
                if (last != null && high != null && high > 0) {
                  const pctOff = ((high - last) / high) * 100
                  if (pctOff <= 0.2) {
                    hodStatus = { label: '🎯 At HOD', className: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/35' }
                  } else if (pctOff <= 1.5) {
                    hodStatus = { label: `🎯 Near HOD (${pctOff.toFixed(1)}% off)`, className: 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' }
                  } else if (pctOff <= 5.0) {
                    hodStatus = { label: `📈 Pullback (${pctOff.toFixed(1)}% off)`, className: 'bg-amber-500/10 text-amber-300 border border-amber-500/20' }
                  } else {
                    hodStatus = { label: `⚠️ Off HOD (${pctOff.toFixed(1)}% off)`, className: 'bg-rose-500/15 text-rose-300 border border-rose-500/25' }
                  }
                }

                let vwapStatus = null
                const atrVwap = g.atr_vwap
                if (atrVwap != null) {
                  const absAtr = Math.abs(atrVwap)
                  if (absAtr <= 0.4) {
                    vwapStatus = { label: '⚡ Nearing VWAP Cross', className: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/35 animate-pulse' }
                  } else if (atrVwap > 0) {
                    vwapStatus = { label: `📈 Above VWAP (+${atrVwap.toFixed(1)} ATR)`, className: 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' }
                  } else {
                    vwapStatus = { label: `📉 Below VWAP (${atrVwap.toFixed(1)} ATR)`, className: 'bg-rose-500/10 text-rose-300 border border-rose-500/20' }
                  }
                }

                let consolStatus = null
                const zen = g.zen_v
                if (zen != null && mom != null) {
                  if (Math.abs(zen) <= 0.25 && Math.abs(mom) <= 0.5) {
                    consolStatus = { label: '⏳ Consolidating', className: 'bg-blue-500/20 text-blue-300 border border-blue-500/35' }
                  } else if (zen > 0.25 && mom > 0.5) {
                    consolStatus = { label: '🚀 Breaking Out', className: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/35' }
                  } else if (zen < -0.25 && mom < -0.5) {
                    consolStatus = { label: '📉 Breaking Down', className: 'bg-rose-500/20 text-rose-300 border border-rose-500/35' }
                  } else {
                    consolStatus = { label: '📊 Trending', className: 'bg-gray-800/40 text-gray-300 border border-gray-800/60' }
                  }
                }

                const isFlashing = !!flashingTickers[g.ticker]
                return (
                  <Fragment key={g.ticker}>
                    <tr
                      key={g.ticker}
                      style={
                        isFlashing
                          ? { backgroundColor: 'rgba(245, 158, 11, 0.3)', transition: 'none' }
                          : { transition: 'background-color 3.5s cubic-bezier(0.25, 1, 0.5, 1)' }
                      }
                      className={`hover:bg-gray-850/40 transition-colors group cursor-pointer ${
                        isExpanded ? 'bg-gray-850/20' : ''
                      }`}
                      onClick={() => handleRowClick(g.ticker)}
                    >
                      {/* 1. Rank */}
                      {showRank && (
                        <td className="py-2.5 pr-4 font-bold text-gray-500 text-xs w-12 pl-1 select-none">
                          {originalRank}
                        </td>
                      )}

                      {/* 2. Ticker with standard badging & custom tooltip */}
                      <td className="py-2.5 pr-4">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white group-hover:text-emerald-400 transition-colors font-mono flex items-center gap-1.5">
                            {g.ticker}
                          </span>
                          <div className="flex items-center gap-0.5 shrink-0 select-none">
                            {lockedTicker === g.ticker && (
                              <span className="relative group/tooltip inline-flex items-center p-0.5 rounded text-[8px] font-black bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                                <Pin size={8} className="fill-current" />
                                <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/tooltip:block bg-gray-950 border border-gray-800 text-white text-[10px] font-medium py-1 px-2 rounded shadow-2xl whitespace-nowrap z-50">
                                  Pinned open (Click to toggle)
                                  <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-950" />
                                </span>
                              </span>
                            )}
                            {g.is_repeat_runner && (
                              <span className="relative group/tooltip inline-flex items-center px-1 py-0.25 rounded text-[8px] font-black bg-amber-500/20 text-amber-400 border border-amber-500/30">
                                RR
                                <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/tooltip:block bg-gray-950 border border-gray-800 text-white text-[10px] font-medium py-1 px-2 rounded shadow-2xl whitespace-nowrap z-50">
                                  RR = Recent Runner (24h)
                                  <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-950" />
                                </span>
                              </span>
                            )}
                            {g.is_follow_through && (
                              <span className="relative group/tooltip inline-flex items-center px-1 py-0.25 rounded text-[8px] font-black bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                FT
                                <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/tooltip:block bg-gray-950 border border-gray-800 text-white text-[10px] font-medium py-1 px-2 rounded shadow-2xl whitespace-nowrap z-50">
                                  FT = Fast Trade (24h)
                                  <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-950" />
                                </span>
                              </span>
                            )}
                            {g.is_hod && (
                              <span className="relative group/tooltip inline-flex items-center px-1 py-0.25 rounded text-[8px] font-black bg-rose-500/20 text-rose-350 border border-rose-500/30">
                                HOD
                                <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/tooltip:block bg-gray-950 border border-gray-800 text-white text-[10px] font-medium py-1 px-2 rounded shadow-2xl whitespace-nowrap z-50">
                                  HOD = High of Day
                                  <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-950" />
                                </span>
                              </span>
                            )}
                            {g.catalyst === 'Technical / No News' && (
                              <span className="relative group/tooltip inline-flex items-center px-1 py-0.25 rounded text-[8px] font-black bg-orange-500/20 text-orange-400 border border-orange-500/30">
                                ⚠️ NNP
                                <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/tooltip:block bg-gray-950 border border-gray-800 text-white text-[10px] font-medium py-1 px-2 rounded shadow-2xl whitespace-nowrap z-50">
                                  No-News Pump — speculative volatility, no fundamental catalyst
                                  <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-950" />
                                </span>
                              </span>
                            )}
                            {g.catalyst === 'Speculative' && (
                              <span className="relative group/tooltip inline-flex items-center px-1 py-0.25 rounded text-[8px] font-black bg-gray-500/20 text-gray-400 border border-gray-500/30">
                                ? SPEC
                                <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/tooltip:block bg-gray-950 border border-gray-800 text-white text-[10px] font-medium py-1 px-2 rounded shadow-2xl whitespace-nowrap z-50">
                                  Speculative — low/unknown RVOL, no confirmed catalyst
                                  <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-950" />
                                </span>
                              </span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* 3. Price */}
                      <PriceCell last={g.last_price} prev={g.prev_close} />

                      {/* 4. Change (%) */}
                      <GapCell gap={g.gap_pct} />

                      {/* 5. Mom % */}
                      <td className="py-2.5 pr-4 text-right font-mono select-none animate-in fade-in duration-200">
                        <span className={`font-bold transition-all duration-300 ${getMomStyle(g.mom_2m)}`}>
                          {g.mom_2m != null ? (g.mom_2m >= 0 ? `+${g.mom_2m.toFixed(2)}%` : `${g.mom_2m.toFixed(2)}%`) : '—'}
                        </span>
                      </td>

                      {/* 6. AtrHoD */}
                      <td className="py-2.5 pr-4 text-right font-mono select-none animate-in fade-in duration-200">
                        <span className={`font-semibold ${getAtrHodColor(g.atr_hod)}`}>
                          {g.atr_hod != null ? g.atr_hod.toFixed(2) : '—'}
                        </span>
                      </td>

                      {/* 7. Float */}
                      <td className="py-2.5 pr-4 text-right animate-in fade-in duration-200">
                        <span className={`inline-flex whitespace-nowrap px-2 py-0.5 rounded text-[11px] font-mono font-bold ${getFloatBadgeStyle(g.float_shares).className}`}>
                          {getFloatBadgeStyle(g.float_shares).label}
                        </span>
                      </td>
                    </tr>

                    {/* Expandable details row */}
                    <tr 
                      key={`${g.ticker}-expand`} 
                      className={`bg-gray-900/10`}
                    >
                      <td colSpan={colSpanCount} className="p-0 border-0">
                        <div
                          className={`grid transition-all duration-300 ease-in-out ${
                            isExpanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
                          }`}
                        >
                          <div className="overflow-hidden">
                             <div className="py-4 px-6 border-t border-gray-800/40 bg-gray-950/20 space-y-4">
                               {/* ⚡ Actionability & Technical Status Dashboard */}
                               <div className="flex flex-wrap gap-2 select-none border-b border-gray-800/35 pb-3">
                                 {playStatus && (
                                   <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-bold border ${playStatus.className}`}>
                                     {playStatus.label}
                                   </span>
                                 )}
                                 {consolStatus && (
                                   <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-bold border ${consolStatus.className}`}>
                                     {consolStatus.label}
                                   </span>
                                 )}
                                 {vwapStatus && (
                                   <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-bold border ${vwapStatus.className}`}>
                                     {vwapStatus.label}
                                   </span>
                                 )}
                                 {hodStatus && (
                                   <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-bold border ${hodStatus.className}`}>
                                     {hodStatus.label}
                                   </span>
                                 )}
                               </div>

                               <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm text-gray-300">
                                 {/* Left Column: Detailed Metrics */}
                                 <div className="space-y-3">
                                   <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider select-none">Secondary Metrics</h4>
                                   <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 font-mono text-xs">
                                     <span className="text-gray-500">Volume:</span>
                                     <span className="text-white font-semibold">{fmtVol(g.volume)}</span>

                                     <MetricLabelWithTooltip
                                       label="RVOL (15m):"
                                       tooltip="Relative Volume over the last 15 minutes compared to historical average. Higher values indicate unusual/strong activity."
                                     />
                                     <div>
                                       <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] ${getRvolBadgeStyle(g.rvol_15m).className}`}>
                                         {getRvolBadgeStyle(g.rvol_15m).label}
                                       </span>
                                     </div>

                                     <MetricLabelWithTooltip
                                       label="Spread %:"
                                       tooltip="The bid-ask spread as a percentage of the last price. Lower spread (<1%) implies better liquidity."
                                     />
                                     <div>
                                       <span className={getSpreadBadgeStyle(g.spread_pct).className}>
                                         {getSpreadBadgeStyle(g.spread_pct).label}
                                       </span>
                                     </div>

                                     <span className="text-gray-500">Trade Time:</span>
                                     <div className="flex flex-col gap-0.5 text-gray-400">
                                       <span>
                                         {g.trade_time
                                           ? new Date(g.trade_time).toLocaleTimeString('en-US', {
                                               timeZone: 'America/New_York',
                                               hour12: false,
                                             })
                                           : '—'} EST
                                       </span>
                                       {g.trade_time && (
                                         <div>
                                           <span className={`inline-flex px-1 py-0.25 rounded text-[9px] ${getTimeAgoBadge(g.trade_time)?.className}`}>
                                             {getTimeAgoBadge(g.trade_time)?.label}
                                           </span>
                                         </div>
                                       )}
                                     </div>
                                   </div>
                                 </div>

                                 {/* Middle Column: Volatility & Relative Level */}
                                 <div className="space-y-3">
                                   <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider select-none">Volatility & Relative Level</h4>
                                   <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 font-mono text-xs">
                                     <MetricLabelWithTooltip
                                       label="ATR Spread:"
                                       tooltip="The current bid-ask spread divided by the 14-period Average True Range. Measures relative cost to cross the spread."
                                     />
                                     <div>
                                       <span className={getAtrSpreadStyle(g.atr_sprd).className}>
                                         {getAtrSpreadStyle(g.atr_sprd).text}
                                       </span>
                                     </div>

                                     <MetricLabelWithTooltip
                                       label="ATR VWAP:"
                                       tooltip="Distance from the Volume Weighted Average Price in ATR units. Near 0 indicates a reversion/consolidation test."
                                     />
                                     <div>
                                       <span className={getAtrVwapStyle(g.atr_vwap).className}>
                                         {getAtrVwapStyle(g.atr_vwap).text}
                                       </span>
                                     </div>

                                     <MetricLabelWithTooltip
                                       label="ZenV (Slope):"
                                       tooltip="The 2-minute slope of volume acceleration. Positive (▲) values indicate escalating buyer urgency."
                                     />
                                     <div>
                                       <span className={getZenVStyle(g.zen_v).className}>
                                         {getZenVStyle(g.zen_v).text}
                                       </span>
                                     </div>

                                     <span className="text-gray-500">Sector:</span>
                                     <span className="text-white font-semibold font-sans">{g.sector ?? '—'}</span>
                                   </div>
                                 </div>

                                {/* Right Column: Trend Sparkline & Actions */}
                                <div className="flex flex-col justify-between gap-4">
                                  {(g.sparkline_intraday && g.sparkline_intraday.length > 0) || (g.sparkline_5d && g.sparkline_5d.length > 0) ? (
                                    <div className="space-y-1.5">
                                      <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider select-none block">
                                        {g.sparkline_intraday && g.sparkline_intraday.length > 0 ? 'Intraday Trend:' : '5d Trend Sparkline:'}
                                      </span>
                                      <div className="bg-[#0b0b0f] p-2 rounded border border-gray-800/80 inline-block shadow-inner">
                                        <Sparkline 
                                          points={g.sparkline_intraday && g.sparkline_intraday.length > 0 ? g.sparkline_intraday : g.sparkline_5d} 
                                          width={100}
                                          height={28}
                                        />
                                      </div>
                                    </div>
                                  ) : (
                                    <div />
                                  )}
                                  <div className="flex flex-row md:flex-col justify-end gap-3 select-none w-full">
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        onOpenModal(g);
                                      }}
                                      className="flex-1 md:flex-initial flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 border border-emerald-500/20 rounded-lg shadow transition-colors"
                                    >
                                      <Maximize2 size={12} />
                                      Open Detailed View
                                    </button>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleResearch(g);
                                      }}
                                      className="flex-1 md:flex-initial flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-300 hover:text-white bg-gray-850 hover:bg-gray-850 border border-gray-700 rounded-lg transition-colors"
                                    >
                                      <ExternalLink size={12} />
                                      Research Ticker
                                    </button>
                                  </div>
                                </div>
                              </div>

                              {/* Headline Footer */}
                              <div className="mt-4 pt-3 border-t border-gray-800/50 flex items-start gap-2 text-xs">
                                <span className="text-gray-500 font-bold uppercase select-none shrink-0 mt-0.5">Headline:</span>
                                {g.catalyst === 'Technical / No News' ? (
                                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-bold bg-orange-500/15 text-orange-300 border border-orange-500/30">
                                    ⚠️ Speculative Volatility / No News
                                    <span className="text-orange-400/70 font-normal text-[10px]">
                                      — High RVOL, no fundamental catalyst detected in last 24h
                                    </span>
                                  </span>
                                ) : g.catalyst === 'Speculative' ? (
                                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-gray-700/30 text-gray-400 border border-gray-600/30">
                                    ? Unconfirmed Momentum
                                    <span className="text-gray-500 font-normal text-[10px]">
                                      — Low or unknown RVOL, no news confirmed
                                    </span>
                                  </span>
                                ) : g.catalyst === 'Confirmed Catalyst' && g.news_headline ? (
                                  <span className="text-gray-300 italic leading-relaxed block max-w-2xl">{g.news_headline}</span>
                                ) : (
                                  <span className="text-gray-500 italic">No recent news</span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  </Fragment>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface AlertItem {
  id: string
  ticker: string
  price: number
  alertType: string
  time: string
  volume?: number
  rvol?: number
  gapPct?: number
  floatShares?: number
}

export default function LiveGainers() {
  const router = useRouter()
  const [snap,        setSnap]        = useState<LiveGainerSnapshot | null>(null)
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState<string | null>(null)
  const [refreshing,  setRefreshing]  = useState(false)
  const [ageStr,      setAgeStr]      = useState('')
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Real-Time Breakout Alerts & Notifications (Phase 3)
  const [audioChimesEnabled, setAudioChimesEnabled] = useState(false)
  const [toastStackEnabled, setToastStackEnabled] = useState(true)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [recentAlerts, setRecentAlerts] = useState<AlertItem[]>([])
  const [flashingTickers, setFlashingTickers] = useState<Record<string, boolean>>({})
  const [toasts, setToasts] = useState<AlertItem[]>([])

  const audioChimesEnabledRef = useRef(audioChimesEnabled)
  const toastStackEnabledRef = useRef(toastStackEnabled)
  const audioCtxRef = useRef<AudioContext | null>(null)

  useEffect(() => {
    audioChimesEnabledRef.current = audioChimesEnabled
  }, [audioChimesEnabled])

  useEffect(() => {
    toastStackEnabledRef.current = toastStackEnabled
  }, [toastStackEnabled])

  const playPlinkChime = useCallback(() => {
    try {
      if (typeof window === 'undefined') return
      if (!audioCtxRef.current) {
        const AudioContextClass = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
        if (!AudioContextClass) return
        audioCtxRef.current = new AudioContextClass()
      }
      const ctx = audioCtxRef.current
      if (ctx.state === 'suspended') {
        ctx.resume()
      }
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.type = 'sine'
      const now = ctx.currentTime
      osc.frequency.setValueAtTime(800, now)
      osc.frequency.exponentialRampToValueAtTime(1200, now + 0.08)
      gain.gain.setValueAtTime(0.12, now)
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3)
      osc.start(now)
      osc.stop(now + 0.32)
    } catch (e) {
      console.error('Web Audio error:', e)
    }
  }, [])

  // SSE connection for real-time alerts
  useEffect(() => {
    const eventSource = new EventSource('/api/alerts/stream')

    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        const ticker = payload.symbol
        const price = payload.price
        const alertType = payload.alert_type

        // Play chime if enabled
        if (audioChimesEnabledRef.current) {
          playPlinkChime()
        }

        // Render toast if enabled
        if (toastStackEnabledRef.current) {
          const id = Math.random().toString(36).substring(2, 9)
          const newToast: AlertItem = {
            id,
            ticker,
            price,
            alertType,
            time: new Date().toLocaleTimeString(),
          }
          setToasts(prev => [newToast, ...prev].slice(0, 5))
          setTimeout(() => {
            setToasts(prev => prev.filter(t => t.id !== id))
          }, 6000)
        }

        // Recent alerts list (cap at 50)
        const recentAlertItem: AlertItem = {
          id: Math.random().toString(36).substring(2, 9),
          ticker,
          price,
          alertType,
          time: new Date().toLocaleTimeString(),
          volume: payload.volume,
          rvol: payload.rvol,
          gapPct: payload.gap_pct,
          floatShares: payload.float_shares
        }
        setRecentAlerts(prev => [recentAlertItem, ...prev].slice(0, 50))

        // Trigger flash effect for the ticker
        setFlashingTickers(prev => ({ ...prev, [ticker]: true }))
        setTimeout(() => {
          setFlashingTickers(prev => ({ ...prev, [ticker]: false }))
        }, 200)

      } catch (err) {
        console.error('Failed to process SSE message:', err)
      }
    }

    eventSource.onerror = (err) => {
      console.error('SSE Stream Error:', err)
    }

    return () => {
      eventSource.close()
    }
  }, [playPlinkChime])

  // UX states
  const [modalGainer, setModalGainer]       = useState<LiveGainerRow | null>(null)
  const [watchlist, setWatchlist]           = useState<WatchlistItem[]>([])
  const [notesText, setNotesText]           = useState('')
  const [savingNotes, setSavingNotes]       = useState(false)
  const [watchlistLoading, setWatchlistLoading] = useState(false)
  const [priceFilterEnabled, setPriceFilterEnabled] = useState(true)

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


  const fetchData = useCallback(async (force = false) => {
    try {
      if (force) setRefreshing(true)
      const data = await getLiveGainers(force)
      setSnap(data)
      setError(null)
    } catch (e: unknown) {
      setError((e as Error)?.message ?? 'Failed to load live data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  const fetchWatchlist = useCallback(async () => {
    try {
      const items = await getWatchlist()
      setWatchlist(items)
    } catch (e) {
      console.error('Failed to load watchlist', e)
    }
  }, [])

  // Initial load + polling
  useEffect(() => {
    fetchData()
    fetchWatchlist()
    // Poll every 1 minute — matches the backend cache TTL
    timerRef.current = setInterval(() => fetchData(), 60 * 1000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [fetchData, fetchWatchlist])

  // Live "X ago" counter (updates every 10s)
  useEffect(() => {
    const tick = () => setAgeStr(snap?.fetched_at ? fmtAge(snap.fetched_at) : '')
    tick()
    const id = setInterval(tick, 10_000)
    return () => clearInterval(id)
  }, [snap?.fetched_at])

  // Sync watchlist notes when modal ticker changes
  useEffect(() => {
    if (modalGainer) {
      const item = watchlist.find(w => w.ticker === modalGainer.ticker)
      setNotesText(item?.notes ?? '')
    }
  }, [modalGainer, watchlist])

  // Prevent background body scroll when detailed view modal is open
  useEffect(() => {
    if (modalGainer) {
      document.body.classList.add('overflow-hidden')
    } else {
      document.body.classList.remove('overflow-hidden')
    }
    return () => {
      document.body.classList.remove('overflow-hidden')
    }
  }, [modalGainer])

  const handleResearch = (g: LiveGainerRow) => {
    const today = new Date().toISOString().slice(0, 10)
    router.push(`/research?ticker=${g.ticker}&date=${today}`)
  }

  const handleToggleWatchlist = async () => {
    if (!modalGainer) return
    setWatchlistLoading(true)
    try {
      const item = watchlist.find(w => w.ticker === modalGainer.ticker)
      if (item) {
        await removeFromWatchlist(modalGainer.ticker)
      } else {
        await addToWatchlist({
          ticker: modalGainer.ticker,
          sector: modalGainer.sector || undefined
        })
      }
      await fetchWatchlist()
    } catch {
      alert('Failed to update watchlist')
    } finally {
      setWatchlistLoading(false)
    }
  }

  const handleSaveNotes = async () => {
    if (!modalGainer) return
    setSavingNotes(true)
    try {
      await updateWatchlistItem(modalGainer.ticker, { notes: notesText })
      await fetchWatchlist()
    } catch {
      alert('Failed to save notes')
    } finally {
      setSavingNotes(false)
    }
  }

  const session    = snap?.session ?? 'closed'
  const isActive   = session !== 'closed'

  const filteredGainers = useMemo(() => {
    const list = snap?.gainers ?? []
    if (!priceFilterEnabled) return list
    return list.filter(g => {
      const p = g.last_price
      return p != null && p >= 2.0 && p <= 25.0
    })
  }, [snap, priceFilterEnabled])

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          {snap && (
            <SessionBadge session={session} label={snap.session_label} />
          )}
          {ageStr && (
            <span className="flex items-center gap-1 text-[11px] text-gray-600">
              <Clock size={10} />
              {ageStr}
            </span>
          )}
          {isActive && !error && (
            <span className="flex items-center gap-1 text-[11px] text-gray-700">
              <Wifi size={10} className="text-emerald-600" />
              auto-refresh 1m
            </span>
          )}
          {error && (
            <span className="flex items-center gap-1 text-[11px] text-red-500">
              <WifiOff size={10} />
              {error}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 select-none">
          {/* Audio Chime Toggle */}
          <button
            onClick={() => setAudioChimesEnabled(!audioChimesEnabled)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              audioChimesEnabled
                ? 'bg-emerald-600/15 border-emerald-500/35 text-emerald-400 hover:bg-emerald-600/25'
                : 'bg-gray-900/40 border-gray-800/60 text-gray-450 hover:text-gray-300 hover:bg-gray-900/60'
            }`}
            title="Toggle Audio Chimes on Breakouts"
          >
            {audioChimesEnabled ? <Volume2 size={12} /> : <VolumeX size={12} />}
            <span>Audio</span>
          </button>

          {/* Toast Stack Toggle */}
          <button
            onClick={() => setToastStackEnabled(!toastStackEnabled)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              toastStackEnabled
                ? 'bg-emerald-600/15 border-emerald-500/35 text-emerald-400 hover:bg-emerald-600/25'
                : 'bg-gray-900/40 border-gray-800/60 text-gray-450 hover:text-gray-300 hover:bg-gray-900/60'
            }`}
            title="Toggle Toast Stack Notifications"
          >
            {toastStackEnabled ? <Bell size={12} /> : <BellOff size={12} />}
            <span>Toasts</span>
          </button>

          <button
            onClick={() => {
              const newValue = !priceFilterEnabled
              setPriceFilterEnabled(newValue)
              localStorage.setItem('price-filter-enabled', String(newValue))
              window.dispatchEvent(new Event('price-filter-changed'))
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              priceFilterEnabled
                ? 'bg-emerald-600/15 border-emerald-500/35 text-emerald-400 hover:bg-emerald-600/25'
                : 'bg-gray-900/40 border-gray-800/60 text-gray-450 hover:text-gray-300 hover:bg-gray-900/60'
            }`}
          >
            <span>$2-$25 Filter</span>
            {priceFilterEnabled ? (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            ) : (
              <span className="w-1.5 h-1.5 rounded-full bg-gray-600" />
            )}
          </button>

          <button
            id="live-gainers-refresh"
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-emerald-400 transition-colors disabled:opacity-40"
          >
            <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* EOD persist notice */}
      {session === 'after_hours' && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-xs text-violet-300">
          <TrendingUp size={12} className="shrink-0" />
          These gainers will be automatically saved to your database at 8:00 PM ET.
        </div>
      )}

      {/* Side-by-Side Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GainerTable
          gainers={loading ? [] : filteredGainers}
          fullList={loading ? [] : filteredGainers}
          title="All Live Gainers"
          showRank={true}
          emptyMessage={
            session === 'closed'
              ? 'Market is closed. Check back during pre-market (4 AM ET) or regular hours.'
              : 'No gainers meeting criteria right now.'
          }
          onOpenModal={setModalGainer}
          handleResearch={handleResearch}
          loading={loading}
          flashingTickers={flashingTickers}
        />
        <GainerTable
          gainers={loading ? [] : filteredGainers.filter(g => g.atr_hod != null && g.atr_hod < 1.0)}
          fullList={loading ? [] : filteredGainers}
          title="Near HOD Radar"
          showRank={false}
          emptyMessage="No Near HOD breakout setups coiling right now (AtrHoD < 1.0)."
          onOpenModal={setModalGainer}
          handleResearch={handleResearch}
          loading={loading}
          defaultSortKey="atr_hod"
          defaultSortDir="asc"
          flashingTickers={flashingTickers}
        />
      </div>

      {/* Footer — last DB ingest */}
      <div className="pt-2 border-t border-gray-800/60">
        <LastIngestRow />
      </div>

      {/* Details modal overlay */}
      {modalGainer && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
          onClick={() => setModalGainer(null)}
        >
          <div 
            className="w-full max-w-3xl bg-[#0c0c12] border border-gray-850 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[95vh] animate-in fade-in zoom-in duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800/80">
              <div className="flex items-center gap-3">
                <span className="text-xl font-bold text-white font-mono">{modalGainer.ticker}</span>
                <div className="flex items-center gap-1">
                  {modalGainer.is_repeat_runner && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-black bg-amber-500/20 text-amber-400 border border-amber-500/30">
                      RR
                    </span>
                  )}
                  {modalGainer.is_follow_through && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-black bg-blue-500/20 text-blue-400 border border-blue-500/30">
                      FT
                    </span>
                  )}
                  {modalGainer.is_hod && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-black bg-rose-500/20 text-rose-300 border border-rose-500/30">
                      HOD
                    </span>
                  )}
                </div>
              </div>
              <button 
                onClick={() => setModalGainer(null)}
                className="text-gray-400 hover:text-white p-1 hover:bg-gray-800 rounded-lg transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Scrollable Body */}
            <div className="p-6 overflow-y-auto space-y-6">
              {/* Interactive Chart */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1 select-none">
                    <Sparkles size={12} className="text-emerald-400" />
                    Interactive Session Chart
                  </h4>
                  <span className="text-[10px] text-gray-500 select-none">Drag to scroll · Scroll to zoom</span>
                </div>
                <div className="min-h-[220px]">
                  <MiniSessionChart 
                    ticker={modalGainer.ticker}
                    date={new Date().toISOString().slice(0, 10)}
                    gapPct={modalGainer.gap_pct}
                    float={modalGainer.float_shares}
                    rvol={modalGainer.rvol_15m}
                    onExpand={(ticker) => {
                      const today = new Date().toISOString().slice(0, 10);
                      router.push(`/research?ticker=${ticker}&date=${today}`);
                      setModalGainer(null);
                    }}
                  />
                </div>
              </div>

              {/* Watchlist & Notes Section */}
              <div className="p-4 rounded-xl bg-gray-900/35 border border-gray-850 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 select-none">
                    <h4 className="text-sm font-semibold text-white">Watchlist Quick Access</h4>
                    {watchlistLoading && <span className="text-xs text-gray-500 animate-pulse">Syncing...</span>}
                  </div>
                  
                  <button
                    onClick={handleToggleWatchlist}
                    disabled={watchlistLoading}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                      watchlist.some(w => w.ticker === modalGainer.ticker)
                        ? 'bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20'
                        : 'bg-gray-800 text-gray-300 border-gray-700 hover:bg-gray-750 hover:text-white'
                    }`}
                  >
                    {watchlist.some(w => w.ticker === modalGainer.ticker) ? (
                      <>
                        <BookmarkCheck size={13} className="text-amber-400" />
                        In Watchlist
                      </>
                    ) : (
                      <>
                        <Bookmark size={13} />
                        Add to Watchlist
                      </>
                    )}
                  </button>
                </div>

                {watchlist.some(w => w.ticker === modalGainer.ticker) && (
                  <div className="space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
                    <label className="text-xs font-medium text-gray-400 block select-none">Watchlist Notes</label>
                    <textarea
                      value={notesText}
                      onChange={(e) => setNotesText(e.target.value)}
                      placeholder="Type watchlist notes for this runner..."
                      className="w-full h-24 bg-[#08080c] border border-gray-800/80 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-emerald-500/50 resize-none font-sans"
                    />
                    <div className="flex justify-end select-none">
                      <button
                        onClick={handleSaveNotes}
                        disabled={savingNotes}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-600/50 text-white font-semibold text-xs rounded-md shadow transition-colors flex items-center gap-1"
                      >
                        {savingNotes ? 'Saving...' : 'Save Notes'}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Full Details Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono text-xs">
                <div className="p-3 bg-gray-900/15 border border-gray-850 rounded-xl space-y-1">
                  <span className="text-gray-500 block text-[10px] uppercase tracking-wider font-sans font-semibold">Price</span>
                  <span className="text-sm font-bold text-white">${modalGainer.last_price?.toFixed(2) ?? '—'}</span>
                </div>
                <div className="p-3 bg-gray-900/15 border border-gray-850 rounded-xl space-y-1">
                  <span className="text-gray-500 block text-[10px] uppercase tracking-wider font-sans font-semibold">Change %</span>
                  <span className={`text-sm font-bold ${modalGainer.gap_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    +{modalGainer.gap_pct?.toFixed(1)}%
                  </span>
                </div>
                <div className="p-3 bg-gray-900/15 border border-gray-850 rounded-xl space-y-1">
                  <span className="text-gray-500 block text-[10px] uppercase tracking-wider font-sans font-semibold">Float Shares</span>
                  <div>
                    <span className={`inline-flex whitespace-nowrap px-1.5 py-0.5 rounded text-[10px] font-bold ${getFloatBadgeStyle(modalGainer.float_shares).className}`}>
                      {getFloatBadgeStyle(modalGainer.float_shares).label}
                    </span>
                  </div>
                </div>
                <div className="p-3 bg-gray-900/15 border border-gray-850 rounded-xl space-y-1">
                  <span className="text-gray-500 block text-[10px] uppercase tracking-wider font-sans font-semibold">RVOL (15m)</span>
                  <div>
                    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] ${getRvolBadgeStyle(modalGainer.rvol_15m).className}`}>
                      {getRvolBadgeStyle(modalGainer.rvol_15m).label}
                    </span>
                  </div>
                </div>
                <div className="p-3 bg-gray-900/15 border border-gray-850 rounded-xl space-y-1">
                  <span className="text-gray-500 block text-[10px] uppercase tracking-wider font-sans font-semibold">Volume</span>
                  <span className="text-sm font-bold text-white">{fmtVol(modalGainer.volume)}</span>
                </div>
                <div className="p-3 bg-gray-900/15 border border-gray-850 rounded-xl space-y-1">
                  <span className="text-gray-500 block text-[10px] uppercase tracking-wider font-sans font-semibold">Spread %</span>
                  <div>
                    <span className={getSpreadBadgeStyle(modalGainer.spread_pct).className}>
                      {getSpreadBadgeStyle(modalGainer.spread_pct).label}
                    </span>
                  </div>
                </div>
                <div className="p-3 bg-gray-900/15 border border-gray-850 rounded-xl space-y-1">
                  <span className="text-gray-500 block text-[10px] uppercase tracking-wider font-sans font-semibold">Sector</span>
                  <span className="text-xs text-white truncate block">{modalGainer.sector ?? '—'}</span>
                </div>
                <div className="p-3 bg-gray-900/15 border border-gray-850 rounded-xl space-y-1">
                  <span className="text-gray-500 block text-[10px] uppercase tracking-wider font-sans font-semibold">Last Trade</span>
                  <span className="text-xs text-white block">
                    {modalGainer.trade_time
                      ? new Date(modalGainer.trade_time).toLocaleTimeString('en-US', {
                          timeZone: 'America/New_York',
                          hour12: false,
                        })
                      : '—'} EST
                  </span>
                </div>
              </div>
            </div>
            
            {/* Modal Footer */}
            <div className="px-6 py-4 bg-gray-950 border-t border-gray-850/80 flex justify-between items-center select-none">
              <span className="text-[10px] text-gray-650">ID: {modalGainer.ticker}</span>
              <button
                onClick={() => {
                  const today = new Date().toISOString().slice(0, 10);
                  router.push(`/research?ticker=${modalGainer.ticker}&date=${today}`);
                  setModalGainer(null);
                }}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg shadow-md transition-colors"
              >
                <ExternalLink size={12} />
                Go to Research Page
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast notifications stack */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-3 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="pointer-events-auto bg-[#0b0b0f] border border-gray-800 rounded-xl p-4 shadow-2xl flex flex-col gap-2 hover:border-emerald-500/50 transition-all cursor-pointer transform hover:scale-[1.02] active:scale-[0.98] animate-in slide-in-from-bottom duration-200"
            onClick={() => {
              const today = new Date().toISOString().slice(0, 10)
              router.push(`/research?ticker=${toast.ticker}&date=${today}`)
              setToasts(prev => prev.filter(t => t.id !== toast.id))
            }}
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-white font-mono flex items-center gap-1.5 text-sm">
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                {toast.ticker}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setToasts(prev => prev.filter(t => t.id !== toast.id))
                }}
                className="text-gray-500 hover:text-white transition-colors p-0.5"
              >
                <X size={14} />
              </button>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-400">
                Trigger: <span className="font-mono text-white font-semibold">${toast.price.toFixed(2)}</span>
              </span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                {toast.alertType}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Last DB ingest sub-row ─────────────────────────────────────────────────────

function LastIngestRow() {
  const [summary, setSummary] = useState<{ date: string | null; total: number } | null>(null)

  useEffect(() => {
    import('@/lib/api').then(({ getGainersSummary }) =>
      getGainersSummary()
        .then(s => setSummary({ date: s.date, total: s.total }))
        .catch(() => {})
    )
  }, [])

  if (!summary?.date) return null

  const dateLabel = new Date(summary.date + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
  })

  return (
    <div className="flex items-center justify-between text-[11px] text-gray-600">
      <span>
        Last ingested: <span className="text-gray-500">{dateLabel}</span>
        <span className="ml-2 text-gray-700">({summary.total} tickers)</span>
      </span>
      <a href="/history" className="hover:text-emerald-400 transition-colors">
        Command Center →
      </a>
    </div>
  )
}
