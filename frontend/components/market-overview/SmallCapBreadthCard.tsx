'use client'

import React from 'react'
import { Activity } from 'lucide-react'
import { CommandSummaryData, CardBaseProps } from './types'
import { CardHeader, fmt, fmtInt } from './shared'

interface SmallCapBreadthCardProps extends CardBaseProps {
  data: CommandSummaryData['breadth']
}

function getSmaColor(val: number | null): string {
  if (val == null) return 'bg-gray-700'
  if (val >= 70) return 'bg-emerald-500'
  if (val >= 40) return 'bg-amber-500'
  return 'bg-red-500'
}

export default function SmallCapBreadthCard({ data, expanded, onToggle }: SmallCapBreadthCardProps) {
  const total = (data.advancing || 0) + (data.declining || 0)
  const pctGreen = data.pct_green ?? (total > 0 ? (data.advancing / total) * 100 : 50)

  const smaItems = [
    { label: '20D', val: data.above_20sma_pct ?? null },
    { label: '50D', val: data.above_50sma_pct ?? null },
    { label: '200D', val: data.above_200sma_pct ?? null },
  ]

  return (
    <div className="bg-[#0D1218] border border-border-subtle p-3.5 shadow-sm flex flex-col justify-between hover:border-gray-700 transition-colors">
      <div>
        <CardHeader
          icon={Activity}
          title="Small-Cap Breadth"
          expanded={expanded}
          onToggle={onToggle}
        />

        {/* Hero A/D Ratio & Status */}
        <div className="flex items-center justify-between mb-3">
          <div className={`text-xl font-mono font-black tracking-tight leading-none ${data.is_bullish ? 'text-[#00ff00]' : 'text-gray-300'}`}>
            {data.ad_ratio_str}
          </div>
          <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider ${
            data.is_bullish ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-gray-800 text-gray-400 border border-gray-700'
          }`}>
            {data.status}
          </span>
        </div>

        {/* Crisp Dual-Color Progress Line */}
        <div className="space-y-1 font-mono text-[10px] tabular-nums">
          <div className="w-full h-1.5 bg-[#131B24] border border-border-subtle flex overflow-hidden">
            <div
              className="h-full bg-emerald-500 transition-all duration-700"
              style={{ width: `${Math.min(100, Math.max(0, pctGreen))}%` }}
            />
            <div
              className="h-full bg-red-500 transition-all duration-700"
              style={{ width: `${Math.min(100, Math.max(0, 100 - pctGreen))}%` }}
            />
          </div>
          <div className="flex justify-between text-[10px] text-gray-400 pt-0.5">
            <span className="text-emerald-400 font-medium">▲ {fmtInt(data.advancing)} Adv ({pctGreen.toFixed(0)}%)</span>
            <span className="text-red-400 font-medium">▼ {fmtInt(data.declining)} Dec</span>
          </div>
        </div>

        {/* Participation Spectrum lines */}
        <div className="mt-2.5 pt-2 border-t border-border-subtle space-y-1.5 font-mono text-[10px] tabular-nums">
          <div className="text-gray-500 uppercase font-bold tracking-wider text-[9px]">
            Stocks Above Moving Averages
          </div>
          {smaItems.map(({ label, val }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="w-8 text-gray-400 font-bold">{label}</span>
              <div className="flex-1 h-1.5 bg-[#131B24] border border-border-subtle overflow-hidden">
                <div
                  className={`h-full ${getSmaColor(val)} transition-all duration-500`}
                  style={{ width: `${val ?? 0}%` }}
                />
              </div>
              <span className="w-9 text-right font-semibold text-gray-300">
                {val != null ? `${val.toFixed(0)}%` : '—'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Expanded Internals Drawer */}
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? 'max-h-48 opacity-100 mt-2.5 pt-2 border-t border-border-subtle' : 'max-h-0 opacity-0'}`}>
        <div className="font-mono text-[10px] space-y-1.5 tabular-nums">
          <div className="text-gray-500 uppercase font-bold tracking-wider text-[9px]">Market Internals</div>

          <div className="flex justify-between text-gray-400">
            <span>Up / Down Volume Ratio</span>
            <span className="font-bold text-gray-200">
              {data.up_down_vol_ratio != null ? `${fmt(data.up_down_vol_ratio, 1)}x` : '—'}
            </span>
          </div>

          {data.net_new_highs != null && (
            <div className="flex justify-between text-gray-400">
              <span>Net New Highs (52W)</span>
              <span className={`font-bold ${data.net_new_highs >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {data.net_new_highs >= 0 ? '+' : ''}{data.net_new_highs}
              </span>
            </div>
          )}

          {data.high_low_index != null && (
            <div className="flex justify-between text-gray-400">
              <span>High-Low Index</span>
              <span className="font-bold text-gray-200">{data.high_low_index.toFixed(0)} / 100</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
