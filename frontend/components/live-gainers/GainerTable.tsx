'use client'

import { useState, Fragment, useEffect, useRef } from 'react'
import { LiveGainerRow } from '@/lib/api'
import { Sparkline } from '@/components/Sparkline'
import { fmtVol } from '@/lib/format'
import { ChevronDown, ChevronUp, Maximize2, ExternalLink, Pin, Info } from 'lucide-react'
import {
  getRvolBadgeStyle, getSpreadBadgeStyle,
  getAtrSpreadStyle, getAtrVwapStyle, getZenVStyle,
  getTimeAgoBadge, getTrendIndicator,
} from './styles'
import {
  GapCell, PriceCell, MetricLabelWithTooltip, SkeletonRows, FloatCellInline,
} from './badges'

// ── Sort header helper ──────────────────────────────────────────────────────

type SortKey = 'rank' | 'ticker' | 'price' | 'change' | 'mom_2m' | 'atr_hod' | 'float' | 'rvol' | 'hod' | 'trend'

interface GainerTableProps {
  gainers:         LiveGainerRow[]
  fullList:        LiveGainerRow[]
  title:           string
  emptyMessage:    string
  onOpenModal:     (g: LiveGainerRow) => void
  handleResearch:  (g: LiveGainerRow) => void
  loading?:        boolean
  defaultSortKey?: SortKey
  defaultSortDir?: 'asc' | 'desc'
  flashingTickers?: Record<string, boolean>
}

