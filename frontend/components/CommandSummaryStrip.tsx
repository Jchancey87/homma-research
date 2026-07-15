'use client'

import { useEffect, useState, useCallback } from 'react'
import { getCommandSummary, CommandSummaryData } from '@/lib/api'
import {
  TrendingUp, TrendingDown, Minus,
  Activity, Gauge, AlertOctagon, RefreshCw, ChevronDown,
} from 'lucide-react'

// ── Helpers ─────────────────────────────────────────────────────────────────

function chgColor(v: number | null) {
  if (v == null) return 'text-gray-500'
  return v > 0 ? 'text-[#00ff00]' : v < 0 ? 'text-[#ff003c]' : 'text-gray-400'
}

function chgSign(v: number | null) {
  if (v == null) return ''
  return v > 0 ? '+' : ''
}

function fmt(v: number | null, decimals = 2): string {
  if (v == null) return '—'
  return v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function fmtInt(v: number | null): string {
  if (v == null) return '—'
  return v.toLocaleString()
}

const INDEX_ORDER = ['SPY', 'QQQ', 'IWM'] as const

const REGIME_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  risk_on:  { bg: 'bg-[#00ff00]/10', text: 'text-[#00ff00]', border: 'border-[#00ff00]/30' },
  neutral:  { bg: 'bg-amber-400/10',  text: 'text-amber-400',  border: 'border-amber-400/30' },
  risk_off: { bg: 'bg-[#ff003c]/10', text: 'text-[#ff003c]', border: 'border-[#ff003c]/30' },
}

const RISK_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  normal:   { bg: 'bg-gray-500/10',    text: 'text-gray-400',   border: 'border-gray-500/30' },
  elevated: { bg: 'bg-amber-400/10',   text: 'text-amber-400',  border: 'border-amber-400/30' },
  high:     { bg: 'bg-[#ff003c]/10',  text: 'text-[#ff003c]', border: 'border-[#ff003c]/30' },
}

function getFloatThemeStyle(theme: string) {
  if (theme.includes('MICRO'))
    return 'bg-[#ff003c]/10 text-[#ff003c] border-[#ff003c]/20'
  if (theme.includes('MID'))
    return 'bg-amber-400/10 text-amber-400 border-amber-400/20'
  return 'bg-blue-400/10 text-blue-400 border-blue-400/20'
}

type CardId = 'regime' | 'breadth' | 'liquidity' | 'risk'

// ── Skeleton ────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-[#050505] p-3">
      <div className="flex items-center gap-1.5 mb-3">
        <div className="h-3 w-3 bg-[#1a1a1a] animate-pulse" />
        <div className="h-3 w-24 bg-[#1a1a1a] animate-pulse" />
      </div>
      <div className="h-7 w-20 bg-[#1a1a1a] animate-pulse mb-2" />
      <div className="h-4 w-16 bg-[#111] animate-pulse mb-3" />
      <div className="space-y-1.5">
        <div className="h-3 w-full bg-[#111] animate-pulse" />
        <div className="h-3 w-3/4 bg-[#111] animate-pulse" />
        <div className="h-3 w-2/3 bg-[#111] animate-pulse" />
      </div>
    </div>
  )
}

// ── Component ───────────────────────────────────────────────────────────────

