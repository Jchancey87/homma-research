'use client'

import React from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { CommandSummaryData, CardBaseProps } from './types'
import { CardHeader, chgColor, chgSign, fmt, fmtInt } from './shared'

interface MarketRegimeCardProps extends CardBaseProps {
  data: CommandSummaryData['regime']
  macro?: CommandSummaryData['macro']
}

const INDEX_ORDER = ['SPY', 'QQQ', 'IWM'] as const

export default function MarketRegimeCard({ data, macro, expanded, onToggle }: MarketRegimeCardProps) {
  const vix = data.vix
  const isContango = vix?.term_slope == null || vix.term_slope >= 0

  let badgeColor = 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
  if (data.tag === 'risk_off') badgeColor = 'text-red-400 bg-red-500/10 border-red-500/20'
  if (data.tag === 'neutral') badgeColor = 'text-amber-400 bg-amber-500/10 border-amber-500/20'

  return (
    <div className="bg-[#0D1218] border border-border-subtle p-3.5 shadow-sm flex flex-col justify-between hover:border-gray-700 transition-colors">
      <div>
        <CardHeader
          icon={data.tag === 'risk_on' ? TrendingUp : data.tag === 'risk_off' ? TrendingDown : Minus}
          title="US Market Regime"
          expanded={expanded}
          onToggle={onToggle}
        />

        {/* Hero Row: Big Regime Indicator & Sub-Status */}
        <div className="flex items-center justify-between mb-3">
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono font-black uppercase tracking-wider border rounded-none ${badgeColor}`}>
            {data.tag === 'risk_on' && <TrendingUp size={13} />}
            {data.tag === 'risk_off' && <TrendingDown size={13} />}
            {data.tag === 'neutral' && <Minus size={13} />}
            {data.tag.replace('_', '-')}
          </div>
          <span className="text-[10px] font-mono text-gray-400 uppercase tracking-tight">
            {vix?.regime ? vix.regime.replace(/_/g, ' ') : data.label}
          </span>
        </div>

        {/* Crisp Index Ticker Matrix */}
        <div className="space-y-1.5 font-mono text-[11px] bg-[#131B24] p-2 border border-border-subtle">
          {INDEX_ORDER.map(ticker => {
            const idx = data.indices?.[ticker]
            if (!idx) return null
            return (
              <div key={ticker} className="flex items-center justify-between tabular-nums">
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

        {/* Single-Line VIX Structure Summary */}
        {vix && (
          <div className="mt-2.5 pt-2 border-t border-border-subtle flex items-center justify-between font-mono text-[10px] tabular-nums text-gray-400">
            <div className="flex items-center gap-1.5">
              <span className="text-gray-500 font-bold">VIX:</span>
              <span className={`font-bold ${vix.value != null && vix.value > 25 ? 'text-red-400' : vix.value != null && vix.value > 18 ? 'text-amber-400' : 'text-emerald-400'}`}>
                {vix.value != null ? fmt(vix.value, 1) : '—'}
              </span>
              <span className="text-gray-600">{vix.direction === 'up' ? '↑' : '↓'}</span>
            </div>
            {vix.percentile_rank != null && (
              <span className="text-gray-400">{vix.percentile_rank.toFixed(0)}th Pct</span>
            )}
            <span className={`text-[9px] font-bold uppercase px-1 py-0.2 rounded-none ${isContango ? 'text-emerald-400 bg-emerald-500/10' : 'text-red-400 bg-red-500/10'}`}>
              {isContango ? 'Contango' : 'Backwardation'}
            </span>
          </div>
        )}
      </div>

      {/* Expanded Macro & Volume Context */}
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? 'max-h-48 opacity-100 mt-2.5 pt-2 border-t border-border-subtle' : 'max-h-0 opacity-0'}`}>
        <div className="font-mono text-[10px] space-y-1 text-gray-400 tabular-nums">
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
              <div className="text-gray-500 uppercase font-bold tracking-wider mt-2 mb-1">Macro Indicators</div>
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
              {macro.crude?.value != null && (
                <div className="flex justify-between">
                  <span>WTI Crude Oil</span>
                  <span className="text-gray-200">${fmt(macro.crude.value, 2)}</span>
                </div>
              )}
              {macro.gold?.value != null && (
                <div className="flex justify-between">
                  <span>Gold (GLD)</span>
                  <span className="text-gray-200">${fmt(macro.gold.value, 2)}</span>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