export function GainerTable({
  gainers,
  fullList,
  title,
  emptyMessage,
  onOpenModal,
  handleResearch,
  loading = false,
  defaultSortKey = 'rank',
  defaultSortDir = 'asc',
  flashingTickers = {},
}: GainerTableProps) {
  const [lockedTicker, setLockedTicker] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>(defaultSortKey)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(defaultSortDir)
  const [showSchwabTooltip, setShowSchwabTooltip] = useState(false)
  const [prevRanks, setPrevRanks] = useState<Record<string, number>>({})
  const prevListRef = useRef<LiveGainerRow[]>([])

  useEffect(() => {
    if (fullList && fullList.length > 0) {
      const prevList = prevListRef.current
      if (prevList.length > 0) {
        const oldRanks: Record<string, number> = {}
        prevList.forEach((item, idx) => {
          oldRanks[item.ticker] = idx + 1
        })
        setPrevRanks(oldRanks)
      }
      prevListRef.current = fullList
    }
  }, [fullList])

  useEffect(() => {
    const checkTime = () => {
      try {
        const etStr = new Date().toLocaleString('en-US', { timeZone: 'America/New_York' });
        const etDate = new Date(etStr);
        const hour = etDate.getHours();
        setShowSchwabTooltip(hour >= 4 && hour < 7);
      } catch (e) {
        console.error('Error checking ET time:', e);
      }
    };
    checkTime();
    const interval = setInterval(checkTime, 60_000);
    return () => clearInterval(interval);
  }, []);

  const handleRowClick = (ticker: string) => {
    setLockedTicker(prev => (prev === ticker ? null : ticker))
  }

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  // Helper to score trend for sorting
  const getTrendScore = (g: LiveGainerRow) => {
    const lastPrice = g.last_price
    const prevClose = g.prev_close
    const openPrice = g.open_price
    if (lastPrice == null) return 2
    const priceUp = openPrice != null ? lastPrice > openPrice : true
    const changeUp = prevClose != null ? lastPrice > prevClose : true
    if (priceUp && changeUp) return 3
    if (!priceUp && !changeUp) return 1
    return 2
  }

  // Apply sorting
  const sortedGainers = [...gainers].sort((a, b) => {
    let valA: string | number = 0
    let valB: string | number = 0

    switch (sortKey) {
      case 'rank':    valA = fullList.findIndex(x => x.ticker === a.ticker)
                      valB = fullList.findIndex(x => x.ticker === b.ticker); break
      case 'ticker':  valA = a.ticker; valB = b.ticker; break
      case 'price':   valA = a.last_price ?? 0; valB = b.last_price ?? 0; break
      case 'change':  valA = a.gap_pct ?? 0; valB = b.gap_pct ?? 0; break
      case 'mom_2m':  valA = a.mom_2m ?? -9999; valB = b.mom_2m ?? -9999; break
      case 'atr_hod': valA = a.atr_hod ?? 9999; valB = b.atr_hod ?? 9999; break
      case 'rvol':    valA = a.rvol_15m ?? 0; valB = b.rvol_15m ?? 0; break
      case 'hod':     valA = a.high_price ?? 0; valB = b.high_price ?? 0; break
      case 'float':   valA = a.float_shares ?? 0; valB = b.float_shares ?? 0; break
      case 'trend':   valA = getTrendScore(a); valB = getTrendScore(b); break
    }

    if (valA < valB) return sortDir === 'asc' ? -1 : 1
    if (valA > valB) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  const Th = ({
    col, label, align = 'left', width,
  }: { col: SortKey; label: string; align?: 'left' | 'right' | 'center'; width?: string }) => {
    const isSorted = sortKey === col

    const renderHeaderContent = () => {
      if (col === 'mom_2m' && showSchwabTooltip) {
        return (
          <div className="relative group/tooltip inline-flex items-center gap-1">
            <span>{label}</span>
            <Info size={11} className="text-amber-custom hover:text-amber-300 cursor-help shrink-0" />
            <div className="pointer-events-none absolute top-full right-0 mt-2 hidden group-hover/tooltip:block bg-panel border border-border-strong text-text-primary text-[10px] font-medium py-2 px-3 shadow-2xl w-64 leading-relaxed z-50 normal-case font-sans text-left">
              Schwab API does not return today&apos;s pre-market minute bars between 4:00 AM and 7:00 AM ET. Momentum calculations will start updating after 7:00 AM ET.
              <span className="absolute bottom-full right-3 border-4 border-transparent border-b-panel" />
            </div>
          </div>
        )
      }
      return <span>{label}</span>
    }

    return (
      <th
        className={`py-3 pr-4 font-bold text-[10px] uppercase tracking-wider text-text-muted cursor-pointer select-none hover:text-text-primary transition-colors group/th ${width || ''} ${
          align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'
        }`}
        onClick={() => handleSort(col)}
      >
        <div className={`inline-flex items-center gap-1 ${align === 'right' ? 'justify-end w-full' : align === 'center' ? 'justify-center w-full' : ''}`}>
          {renderHeaderContent()}
          <span className={`text-[10px] transition-opacity ${isSorted ? 'opacity-100 text-info-custom' : 'opacity-0 group-hover/th:opacity-50'}`}>
            {isSorted ? (sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />) : <ChevronDown size={12} />}
          </span>
        </div>
      </th>
    )
  }

  const colSpanCount = 6

  return (
    <div className="bg-panel border border-border-subtle p-4 shadow-sm space-y-4">
      <h3 className="text-xs font-bold text-text-secondary tracking-wider uppercase border-b border-border-subtle pb-3 flex items-center justify-between select-none">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-green-custom animate-pulse" />
          {title}
        </div>
        {!loading && (
          <span className="text-[10px] text-text-muted font-mono font-semibold normal-case bg-raised border border-border-subtle px-2 py-0.5">
            {gainers.length} Runners
          </span>
        )}
      </h3>

      <div className="overflow-x-auto overflow-y-hidden">
        <table className="w-full text-sm table-fixed min-w-[500px]">
          <thead className="bg-raised border-b-2 border-border-strong">
            <tr className="text-left text-xs text-text-muted">
              <Th col="rank" label="Rank" width="w-[8%]" />
              <Th col="ticker" label="Ticker" width="w-[22%]" />
              <Th col="price"  label="Price"   align="right" width="w-[15%]" />
              <Th col="change" label="Change(%)" align="right" width="w-[15%]" />
              <Th col="trend"  label="Trend"    align="center" width="w-[18%]" />
              <Th col="float"  label="Float"   align="right" width="w-[22%]" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border-subtle/50">
            {loading ? (
              <SkeletonRows cols={colSpanCount} />
            ) : sortedGainers.length === 0 ? (
              <tr>
                <td colSpan={colSpanCount} className="py-10 text-center text-text-muted text-xs">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              sortedGainers.map((g) => {
                const originalRank = fullList.findIndex(x => x.ticker === g.ticker) + 1
                const isExpanded = lockedTicker === g.ticker

                // Actionability Status Badge Calculations
                const playStatus = computePlayStatus(g.rvol_15m, g.mom_2m)
                const hodStatus  = computeHodStatus(g.last_price, g.high_price)
                const vwapStatus = computeVwapStatus(g.atr_vwap)
                const consolStatus = computeConsolStatus(g.zen_v, g.mom_2m)

                const isFlashing = !!flashingTickers[g.ticker]
                const prevRank = prevRanks[g.ticker]
                const rankChange = prevRank !== undefined ? prevRank - originalRank : 0

                return (
                  <Fragment key={g.ticker}>
                    <tr
                      style={
                        isFlashing
                          ? { backgroundColor: 'rgba(244, 184, 74, 0.2)', transition: 'none' }
                          : { transition: 'background-color 1.5s cubic-bezier(0.25, 1, 0.5, 1)' }
                      }
                      className={`hover:bg-hover transition-all duration-150 border-b border-border-subtle group cursor-pointer ${
                        isExpanded ? 'bg-hover border-l-2 border-l-info-custom font-semibold' : 'even:bg-raised/20'
                      }`}
                      onClick={() => handleRowClick(g.ticker)}
                    >
                      {/* 1. Rank */}
                      <td className="py-2 pr-4 font-bold text-text-secondary text-[14px] w-12 pl-1 select-none tabular-nums text-right">
                        {originalRank}
                      </td>

                      {/* 2. Ticker with badging */}
                      <td className="py-2 pr-4 font-mono text-[13px]">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-text-primary group-hover:text-green-custom transition-colors flex items-center gap-1.5">
                            {g.ticker}
                          </span>
                          <div className="flex items-center gap-1 shrink-0 select-none">
                            {lockedTicker === g.ticker && (
                              <span className="relative group/tooltip inline-flex items-center p-0.5 rounded-none text-[8px] font-black bg-info-custom/10 text-info-custom border border-info-custom/20">
                                <Pin size={8} className="fill-current" />
                                <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-strong text-text-primary text-[10px] font-medium py-1 px-2 rounded-none shadow-2xl whitespace-nowrap z-50">
                                  Pinned open (Click to toggle)
                                  <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-panel" />
                                </span>
                              </span>
                            )}
                            {rankChange > 0 && (
                              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-none text-[9px] font-bold bg-green-custom/10 text-green-custom border border-green-custom/25">
                                <ChevronUp size={10} className="stroke-[3]" />
                                {rankChange}
                              </span>
                            )}
                            {rankChange < 0 && (
                              <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-none text-[9px] font-bold bg-red-custom/10 text-red-custom border border-red-custom/25">
                                <ChevronDown size={10} className="stroke-[3]" />
                                {Math.abs(rankChange)}
                              </span>
                            )}
                            {g.is_repeat_runner && (
                              <span className="relative group/tooltip inline-flex items-center px-1 py-0.25 rounded-none text-[9px] font-bold bg-amber-custom/10 text-amber-custom border border-amber-custom/25">
                                RR
                                <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-strong text-text-primary text-[10px] font-medium py-1 px-2 rounded-none shadow-2xl whitespace-nowrap z-50 normal-case font-sans">
                                  RR = Recent Runner (24h)
                                  <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-panel" />
                                </span>
                              </span>
                            )}
                            {g.is_follow_through && (
                              <span className="relative group/tooltip inline-flex items-center px-1 py-0.25 rounded-none text-[9px] font-bold bg-info-custom/10 text-info-custom border border-info-custom/25">
                                FT
                                <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-strong text-text-primary text-[10px] font-medium py-1 px-2 rounded-none shadow-2xl whitespace-nowrap z-50 normal-case font-sans">
                                  FT = Fast Trade (24h)
                                  <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-panel" />
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

                      {/* 5. Trend */}
                      <td className="py-2 pr-4 text-center select-none">
                        {(() => {
                          const trend = getTrendIndicator(g.last_price, g.prev_close, g.open_price)
                          return (
                            <div className="inline-flex justify-center group/tooltip relative">
                              <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-none text-[11px] border font-bold ${trend.className}`}>
                                {trend.emoji}
                              </span>
                              <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover/tooltip:block bg-panel border border-border-strong text-text-primary text-[10px] font-medium py-1.5 px-2.5 shadow-2xl w-60 leading-relaxed z-50 normal-case font-sans text-left">
                                {trend.tooltip}
                                <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-panel" />
                              </div>
                            </div>
                          )
                        })()}
                      </td>

                      {/* 6. Float & Chevron */}
                      <td className="py-2 pr-4 text-right select-none font-mono text-[12px]">
                        <div className="flex items-center justify-end gap-2 w-full">
                          <FloatCellInline float={g.float_shares} />
                          <span className="text-text-muted group-hover:text-text-primary transition-colors shrink-0">
                            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </span>
                        </div>
                      </td>
                    </tr>

                    {/* Expandable details row */}
                    <tr className="bg-raised/30">
                      <td colSpan={colSpanCount} className="p-0 border-0">
                        <div
                          className={`grid transition-all duration-350 ease-in-out ${
                            isExpanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
                          }`}
                        >
                          <div className="overflow-hidden">
                            <div className="py-4 px-6 border-t border-border-subtle bg-raised/20 space-y-4">
                              {/* ⚡ Actionability & Technical Status Dashboard */}
                              <div className="flex flex-wrap gap-2 select-none border-b border-border-subtle/50 pb-3">
                                {playStatus && (
                                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-none text-[11px] font-bold border ${playStatus.className}`}>
                                    {playStatus.label}
                                  </span>
                                )}
                                {consolStatus && (
                                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-none text-[11px] font-bold border ${consolStatus.className}`}>
                                    {consolStatus.label}
                                  </span>
                                )}
                                {vwapStatus && (
                                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-none text-[11px] font-bold border ${vwapStatus.className}`}>
                                    {vwapStatus.label}
                                  </span>
                                )}
                                {hodStatus && (
                                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-none text-[11px] font-bold border ${hodStatus.className}`}>
                                    {hodStatus.label}
                                  </span>
                                )}
                              </div>

                              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm text-text-secondary">
                                {/* Left Column: Detailed Metrics */}
                                <div className="space-y-3">
                                  <h4 className="text-xs font-bold text-text-muted uppercase tracking-wider select-none">Secondary Metrics</h4>
                                  <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 font-mono text-xs">
                                    <span className="text-text-muted">Volume:</span>
                                    <span className="text-text-primary font-bold">{fmtVol(g.volume)}</span>

                                    <MetricLabelWithTooltip
                                      label="RVOL (15m):"
                                      tooltip="Relative Volume over the last 15 minutes compared to historical average. Higher values indicate unusual/strong activity."
                                    />
                                    <div>
                                      <span className={`inline-flex px-1.5 py-0.5 rounded-none text-[10px] ${getRvolBadgeStyle(g.rvol_15m).className}`}>
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

                                    <span className="text-text-muted">Trade Time:</span>
                                    <div className="flex flex-col gap-0.5 text-text-secondary">
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
                                          <span className={`inline-flex px-1 py-0.25 rounded-none text-[9px] ${getTimeAgoBadge(g.trade_time)?.className}`}>
                                            {getTimeAgoBadge(g.trade_time)?.label}
                                          </span>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>

                                {/* Middle Column: Volatility & Relative Level */}
                                <div className="space-y-3">
                                  <h4 className="text-xs font-bold text-text-muted uppercase tracking-wider select-none">Volatility & Relative Level</h4>
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

                                    <span className="text-text-muted">Sector:</span>
                                    <span className="text-text-primary font-bold font-sans">{g.sector ?? '—'}</span>
                                  </div>
                                </div>

                                {/* Right Column: Trend Sparkline & Actions */}
                                <div className="flex flex-col justify-between gap-4">
                                  {(g.sparkline_intraday && g.sparkline_intraday.length > 0) || (g.sparkline_5d && g.sparkline_5d.length > 0) ? (
                                    <div className="space-y-1.5">
                                      <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider select-none block">
                                        {g.sparkline_intraday && g.sparkline_intraday.length > 0 ? 'Intraday Trend:' : '5d Trend Sparkline:'}
                                      </span>
                                      <div className="bg-raised p-2 rounded-none border border-border-subtle inline-block shadow-inner">
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
                                        e.stopPropagation()
                                        onOpenModal(g)
                                      }}
                                      className="flex-1 md:flex-initial flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-green-custom hover:bg-green-custom/80 border border-green-custom/20 rounded-none shadow transition-all duration-150 active:translate-y-[1px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-green-custom"
                                    >
                                      <Maximize2 size={12} />
                                      Open Detailed View
                                    </button>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        handleResearch(g)
                                      }}
                                      className="flex-1 md:flex-initial flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary bg-raised hover:bg-hover border border-border-strong rounded-none transition-all duration-150 active:translate-y-[1px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-strong"
                                    >
                                      <ExternalLink size={12} />
                                      Research Ticker
                                    </button>
                                  </div>
                                </div>
                              </div>

                              {/* Headline Footer */}
                              <div className="mt-4 pt-3 border-t border-border-subtle/50 flex items-start gap-2 text-xs">
                                <span className="text-text-muted font-bold uppercase select-none shrink-0 mt-0.5">Headline:</span>
                                {g.catalyst === 'Technical / No News' ? (
                                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-none text-[11px] font-bold bg-amber-custom/10 text-amber-custom border border-amber-custom/25">
                                    ⚠️ Speculative Volatility / No News
                                    <span className="text-text-muted font-normal text-[10px]">
                                      — High RVOL, no fundamental catalyst detected in last 24h
                                    </span>
                                  </span>
                                ) : g.catalyst === 'Speculative' ? (
                                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-none text-[11px] font-semibold bg-raised text-text-secondary border border-border-subtle">
                                    ? Unconfirmed Momentum
                                    <span className="text-text-muted font-normal text-[10px]">
                                      — Low or unknown RVOL, no news confirmed
                                    </span>
                                  </span>
                                ) : g.catalyst === 'Confirmed Catalyst' && g.news_headline ? (
                                  <span className="text-text-primary italic leading-relaxed block max-w-2xl">{g.news_headline}</span>
                                ) : (
                                  <span className="text-text-muted italic">No recent news</span>
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

// ── Actionability badge helpers (kept here since they're table-specific) ───

function computePlayStatus(rvol: number | null | undefined, mom: number | null | undefined) {
  if (rvol == null || mom == null) return null
  if (rvol >= 2.0 && mom >= 1.0)   return { label: '🔥 Active In-Play', className: 'bg-amber-custom/20 text-amber-custom border border-amber-custom/35 animate-pulse' }
  if (rvol >= 1.5 || mom >= 0.5)   return { label: '⚡ Actionable',     className: 'bg-amber-custom/10 text-amber-custom border border-amber-custom/20' }
  if (mom < -1.5)                  return { label: '❄️ Fading',         className: 'bg-red-custom/10 text-red-custom border border-red-custom/25' }
  return { label: '💤 Drifting / Cold', className: 'bg-raised text-text-muted border border-border-subtle' }
}

function computeHodStatus(last: number | null | undefined, high: number | null | undefined) {
  if (last == null || high == null || high <= 0) return null
  const pctOff = ((high - last) / high) * 100
  if (pctOff <= 0.2) return { label: '🎯 At HOD', className: 'bg-green-custom/20 text-green-custom border border-green-custom/35' }
  if (pctOff <= 1.5) return { label: `🎯 Near HOD (${pctOff.toFixed(1)}% off)`, className: 'bg-green-custom/10 text-green-custom border border-green-custom/20' }
  if (pctOff <= 5.0) return { label: `📈 Pullback (${pctOff.toFixed(1)}% off)`, className: 'bg-amber-custom/10 text-amber-custom border border-amber-custom/20' }
  return { label: `⚠️ Off HOD (${pctOff.toFixed(1)}% off)`, className: 'bg-red-custom/10 text-red-custom border border-red-custom/25' }
}

function computeVwapStatus(atrVwap: number | null | undefined) {
  if (atrVwap == null) return null
  const absAtr = Math.abs(atrVwap)
  if (absAtr <= 0.4) return { label: '⚡ Nearing VWAP Cross', className: 'bg-green-custom/20 text-green-custom border border-green-custom/35 animate-pulse' }
  if (atrVwap > 0)    return { label: `📈 Above VWAP (+${atrVwap.toFixed(1)} ATR)`, className: 'bg-green-custom/10 text-green-custom border border-green-custom/20' }
  return { label: `📉 Below VWAP (${atrVwap.toFixed(1)} ATR)`, className: 'bg-red-custom/10 text-red-custom border border-red-custom/25' }
}

function computeConsolStatus(zen: number | null | undefined, mom: number | null | undefined) {
  if (zen == null || mom == null) return null
  if (Math.abs(zen) <= 0.25 && Math.abs(mom) <= 0.5) return { label: '⏳ Consolidating',  className: 'bg-info-custom/15 text-info-custom border border-info-custom/30' }
  if (zen > 0.25  && mom > 0.5)  return { label: '🚀 Breaking Out',   className: 'bg-green-custom/20 text-green-custom border border-green-custom/35' }
  if (zen < -0.25 && mom < -0.5) return { label: '📉 Breaking Down',  className: 'bg-red-custom/10 text-red-custom border border-red-custom/25' }
  return { label: '📊 Trending', className: 'bg-raised text-text-secondary border border-border-subtle' }
}