export default function CommandSummaryStrip() {
  const [data, setData] = useState<CommandSummaryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [priceFilter, setPriceFilter] = useState(true)
  const [expanded, setExpanded] = useState<CardId | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const toggle = (id: CardId) => setExpanded(prev => prev === id ? null : id)

  const loadData = useCallback(async (filter: boolean) => {
    try {
      const res = await getCommandSummary(filter)
      setData(res)
      setLastUpdated(new Date())
    } catch (err) {
      console.error('Failed to load command summary', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Sync price filter from localStorage
  useEffect(() => {
    const val = localStorage.getItem('price-filter-enabled')
    const currentFilter = val !== null ? val === 'true' : true
    setPriceFilter(currentFilter)
    loadData(currentFilter)

    const handleSync = () => {
      const syncedVal = localStorage.getItem('price-filter-enabled')
      const newFilter = syncedVal !== null ? syncedVal === 'true' : true
      setPriceFilter(newFilter)
      setLoading(true)
      loadData(newFilter)
    }

    window.addEventListener('price-filter-changed', handleSync)
    return () => window.removeEventListener('price-filter-changed', handleSync)
  }, [loadData])

  // Poll every 60s
  useEffect(() => {
    const timer = setInterval(() => loadData(priceFilter), 60_000)
    return () => clearInterval(timer)
  }, [priceFilter, loadData])

  const refresh = () => {
    setLoading(true)
    loadData(priceFilter)
  }

  // ── Loading skeleton ──
  if (loading && !data) {
    return (
      <div className="bg-[#262626] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-[1px]">
        {[1, 2, 3, 4].map(i => <SkeletonCard key={i} />)}
      </div>
    )
  }

  if (!data) return null

  const { regime, breadth, liquidity, risk } = data

  const regimeStyle = REGIME_STYLE[regime.tag] ?? REGIME_STYLE.neutral
  const riskStyle = RISK_STYLE[risk.tag] ?? RISK_STYLE.normal

  // ── Card Header ──
  const CardHeader = ({
    icon: Icon, title, cardId, showRefresh = false,
  }: {
    icon: React.ElementType; title: string; cardId: CardId; showRefresh?: boolean
  }) => (
    <button
      onClick={() => toggle(cardId)}
      className="flex items-center justify-between w-full mb-2 group"
    >
      <span className="text-[10px] font-mono font-bold text-gray-500 uppercase tracking-widest flex items-center gap-1.5">
        <Icon size={11} className="text-gray-600" />
        {title}
      </span>
      <div className="flex items-center gap-1.5">
        {showRefresh && (
          <span
            role="button"
            onClick={(e) => { e.stopPropagation(); refresh() }}
            className="text-gray-600 hover:text-gray-400 transition-colors"
            title="Refresh data"
          >
            <RefreshCw size={10} className={loading ? 'animate-spin' : ''} />
          </span>
        )}
        <ChevronDown
          size={10}
          className={`text-gray-600 group-hover:text-gray-400 transition-transform ${expanded === cardId ? 'rotate-180' : ''}`}
        />
      </div>
    </button>
  )

  // ── Badge helper ──
  const Badge = ({ label, style }: { label: string; style: { bg: string; text: string; border: string } }) => (
    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider border ${style.bg} ${style.text} ${style.border}`}>
      {label}
    </span>
  )

  // ── Sort sector clusters by count desc, take top 3 ──
  const topSectors = Object.entries(liquidity.sector_clusters)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5)

  return (
    <div>
      {/* 4-card grid with 1px charcoal gaps */}
      <div className="bg-[#262626] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-[1px]">

        {/* ─── Card 1: REGIME & INDICES ─── */}
        <div className="bg-[#050505] p-3">
          <CardHeader
            icon={regime.tag === 'risk_on' ? TrendingUp : regime.tag === 'risk_off' ? TrendingDown : Minus}
            title="Market Regime"
            cardId="regime"
          />

          {/* Hero badge */}
          <div className="mb-2">
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1 text-lg font-mono font-black uppercase tracking-wider border ${regimeStyle.bg} ${regimeStyle.text} ${regimeStyle.border}`}
              title={regime.label}
            >
              {regime.tag === 'risk_on' && <TrendingUp size={14} />}
              {regime.tag === 'risk_off' && <TrendingDown size={14} />}
              {regime.tag === 'neutral' && <Minus size={14} />}
              {regime.tag.replace('_', '-').toUpperCase()}
            </span>
          </div>

          {/* Index lines */}
          <div className="space-y-0.5">
            {INDEX_ORDER.map(ticker => {
              const idx = regime.indices?.[ticker]
              if (!idx) return null
              return (
                <div key={ticker} className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-gray-500 font-bold w-8">{ticker}</span>
                  <span className="text-gray-300">
                    {idx.price != null ? `$${fmt(idx.price)}` : '—'}
                  </span>
                  <span className={`font-medium ${chgColor(idx.chg_pct)}`}>
                    {idx.chg_pct != null ? `${chgSign(idx.chg_pct)}${fmt(idx.chg_pct)}%` : '—'}
                  </span>
                </div>
              )
            })}
          </div>

          {/* VIX line */}
          {regime.vix && (
            <div className="flex items-center gap-1.5 mt-1.5 text-[10px] font-mono text-gray-500">
              <span>VIX:</span>
              <span className={regime.vix.value != null && regime.vix.value > 25 ? 'text-[#ff003c]' : regime.vix.value != null && regime.vix.value > 18 ? 'text-amber-400' : 'text-gray-400'}>
                {regime.vix.value != null ? fmt(regime.vix.value, 1) : '—'}
              </span>
              <span className="text-gray-600">{regime.vix.direction === 'up' ? '↑' : regime.vix.direction === 'down' ? '↓' : '→'}</span>
            </div>
          )}

          {/* Expanded drill-down */}
          {expanded === 'regime' && (
            <div className="mt-2 pt-2 border-t border-[#1a1a1a] text-[10px] font-mono text-gray-500 space-y-0.5">
              {INDEX_ORDER.map(ticker => {
                const idx = regime.indices?.[ticker]
                if (!idx) return null
                return (
                  <div key={`vol-${ticker}`} className="flex justify-between">
                    <span>{ticker} Vol</span>
                    <span className="text-gray-400">{idx.volume != null ? fmtInt(idx.volume) : '—'}</span>
                  </div>
                )
              })}
              {lastUpdated && (
                <div className="text-gray-600 pt-1">
                  Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ─── Card 2: SMALL-CAP BREADTH ─── */}
        <div className="bg-[#050505] p-3">
          <CardHeader icon={Activity} title="Small-Cap Breadth" cardId="breadth" />

          {/* Hero: A/D ratio */}
          <div
            className={`text-2xl font-mono font-black tracking-tight leading-none mb-1 ${breadth.is_bullish ? 'text-[#00ff00]' : 'text-gray-300'}`}
            title={`A/D Ratio: ${breadth.ad_ratio_str}`}
          >
            {breadth.ad_ratio_str}
          </div>

          {/* Status badge */}
          <Badge
            label={breadth.status}
            style={breadth.is_bullish
              ? { bg: 'bg-[#00ff00]/10', text: 'text-[#00ff00]', border: 'border-[#00ff00]/20' }
              : { bg: 'bg-gray-500/10', text: 'text-gray-400', border: 'border-gray-500/20' }
            }
          />

          {/* Sub-lines */}
          <div className="mt-2 space-y-0.5 text-[10px] font-mono">
            <div className="text-gray-500">
              Green: <span className="text-[#00ff00]">{fmtInt(breadth.advancing)}</span>
              {' / '}
              Red: <span className="text-[#ff003c]">{fmtInt(breadth.declining)}</span>
            </div>
            <div className="text-gray-500">
              UpVol {breadth.up_down_vol_ratio != null ? (
                <span className="text-gray-400">{fmt(breadth.up_down_vol_ratio, 1)}x</span>
              ) : '—'} DownVol
            </div>
            <div className="text-gray-500">
              {'> 40SMA: '}
              {breadth.above_40sma_pct != null ? (
                <span className="text-gray-400">{fmt(breadth.above_40sma_pct, 0)}%</span>
              ) : '—'}
            </div>
          </div>

          {/* Expanded: pct_green progress bar */}
          {expanded === 'breadth' && (
            <div className="mt-2 pt-2 border-t border-[#1a1a1a]">
              <div className="text-[10px] font-mono text-gray-500 mb-1">
                % Green: {breadth.pct_green != null ? `${fmt(breadth.pct_green, 1)}%` : '—'}
              </div>
              {breadth.pct_green != null && (
                <div className="w-full h-1.5 bg-[#1a1a1a]">
                  <div
                    className="h-full bg-[#00ff00]/60"
                    style={{ width: `${Math.min(breadth.pct_green, 100)}%` }}
                  />
                </div>
              )}
              {breadth.ad_ratio_val != null && (
                <div className="text-[10px] font-mono text-gray-600 mt-1">
                  Raw A/D: {fmt(breadth.ad_ratio_val, 2)}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ─── Card 3: LIQUIDITY & FLOAT ─── */}
        <div className="bg-[#050505] p-3">
          <CardHeader icon={Gauge} title="Liquidity & Float" cardId="liquidity" />

          {/* Hero: avg_rvol_top5 */}
          <div
            className={`text-2xl font-mono font-black tracking-tight leading-none mb-1 ${liquidity.is_high ? 'text-[#00ff00]' : 'text-gray-300'}`}
            title={`Top-5 Avg RVOL: ${fmt(liquidity.avg_rvol_top5, 1)}x`}
          >
            {fmt(liquidity.avg_rvol_top5, 1)}x
          </div>

          {/* Status badge */}
          <Badge
            label={liquidity.status}
            style={liquidity.is_high
              ? { bg: 'bg-[#00ff00]/10', text: 'text-[#00ff00]', border: 'border-[#00ff00]/20' }
              : { bg: 'bg-gray-500/10', text: 'text-gray-400', border: 'border-gray-500/20' }
            }
          />

          {/* Float theme badge */}
          <div className="mt-1.5">
            <span className={`inline-flex px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider border ${getFloatThemeStyle(liquidity.float_theme)}`}>
              {liquidity.float_theme}
            </span>
          </div>

          {/* Float counts */}
          <div className="mt-1.5 text-[10px] font-mono text-gray-500">
            {Object.entries(liquidity.float_counts).map(([key, count], i, arr) => (
              <span key={key}>
                {key.split(' ')[0].replace('MICRO-FLOAT', 'Micro').replace('MID-FLOAT', 'Mid').replace('LARGE-FLOAT', 'Large')}: {count}
                {i < arr.length - 1 && ' · '}
              </span>
            ))}
          </div>

          {/* Top sector clusters */}
          {topSectors.length > 0 && (
            <div className="mt-1 text-[10px] font-mono text-gray-500 truncate">
              {topSectors.slice(0, 3).map(([sector, count], i, arr) => (
                <span key={sector}>
                  {sector}: {count}{i < arr.length - 1 && ' | '}
                </span>
              ))}
            </div>
          )}

          {/* Expanded: full sector breakdown */}
          {expanded === 'liquidity' && (
            <div className="mt-2 pt-2 border-t border-[#1a1a1a] text-[10px] font-mono space-y-0.5">
              {liquidity.median_rvol != null && (
                <div className="flex justify-between text-gray-500">
                  <span>Median RVOL</span>
                  <span className="text-gray-400">{fmt(liquidity.median_rvol, 1)}x</span>
                </div>
              )}
              <div className="text-gray-600 uppercase tracking-wider pt-1 pb-0.5">All Sectors</div>
              {topSectors.map(([sector, count]) => (
                <div key={sector} className="flex justify-between text-gray-500">
                  <span>{sector}</span>
                  <span className="text-gray-400">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ─── Card 4: RISK & ANOMALIES ─── */}
        <div className="bg-[#050505] p-3">
          <CardHeader icon={AlertOctagon} title="Risk & Anomalies" cardId="risk" showRefresh />

          {/* Hero: Risk tag */}
          <div className="mb-2">
            <span
              className={`inline-flex items-center px-3 py-1 text-lg font-mono font-black uppercase tracking-wider border ${riskStyle.bg} ${riskStyle.text} ${riskStyle.border}`}
              title={risk.label}
            >
              {risk.tag.toUpperCase()}
            </span>
          </div>

          {/* VIX sub-line */}
          <div className="text-[10px] font-mono text-gray-500">
            VIX:{' '}
            <span className={risk.vix_value != null && risk.vix_value > 25 ? 'text-[#ff003c]' : risk.vix_value != null && risk.vix_value > 18 ? 'text-amber-400' : 'text-gray-400'}>
              {risk.vix_value != null ? fmt(risk.vix_value, 1) : '—'}
            </span>
            {risk.vix_direction && (
              <span className="text-gray-600 ml-1">{risk.vix_direction === 'up' ? '↑' : risk.vix_direction === 'down' ? '↓' : '→'}</span>
            )}
          </div>

          {/* Halts */}
          <div className="mt-1 text-[10px] font-mono text-gray-500">
            <span className={risk.halt_count > 0 ? 'text-amber-400' : ''}>
              {risk.halt_count} {risk.halt_count === 1 ? 'Halt' : 'Halts'} Active
            </span>
          </div>

          {/* Halt tickers inline */}
          {risk.halt_tickers.length > 0 && (
            <div className="flex items-center gap-1 flex-wrap mt-1">
              {risk.halt_tickers.slice(0, 5).map(ticker => (
                <span
                  key={ticker}
                  className="inline-flex items-center px-1.5 py-0.5 font-mono text-[9px] font-bold bg-amber-400/10 text-amber-400 border border-amber-400/20"
                >
                  {ticker}
                </span>
              ))}
              {risk.halt_tickers.length > 5 && (
                <span className="text-[9px] font-mono text-gray-600">+{risk.halt_tickers.length - 5}</span>
              )}
            </div>
          )}

          {/* Halt rate */}
          {risk.halt_rate_per_hour != null && (
            <div className="mt-1 text-[10px] font-mono text-gray-500">
              Halt Rate: <span className="text-gray-400">{fmt(risk.halt_rate_per_hour, 1)}/hr</span>
            </div>
          )}

          {/* Expanded: risk signals + all halt tickers */}
          {expanded === 'risk' && (
            <div className="mt-2 pt-2 border-t border-[#1a1a1a] text-[10px] font-mono space-y-0.5">
              {risk.signals.length > 0 ? (
                <>
                  <div className="text-gray-600 uppercase tracking-wider pb-0.5">Signals</div>
                  {risk.signals.map((sig, i) => (
                    <div key={i} className="text-gray-400">• {sig}</div>
                  ))}
                </>
              ) : (
                <div className="text-gray-600">No active risk signals</div>
              )}
              {risk.halt_tickers.length > 5 && (
                <>
                  <div className="text-gray-600 uppercase tracking-wider pt-1 pb-0.5">All Halted Tickers</div>
                  <div className="flex items-center gap-1 flex-wrap">
                    {risk.halt_tickers.map(ticker => (
                      <span
                        key={ticker}
                        className="inline-flex items-center px-1.5 py-0.5 font-mono text-[9px] font-bold bg-amber-400/10 text-amber-400 border border-amber-400/20"
                      >
                        {ticker}
                      </span>
                    ))}
                  </div>
                </>
              )}
              {lastUpdated && (
                <div className="text-gray-600 pt-1">
                  Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              )}
            </div>
          )}
        </div>

      </div>

      {/* Subtle footer with last-updated */}
      {lastUpdated && (
        <div className="flex justify-end px-1 pt-0.5">
          <span className="text-[9px] font-mono text-gray-700">
            {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · {data.cache_ttl_s}s cache
          </span>
        </div>
      )}
    </div>
  )
}
