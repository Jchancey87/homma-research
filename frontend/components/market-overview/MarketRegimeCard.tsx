'use client'

import React from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { CommandSummaryData, CardBaseProps } from './types'
import { CardHeader, REGIME_STYLE, chgColor, chgSign, fmt, fmtInt } from './shared'
import MiniGauge from '../ui/MiniGauge'

interface MarketRegimeCardProps extends CardBaseProps {
  data: CommandSummaryData['regime']
  macro?: CommandSummaryData['macro']
}

const INDEX_ORDER = ['SPY', 'QQQ', 'IWM'] as const

export default function MarketRegimeCard({ data, macro, expanded, onToggle }: MarketRegimeCardProps) {
  const regimeStyle = REGIME_STYLE[data.tag] ?? REGIME_STYLE.neutral
  const vix = data.vix

  const isContango = vix?.term_slope == null || vix.term_slope >= 0

  return (
    <div className="bg-[#0D1218] border border-border-subtle p-3 shadow-sm flex flex-col justify-between transition-all duration-300">
      <div>
        <CardHeader
          icon={data.tag === 'risk_on' ? TrendingUp : data.tag === 'risk_off' ? TrendingDown : Minus}
          title="Market Regime"
          expanded={expanded}
          onToggle={onToggle}
        />

        {/* Hero Banner with Left Accent Border */}
        <div className={`p-2 border-l-4 mb-2.5 ${regimeStyle.bg} ${regimeStyle.border}`}>
          <div className="flex items-center gap-1.5 font-mono font-black text-sm uppercase tracking-wider text-white">
            {data.tag === 'risk_on' && <TrendingUp size={14} className="text-[#00ff00]" />}
            {data.tag === 'risk_off' && <TrendingDown size={14} className="text-[#ff003c]" />}
            {data.tag === 'neutral' && <Minus size={14} className="text-amber-400" />}
            <span className={regimeStyle.text}>{data.tag.replace('_', '-').toUpperCase()}</span>
          </div>
          <div className="text-[10px] font-mono text-gray-400 uppercase mt-0.5 tracking-tight font-medium">
            {vix?.regime ? vix.regime.replace(/_/g, ' ') : data.label}
          </div>
        </div>

        {/* Index Lines */}
        <div className="space-y-1 font-mono text-[11px]">
          {INDEX_ORDER.map(ticker => {
            const idx = data.indices?.[ticker]
            if (!idx) return null
            return (
              <div key={ticker} className="flex items-center justify-between py-0.5">
                <span className="text-gray-400 font-bold w-10">{ticker}</span>
                <span className="text-gray-200">
                  {idx.price != null ? `$${fmt(idx.price)}` : '—'}
                </span>
                <span className={`font-semibold w-16 text-right ${chgColor(idx.chg_pct)}`}>
                  {idx.chg_pct != null ? `${chgSign(idx.chg_pct)}${fmt(idx.chg_pct)}%` : '—'}
                </span>
              </div>
            )
          })}
        </div>

        {/* VIX Structure Section */}
        {vix && (
          <div className="mt-2.5 pt-2 border-t border-border-subtle flex items-center justify-between font-mono text-[10px]">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-gray-500 font-bold">VIX:</span>
                <span className={`font-bold ${vix.value != null && vix.value > 25 ? 'text-[#ff003c]' : vix.value != null && vix.value > 18 ? 'text-amber-400' : 'text-gray-300'}`}>
                  {vix.value != null ? fmt(vix.value, 1) : '—'}
                </span>
                <span className="text-gray-600">{vix.direction === 'up' ? '↑' : '↓'}</span>
              </div>

              {vix.vix3m != null && (
                <div className="flex items-center gap-1.5">
                  <span className="text-gray-500">VIX3M:</span>
                  <span className="text-gray-300">{fmt(vix.vix3m, 1)}</span>
                  <span className={`px-1 py-0.2 rounded text-[9px] font-bold ${isContango ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}>
                    {isContango ? 'Contango ▲' : 'Backwardation ▼'}
                  </span>
                </div>
              )}
            </div>

            {vix.percentile_rank != null && (
              <MiniGauge value={vix.percentile_rank} label="1Y Pct" size={40} colorScale="green-red" />
            )}
          </div>
        )}
      </div>

      {/* Expanded Drill-Down */}
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? 'max-h-48 opacity-100 mt-2 pt-2 border-t border-border-subtle' : 'max-h-0 opacity-0'}`}>
        <div className="font-mono text-[10px] space-y-1 text-gray-400">
          <div className="text-gray-500 uppercase font-bold tracking-wider mb-1">Index Volume</div>
          {INDEX_ORDER.map(ticker => {
            const idx = data.indices?.[ticker]
            if (!idx) return null
            return (
              <div key={`vol-${ticker}`} className="flex justify-between">
                <span>{ticker} Volume</span>
                <span className="text-gray-200">{idx.volume != null ? fmtInt(idx.volume) : '—'}</span>
              </div>
            )
          })}

          {macro && (
            <>
              <div className="text-gray-500 uppercase font-bold tracking-wider mt-2 mb-1">Cross-Asset Context</div>
              {macro.us10y?.value != null && (
                <div className="flex justify-between">
                  <span>US 10Y Yield</span>
                  <span className="text-gray-200">{fmt(macro.us10y.value, 2)}%</span>
                </div>
              )}
              {macro.dxy?.value != null && (
                <div className="flex justify-between">
                  <span>Dollar Index (DXY)</span>
                  <span className="text-gray-200">{fmt(macro.dxy.value, 2)}</span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
