'use client'

import { useState, Fragment, useEffect } from 'react'
import { LiveGainerRow } from '@/lib/api'
import { Sparkline } from '@/components/Sparkline'
import { getMomStyle } from '@/lib/momentum'
import { fmtVol } from '@/lib/format'
import { ChevronDown, ChevronUp, Maximize2, ExternalLink, Pin, Info } from 'lucide-react'
import {
  getRvolBadgeStyle, getRvolColor,
  getFloatBadgeStyle, getSpreadBadgeStyle,
  getAtrSpreadStyle, getAtrVwapStyle, getZenVStyle,
  getTimeAgoBadge,
} from './styles'
import {
  GapCell, PriceCell, MetricLabelWithTooltip, SkeletonRows,
} from './badges'

// ── Sort header helper ──────────────────────────────────────────────────────

type SortKey = 'rank' | 'ticker' | 'price' | 'change' | 'mom_2m' | 'atr_hod' | 'float' | 'rvol' | 'hod'

interface GainerTableProps {
  gainers:         LiveGainerRow[]
  fullList:        LiveGainerRow[]
  title:           string
  showRank?:       boolean
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
  const [sortKey, setSortKey] = useState<SortKey>(defaultSortKey)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(defaultSortDir)
  const [showSchwabTooltip, setShowSchwabTooltip] = useState(false)

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
            <Info size={11} className="text-amber-550 hover:text-amber-400 cursor-help shrink-0" />
            <div className="pointer-events-none absolute top-full right-0 mt-2 hidden group-hover/tooltip:block bg-gray-950 border border-gray-800 text-white text-[10px] font-medium py-2 px-3 rounded-lg shadow-2xl w-64 leading-relaxed z-50 normal-case font-sans text-left">
              Schwab API does not return today&apos;s pre-market minute bars between 4:00 AM and 7:00 AM ET. Momentum calculations will start updating after 7:00 AM ET.
              <span className="absolute bottom-full right-3 border-4 border-transparent border-b-gray-950" />
            </div>
          </div>
        )
      }
      return <span>{label}</span>
    }

    return (
      <th
        className={`pb-2 pr-4 font-semibold cursor-pointer select-none hover:text-white transition-colors group/th ${width || ''} ${
          align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'
        }`}
        onClick={() => handleSort(col)}
      >
        <div className={`inline-flex items-center gap-1 ${align === 'right' ? 'justify-end w-full' : align === 'center' ? 'justify-center w-full' : ''}`}>
          {renderHeaderContent()}
          <span className={`text-[10px] transition-opacity ${isSorted ? 'opacity-100 text-emerald-400' : 'opacity-0 group-hover/th:opacity-50'}`}>
            {isSorted ? (sortDir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />) : <ChevronDown size={12} />}
          </span>
        </div>
      </th>
    )
  }

  const colSpanCount = showRank ? 8 : 7

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
              {showRank && <Th col="rank" label="Rank" width="w-[7%]" />}
              <Th col="ticker" label="Ticker" width={showRank ? 'w-[15%]' : 'w-[20%]'} />
              <Th col="price"  label="Price"   align="right" width={showRank ? 'w-[11%]' : 'w-[12%]'} />
              <Th col="change" label="Change(%)" align="right" width={showRank ? 'w-[11%]' : 'w-[12%]'} />
              <Th col="mom_2m" label="Mom %"   align="right" width={showRank ? 'w-[11%]' : 'w-[12%]'} />
              <th className="pb-2 pr-4 font-semibold text-center select-none w-[20%]">Trend (1h)</th>
              {title === 'All Live Gainers' ? (
                <Th col="rvol" label="RVOL" align="right" width={showRank ? 'w-[11%]' : 'w-[12%]'} />
              ) : (
                <Th col="hod" label="HOD" align="right" width={showRank ? 'w-[11%]' : 'w-[12%]'} />
              )}
              <Th col="float" label="Float" align="right" width={showRank ? 'w-[14%]' : 'w-[12%]'} />
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
                const playStatus = computePlayStatus(g.rvol_15m, g.mom_2m)
                const hodStatus  = computeHodStatus(g.last_price, g.high_price)
                const vwapStatus = computeVwapStatus(g.atr_vwap)
                const consolStatus = computeConsolStatus(g.zen_v, g.mom_2m)

                const isFlashing = !!flashingTickers[g.ticker]
                return (
                  <Fragment key={g.ticker}>
                    <tr
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

                      {/* 2. Ticker with badging */}
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
                            {g.is_follow_through && (
                              <span className="relative group/tooltip inline-flex items-center px-1 py-0.25 rounded text-[8px] font-black bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                FT
                                <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover/tooltip:block bg-gray-950 border border-gray-800 text-white text-[10px] font-medium py-1 px-2 rounded shadow-2xl whitespace-nowrap z-50">
                                  FT = Fast Trade (24h)
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

                      {/* Trend (1h) sparkline */}
                      <td className="py-2.5 pr-4 text-center select-none">
                        <div className="inline-flex justify-center bg-gray-900/20 px-1 py-0.5 rounded border border-gray-800/60">
                          {g.sparkline_1h && g.sparkline_1h.length > 0 ? (
                            <Sparkline points={g.sparkline_1h} width={70} height={18} />
                          ) : (
                            <span className="text-[10px] text-gray-650 font-mono">—</span>
                          )}
                        </div>
                      </td>

                      {/* 6. RVOL or HOD Column */}
                      <td className="py-2.5 pr-4 text-right font-mono select-none animate-in fade-in duration-200">
                        {title === 'All Live Gainers' ? (
                          <span className={`font-semibold ${getRvolColor(g.rvol_15m)}`}>
                            {g.rvol_15m != null ? `${g.rvol_15m.toFixed(1)}x` : '—'}
                          </span>
                        ) : (
                          <span className="font-semibold text-white">
                            {g.high_price != null && g.high_price > 0 ? `$${g.high_price.toFixed(2)}` : '—'}
                          </span>
                        )}
                      </td>

                      {/* 7. Float */}
                      <td className="py-2.5 pr-4 text-right animate-in fade-in duration-200">
                        <span className={`whitespace-nowrap text-[11px] font-mono font-bold ${getFloatBadgeStyle(g.float_shares).className}`}>
                          {getFloatBadgeStyle(g.float_shares).label}
                        </span>
                      </td>
                    </tr>

                    {/* Expandable details row */}
                    <tr className="bg-gray-900/10">
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
                                        e.stopPropagation()
                                        onOpenModal(g)
                                      }}
                                      className="flex-1 md:flex-initial flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 border border-emerald-500/20 rounded-lg shadow transition-colors"
                                    >
                                      <Maximize2 size={12} />
                                      Open Detailed View
                                    </button>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        handleResearch(g)
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

// ── Actionability badge helpers (kept here since they're table-specific) ───

function computePlayStatus(rvol: number | null | undefined, mom: number | null | undefined) {
  if (rvol == null || mom == null) return null
  if (rvol >= 2.0 && mom >= 1.0)   return { label: '🔥 Active In-Play', className: 'bg-orange-500/20 text-orange-400 border border-orange-500/35 animate-pulse' }
  if (rvol >= 1.5 || mom >= 0.5)   return { label: '⚡ Actionable',     className: 'bg-amber-500/15 text-amber-300 border border-amber-500/25' }
  if (mom < -1.5)                  return { label: '❄️ Fading',         className: 'bg-rose-500/15 text-rose-355 border border-rose-500/25' }
  return { label: '💤 Drifting / Cold', className: 'bg-gray-800/40 text-gray-400 border border-gray-800/60' }
}

function computeHodStatus(last: number | null | undefined, high: number | null | undefined) {
  if (last == null || high == null || high <= 0) return null
  const pctOff = ((high - last) / high) * 100
  if (pctOff <= 0.2) return { label: '🎯 At HOD', className: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/35' }
  if (pctOff <= 1.5) return { label: `🎯 Near HOD (${pctOff.toFixed(1)}% off)`, className: 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' }
  if (pctOff <= 5.0) return { label: `📈 Pullback (${pctOff.toFixed(1)}% off)`, className: 'bg-amber-500/10 text-amber-300 border border-amber-500/20' }
  return { label: `⚠️ Off HOD (${pctOff.toFixed(1)}% off)`, className: 'bg-rose-500/15 text-rose-300 border border-rose-500/25' }
}

function computeVwapStatus(atrVwap: number | null | undefined) {
  if (atrVwap == null) return null
  const absAtr = Math.abs(atrVwap)
  if (absAtr <= 0.4) return { label: '⚡ Nearing VWAP Cross', className: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/35 animate-pulse' }
  if (atrVwap > 0)    return { label: `📈 Above VWAP (+${atrVwap.toFixed(1)} ATR)`, className: 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' }
  return { label: `📉 Below VWAP (${atrVwap.toFixed(1)} ATR)`, className: 'bg-rose-500/10 text-rose-300 border border-rose-500/20' }
}

function computeConsolStatus(zen: number | null | undefined, mom: number | null | undefined) {
  if (zen == null || mom == null) return null
  if (Math.abs(zen) <= 0.25 && Math.abs(mom) <= 0.5) return { label: '⏳ Consolidating',  className: 'bg-blue-500/20 text-blue-300 border border-blue-500/35' }
  if (zen > 0.25  && mom > 0.5)  return { label: '🚀 Breaking Out',   className: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/35' }
  if (zen < -0.25 && mom < -0.5) return { label: '📉 Breaking Down',  className: 'bg-rose-500/20 text-rose-300 border border-rose-500/35' }
  return { label: '📊 Trending', className: 'bg-gray-800/40 text-gray-300 border border-gray-800/60' }
}
