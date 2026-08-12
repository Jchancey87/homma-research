'use client'

import React from 'react'
import { BarChart3 } from 'lucide-react'
import { CommandSummaryData, CardBaseProps } from './types'
import { CardHeader, chgColor, chgSign, fmt } from './shared'

interface SectorStrengthCardProps extends CardBaseProps {
  data?: CommandSummaryData['sector_strength']
}

export default function SectorStrengthCard({ data, expanded, onToggle }: SectorStrengthCardProps) {
  let badgeColor = 'text-gray-400 bg-gray-500/10 border-gray-500/20'
  let tone = 'UNKNOWN'
  if (data?.market_tone) {
    tone = data.market_tone.toUpperCase()
    if (data.market_tone === 'bullish') badgeColor = 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
    else if (data.market_tone === 'bearish') badgeColor = 'text-red-400 bg-red-500/10 border-red-500/20'
    else if (data.market_tone === 'mixed') badgeColor = 'text-amber-400 bg-amber-500/10 border-amber-500/20'
    else if (data.market_tone === 'rotation') badgeColor = 'text-sky-400 bg-sky-500/10 border-sky-500/20'
  }

  const getRsBg = (rs: number | null) => {
    if (rs == null) return 'bg-gray-500/10 text-gray-400'
    if (rs >= 1.0) return 'bg-emerald-500/25 text-emerald-300'
    if (rs >= 0.25) return 'bg-emerald-500/10 text-emerald-400'
    if (rs > -0.25) return 'bg-gray-500/10 text-gray-400'
    if (rs > -1.0) return 'bg-red-500/10 text-red-400'
    return 'bg-red-500/25 text-red-300'
  }

  const sectors = data?.sectors || []
  const sortedSectors = [...sectors].sort((a, b) => (b.rs_vs_spy || 0) - (a.rs_vs_spy || 0))

  return (
    <div className="bg-[#0D1218] border border-border-subtle p-3.5 shadow-sm flex flex-col justify-between hover:border-gray-700 transition-colors">
      <div>
        <CardHeader
          icon={BarChart3}
          title="Sector Strength"
          expanded={expanded}
          onToggle={onToggle}
        />

        {/* Hero Row: Market Tone & SPY */}
        <div className="flex items-center justify-between mb-3">
          <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono font-black tracking-wider border rounded-none ${badgeColor}`}>
            {tone}
          </div>
          {data?.spy && (
            <div className="flex items-center gap-2 font-mono text-[11px] tabular-nums">
              <span className="text-gray-400 font-bold">SPY</span>
              <span className="text-gray-200">{data.spy.price != null ? `$${fmt(data.spy.price)}` : '—'}</span>
              <span className={`font-semibold ${chgColor(data.spy.chg_pct)}`}>
                {data.spy.chg_pct != null ? `${chgSign(data.spy.chg_pct)}${fmt(data.spy.chg_pct)}%` : '—'}
              </span>
            </div>
          )}
        </div>

        {/* Sector Grid Heatmap */}
        <div className="grid grid-cols-4 gap-1.5 mb-2.5">
          {sectors.map((s) => {
            const rsBg = getRsBg(s.rs_vs_spy)
            return (
              <div key={s.etf} className={`flex flex-col items-center justify-center p-1.5 border border-border-subtle ${rsBg} font-mono text-[10px] tabular-nums`}>
                <span className="font-bold">{s.etf}</span>
                <span>{s.rs_vs_spy != null ? `${chgSign(s.rs_vs_spy)}${fmt(s.rs_vs_spy)}` : '—'}</span>
              </div>
            )
          })}
        </div>

        {/* Summary Line */}
        <div className="pt-2 border-t border-border-subtle flex items-center justify-center font-mono text-[10px] text-gray-400">
          {data?.leading_count ?? 0} leading · {data?.lagging_count ?? 0} lagging
        </div>
      </div>

      {/* Expanded Detail Table */}
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? 'max-h-96 opacity-100 mt-2.5 pt-2 border-t border-border-subtle' : 'max-h-0 opacity-0'}`}>
        <div className="font-mono text-[10px] w-full text-left tabular-nums space-y-1">
          <div className="flex text-gray-500 uppercase font-bold tracking-wider mb-2 pb-1 border-b border-border-subtle">
            <div className="w-1/4">Sector</div>
            <div className="w-1/4 text-right">Price</div>
            <div className="w-1/4 text-right">Chg%</div>
            <div className="w-1/4 text-right">RS</div>
          </div>
          {sortedSectors.map((s) => (
            <div key={s.etf} className="flex items-center text-gray-300 py-0.5">
              <div className="w-1/4 flex flex-col">
                <span className="font-bold">{s.etf}</span>
                <span className="text-[9px] text-gray-500 truncate">{s.sector}</span>
              </div>
              <div className="w-1/4 text-right">{s.price != null ? fmt(s.price) : '—'}</div>
              <div className={`w-1/4 text-right ${chgColor(s.chg_pct)}`}>{s.chg_pct != null ? `${chgSign(s.chg_pct)}${fmt(s.chg_pct)}%` : '—'}</div>
              <div className="w-1/4 text-right flex justify-end">
                <span className={`px-1.5 py-0.5 rounded-none ${getRsBg(s.rs_vs_spy)}`}>
                  {s.rs_vs_spy != null ? `${chgSign(s.rs_vs_spy)}${fmt(s.rs_vs_spy)}` : '—'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
