'use client'

import { useState, Fragment, useEffect, useRef } from 'react'
import { LiveGainerRow } from '@/lib/api'
import { Sparkline } from '@/components/Sparkline'
import { fmtVol } from '@/lib/format'
import { ChevronDown, ChevronUp, Maximize2, ExternalLink, Pin, Info } from 'lucide-react'
import {
  getRvolBadgeStyle, getRvolColor, getSpreadBadgeStyle,
  getAtrSpreadStyle, getAtrVwapStyle, getZenVStyle,
  getTrendIndicator,
} from './styles'
import {
  GapCell, PriceCell, MetricLabelWithTooltip, SkeletonRows, FloatCellInline,
} from './badges'

// ── Sort header helper ──────────────────────────────────────────────────────

type SortKey = 'rank' | 'ticker' | 'price' | 'change' | 'mom_2m' | 'atr_hod' | 'float' | 'rvol' | 'hod' | 'trend' | 'spark' | 'signal'

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
      case 'spark':   valA = a.gap_pct ?? 0; valB = b.gap_pct ?? 0; break
      case 'signal':  valA = a.rvol_15m ?? 0; valB = b.rvol_15m ?? 0; break
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
          <div className="relative group/tooltip inline-flex items-center gap-0.5">
            <span>{label}</span>
            <Info size={9} className="text-amber-custom hover:text-amber-300 cursor-help shrink-0" />
            <div className="pointer-events-none absolute top-full right-0 mt-1 hidden group-hover/tooltip:block bg-panel border border-border-strong text-text-primary text-[10px] font-medium py-1 px-2 shadow-2xl w-56 leading-normal z-50 normal-case font-sans text-left">
              Schwab API does not return today&apos;s pre-market minute bars between 4:00 AM and 7:00 AM ET. Momentum calculations will start updating after 7:00 AM ET.
              <span className="absolute bottom-full right-2 border-4 border-transparent border-b-panel" />
            </div>
          </div>
        )
      }
      return <span>{label}</span>
    }

    return (
      <th
        className={`py-[4px] px-1.5 font-bold text-[10px] uppercase tracking-normal text-text-muted cursor-pointer select-none hover:text-text-primary transition-colors group/th ${width || ''} ${
          align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left'
        } ${isSorted ? 'text-text-primary' : ''}`}
        onClick={() => handleSort(col)}
      >
        <div className={`inline-flex items-center gap-0.5 ${align === 'right' ? 'justify-end w-full' : align === 'center' ? 'justify-center w-full' : ''}`}>
          {renderHeaderContent()}
          <span className={`text-[10px] transition-opacity ${isSorted ? 'opacity-100 text-info-custom' : 'opacity-0 group-hover/th:opacity-50'}`}>
            {isSorted ? (sortDir === 'asc' ? <ChevronUp size={10} /> : <ChevronDown size={10} />) : <ChevronDown size={10} />}
          </span>
        </div>
      </th>
    )
  }

  const colSpanCount = 9

  return (
    <div className="bg-panel border border-border-subtle/30 p-2.5 space-y-2.5">
      <h3 className="text-[11px] font-bold text-text-secondary tracking-wide uppercase border-b border-border-subtle/30 pb-1.5 flex items-center justify-between select-none h-[24px]">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 bg-green-custom animate-pulse shrink-0" />
          <span>{title}</span>
        </div>
        {!loading && (
          <span className="text-[9px] text-text-muted font-mono font-medium lowercase">
            {gainers.length} runners
          </span>
        )}
      </h3>

      <div className="overflow-x-auto overflow-y-auto h-[320px] scrollbar-thin">
        <table className="w-full text-xs table-fixed min-w-[580px]">
          <thead className="bg-[#12161c] border-b border-[#2b323e]">
            <tr className="text-left text-xs text-text-muted">
              <Th col="rank" label="Rk" align="right" width="w-[5%]" />
              <Th col="ticker" label="Ticker" width="w-[14%]" />
              <Th col="price"  label="Price"   align="right" width="w-[11%]" />
              <Th col="change" label="Chg(%)" align="right" width="w-[11%]" />
              <Th col="trend"  label="Tr"    align="center" width="w-[6%]" />
              <Th col="float"  label="Float"   align="right" width="w-[13%]" />
              <Th col="rvol"   label="RVOL"    align="right" width="w-[10%]" />
              <Th col="spark"  label="Spark"   align="center" width="w-[14%]" />
              <Th col="signal" label="Signals" align="left" width="w-[16%]" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e222a]/50">
            {loading ? (
              <SkeletonRows cols={colSpanCount} />
            ) : sortedGainers.length === 0 ? (
              <tr>
                <td colSpan={colSpanCount} className="py-8 text-center text-text-muted text-xs">
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
                          ? { backgroundColor: 'rgba(244, 184, 74, 0.15)', transition: 'none' }
                          : { transition: 'background-color 1s ease-out' }
                      }
                      className={`hover:bg-hover transition-all duration-75 border-b border-[#1A202C]/20 cursor-pointer ${
                        isExpanded ? 'bg-hover/80 border-l-2 border-l-info-custom font-semibold' : 'even:bg-[#0A0B0D]/30'
                      }`}
                      onClick={() => handleRowClick(g.ticker)}
                    >
                      {/* 1. Rank */}
                      <td className="py-[3px] pr-2 font-bold text-text-secondary text-[12px] tabular-nums select-none text-right">
                        {originalRank}
                      </td>

                      {/* 2. Ticker with inline badging */}
                      <td className="py-[3px] px-1.5 font-mono text-[12px]">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-text-primary group-hover:text-green-custom transition-colors">
                            {g.ticker}
                          </span>
                          <div className="flex items-center gap-0.5 shrink-0 select-none">
                            {lockedTicker === g.ticker && (
                              <span className="text-[8px] text-info-custom font-black shrink-0">
                                <Pin size={7} className="fill-current" />
                              </span>
                            )}
                            {rankChange > 0 && (
                              <span className="text-[9px] font-bold text-green-custom shrink-0" title={`Rank up by ${rankChange}`}>
                                ▲{rankChange}
                              </span>
                            )}
                            {rankChange < 0 && (
                              <span className="text-[9px] font-bold text-red-custom shrink-0" title={`Rank down by ${Math.abs(rankChange)}`}>
                                ▼{Math.abs(rankChange)}
                              </span>
                            )}
                            {g.is_repeat_runner && (
                              <span className="text-[9px] font-bold text-amber-custom bg-amber-custom/5 px-0.5 border border-amber-custom/10 shrink-0" title="Recent Runner (24h)">
                                RR
                              </span>
                            )}
                            {g.is_follow_through && (
                              <span className="text-[9px] font-bold text-info-custom bg-info-custom/5 px-0.5 border border-info-custom/10 shrink-0" title="Fast Trade (24h)">
                                FT
                              </span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* 3. Price */}
                      <PriceCell last={g.last_price} prev={g.prev_close} />

                      {/* 4. Change (%) */}
                      <GapCell gap={g.gap_pct} />

                      {/* 5. Trend (simplified to minimal arrow/dash glyph) */}
                      {(() => {
                        const trend = getTrendIndicator(g.last_price, g.prev_close, g.open_price)
                        let glyph = '■'
                        let colorClass = 'text-text-muted'
                        if (trend.label === 'Strong Bullish') {
                          glyph = '▲'
                          colorClass = 'text-green-custom'
                        } else if (trend.label === 'Strong Bearish') {
                          glyph = '▼'
                          colorClass = 'text-red-custom'
                        }
                        return (
                          <td className="py-[3px] px-1.5 text-center select-none font-mono text-[11px] font-bold" title={trend.tooltip}>
                            <span className={colorClass}>{glyph}</span>
                          </td>
                        )
                      })()}

                      {/* 6. Float */}
                      <td className="py-[3px] px-1.5 text-right select-none font-mono text-[11px]">
                        <FloatCellInline float={g.float_shares} />
                      </td>

                      {/* 7. RVOL */}
                      <td className={`py-[3px] px-1.5 text-right select-none font-mono text-[11px] font-bold ${getRvolColor(g.rvol_15m)}`}>
                        {g.rvol_15m != null ? `${g.rvol_15m.toFixed(1)}x` : '—'}
                      </td>

                      {/* 8. Sparkline (colored dynamically by last 5m candle direction) */}
                      <td className="py-[3px] px-1.5 text-center select-none">
                        {((g.sparkline_intraday && g.sparkline_intraday.length > 0) || (g.sparkline_5d && g.sparkline_5d.length > 0)) ? (
                          <Sparkline
                            points={g.sparkline_intraday && g.sparkline_intraday.length > 0 ? g.sparkline_intraday : g.sparkline_5d}
                            width={38}
                            height={10}
                            colorByLast5m={true}
                          />
                        ) : (
                          <span className="text-[10px] text-text-muted">—</span>
                        )}
                      </td>

                      {/* 9. Signals */}
                      {(() => {
                        const signals = []
                        if (g.mom_2m != null && g.mom_2m > 0.5) {
                          signals.push({ code: 'MOM', className: 'text-green-custom' })
                        }
                        if (g.atr_hod != null && g.atr_hod <= 1.0) {
                          signals.push({ code: 'HOD', className: 'text-amber-custom' })
                        }
                        if (g.atr_vwap != null && g.atr_vwap >= 0) {
                          signals.push({ code: 'VWP', className: 'text-info-custom' })
                        }
                        if (g.rvol_15m != null && g.rvol_15m >= 5.0) {
                          signals.push({ code: 'VOL', className: 'text-emerald-500 font-bold' })
                        }
                        return (
                          <td className="py-[3px] px-1.5 text-left select-none font-mono text-[9px] font-bold">
                            <div className="flex items-center gap-1">
                              {signals.map(s => (
                                <span key={s.code} className={`${s.className} tracking-tighter`} title={s.code}>
                                  {s.code}
                                </span>
                              ))}
                              {signals.length === 0 && <span className="text-text-muted/40">—</span>}
                            </div>
                          </td>
                        )
                      })()}
                    </tr>

                    {/* Expandable details row */}
                    <tr className="bg-raised/15">
                      <td colSpan={colSpanCount} className="p-0 border-0">
                        <div
                          className={`grid transition-all duration-300 ease-in-out ${
                            isExpanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
                          }`}
                        >
                          <div className="overflow-hidden">
                            <div className="py-2.5 px-4 border-t border-border-subtle/30 bg-[#0E1116] space-y-2.5">
                              {/* Actionability & Technical Status Dashboard */}
                              <div className="flex flex-wrap gap-2 select-none border-b border-border-subtle/20 pb-2">
                                {playStatus && (
                                  <span className={`inline-flex items-center px-1.5 py-0.25 text-[10px] font-mono font-bold border border-current bg-transparent ${playStatus.className}`}>
                                    {playStatus.label}
                                  </span>
                                )}
                                {consolStatus && (
                                  <span className={`inline-flex items-center px-1.5 py-0.25 text-[10px] font-mono font-bold border border-current bg-transparent ${consolStatus.className}`}>
                                    {consolStatus.label}
                                  </span>
                                )}
                                {vwapStatus && (
                                  <span className={`inline-flex items-center px-1.5 py-0.25 text-[10px] font-mono font-bold border border-current bg-transparent ${vwapStatus.className}`}>
                                    {vwapStatus.label}
                                  </span>
                                )}
                                {hodStatus && (
                                  <span className={`inline-flex items-center px-1.5 py-0.25 text-[10px] font-mono font-bold border border-current bg-transparent ${hodStatus.className}`}>
                                    {hodStatus.label}
                                  </span>
                                )}
                              </div>

                              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-text-secondary">
                                {/* Left Column: Detailed Metrics */}
                                <div className="space-y-2">
                                  <h4 className="text-[10px] font-bold text-text-muted uppercase tracking-wider select-none border-b border-border-subtle/25 pb-0.5">Secondary Metrics</h4>
                                  <div className="grid grid-cols-2 gap-x-2 gap-y-1 font-mono text-[11px]">
                                    <span className="text-text-muted">Volume:</span>
                                    <span className="text-text-primary font-bold">{fmtVol(g.volume)}</span>

                                    <MetricLabelWithTooltip
                                      label="RVOL (15m):"
                                      tooltip="Relative Volume over the last 15 minutes compared to historical average. Higher values indicate unusual/strong activity."
                                    />
                                    <div>
                                      <span className={`inline-flex font-bold ${getRvolBadgeStyle(g.rvol_15m).className}`}>
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
                                    </div>
                                  </div>
                                </div>

                                {/* Middle Column: Volatility & Relative Level */}
                                <div className="space-y-2">
                                  <h4 className="text-[10px] font-bold text-text-muted uppercase tracking-wider select-none border-b border-border-subtle/25 pb-0.5">Volatility & Relative Level</h4>
                                  <div className="grid grid-cols-2 gap-x-2 gap-y-1 font-mono text-[11px]">
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
                                    <span className="text-text-primary font-bold font-sans truncate">{g.sector ?? '—'}</span>
                                  </div>
                                </div>

                                {/* Right Column: Trend Sparkline & Actions */}
                                <div className="flex flex-col justify-between gap-2.5">
                                  {(g.sparkline_intraday && g.sparkline_intraday.length > 0) || (g.sparkline_5d && g.sparkline_5d.length > 0) ? (
                                    <div className="space-y-0.5">
                                      <span className="text-[9px] font-bold text-text-muted uppercase tracking-wider select-none block">
                                        Trend Sparkline:
                                      </span>
                                      <div className="bg-[#12161c] p-1.5 border border-border-subtle/30 inline-block">
                                        <Sparkline
                                          points={g.sparkline_intraday && g.sparkline_intraday.length > 0 ? g.sparkline_intraday : g.sparkline_5d}
                                          width={80}
                                          height={20}
                                          colorByLast5m={true}
                                        />
                                      </div>
                                    </div>
                                  ) : (
                                    <div />
                                  )}
                                  <div className="flex flex-row md:flex-col justify-end gap-1.5 select-none w-full">
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        onOpenModal(g)
                                      }}
                                      className="flex-1 md:flex-initial flex items-center justify-center gap-1 px-2.5 py-1 text-[11px] font-bold text-white bg-green-custom/80 hover:bg-green-custom border border-green-custom/20 transition-all"
                                    >
                                      <Maximize2 size={11} />
                                      Detailed View
                                    </button>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        handleResearch(g)
                                      }}
                                      className="flex-1 md:flex-initial flex items-center justify-center gap-1 px-2.5 py-1 text-[11px] font-bold text-text-secondary hover:text-text-primary bg-[#12161c] hover:bg-[#1b222d] border border-border-subtle/45 transition-all"
                                    >
                                      <ExternalLink size={11} />
                                      Research Ticker
                                    </button>
                                  </div>
                                </div>
                              </div>

                              {/* Headline Footer */}
                              <div className="mt-2 pt-2 border-t border-border-subtle/20 flex items-start gap-1.5 text-[11px]">
                                <span className="text-text-muted font-bold uppercase select-none shrink-0">Headline:</span>
                                {g.catalyst === 'Technical / No News' ? (
                                  <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-custom">
                                    ⚠️ Speculative Volatility / No News
                                    <span className="text-text-muted font-normal">
                                      — High RVOL, no news catalyst in 24h
                                    </span>
                                  </span>
                                ) : g.catalyst === 'Speculative' ? (
                                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-text-secondary">
                                    ? Unconfirmed Momentum
                                    <span className="text-text-muted font-normal">
                                      — Low RVOL, no news confirmed
                                    </span>
                                  </span>
                                ) : g.catalyst === 'Confirmed Catalyst' && g.news_headline ? (
                                  <span className="text-text-primary leading-normal block max-w-2xl font-medium">{g.news_headline}</span>
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
  if (rvol >= 2.0 && mom >= 1.0)   return { label: '🔥 Active In-Play', className: 'text-amber-custom animate-pulse' }
  if (rvol >= 1.5 || mom >= 0.5)   return { label: '⚡ Actionable',     className: 'text-amber-custom' }
  if (mom < -1.5)                  return { label: '❄️ Fading',         className: 'text-red-custom' }
  return { label: '💤 Drifting / Cold', className: 'text-text-muted' }
}

function computeHodStatus(last: number | null | undefined, high: number | null | undefined) {
  if (last == null || high == null || high <= 0) return null
  const pctOff = ((high - last) / high) * 100
  if (pctOff <= 0.2) return { label: '🎯 At HOD', className: 'text-green-custom font-bold' }
  if (pctOff <= 1.5) return { label: `🎯 Near HOD (${pctOff.toFixed(1)}% off)`, className: 'text-green-custom' }
  if (pctOff <= 5.0) return { label: `📈 Pullback (${pctOff.toFixed(1)}% off)`, className: 'text-amber-custom' }
  return { label: `⚠️ Off HOD (${pctOff.toFixed(1)}% off)`, className: 'text-red-custom' }
}

// Keep parameter name 'atrVwap' to preserve exact implementation logic
function computeVwapStatus(atrVwap: number | null | undefined) {
  if (atrVwap == null) return null
  const absAtr = Math.abs(atrVwap)
  if (absAtr <= 0.4) return { label: '⚡ Nearing VWAP Cross', className: 'text-green-custom font-bold animate-pulse' }
  if (atrVwap > 0)    return { label: `📈 Above VWAP (+${atrVwap.toFixed(1)} ATR)`, className: 'text-green-custom' }
  return { label: `📉 Below VWAP (${atrVwap.toFixed(1)} ATR)`, className: 'text-red-custom' }
}

function computeConsolStatus(zen: number | null | undefined, mom: number | null | undefined) {
  if (zen == null || mom == null) return null
  if (Math.abs(zen) <= 0.25 && Math.abs(mom) <= 0.5) return { label: '⏳ Consolidating',  className: 'text-info-custom' }
  if (zen > 0.25  && mom > 0.5)  return { label: '🚀 Breaking Out',   className: 'text-green-custom font-bold' }
  if (zen < -0.25 && mom < -0.5) return { label: '📉 Breaking Down',  className: 'text-red-custom' }
  return { label: '📊 Trending', className: 'text-text-secondary' }
}
