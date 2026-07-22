'use client'

import React from 'react'
import { Activity } from 'lucide-react'
import { CommandSummaryData, CardBaseProps } from './types'
import { CardHeader, fmt, fmtInt } from './shared'
import BreadthStack from '../ui/BreadthStack'
import NetHistogram from '../ui/NetHistogram'
import MiniGauge from '../ui/MiniGauge'

interface SmallCapBreadthCardProps extends CardBaseProps {
  data: CommandSummaryData['breadth']
}

export default function SmallCapBreadthCard({ data, expanded, onToggle }: SmallCapBreadthCardProps) {
  const total = (data.advancing || 0) + (data.declining || 0)
  const pctGreen = data.pct_green ?? (total > 0 ? (data.advancing / total) * 100 : 50)

  return (
    <div className="bg-[#0D1218] border border-border-subtle p-3 shadow-sm flex flex-col justify-between transition-all duration-300">
      <div>
        <CardHeader
          icon={Activity}
          title="Small-Cap Breadth"
          expanded={expanded}
          onToggle={onToggle}
        />

        {/* Hero A/D Ratio & Status */}
        <div className="flex items-baseline justify-between mb-1">
          <div className={`text-2xl font-mono font-black tracking-tight leading-none ${data.is_bullish ? 'text-[#00ff00]' : 'text-gray-300'}`}>
            {data.ad_ratio_str}
          </div>
          <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider ${
            data.is_bullish ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-gray-800 text-gray-400'
          }`}>
            {data.status}
          </span>
        </div>

        {/* Visual A/D Bar (Proportional Green / Red Segment) */}
        <div className="my-2 space-y-1 font-mono text-[10px]">
          <div className="w-full h-2 bg-[#131B24] border border-border-subtle flex overflow-hidden">
            <div
              className="h-full bg-[#00ff00] transition-all duration-700 ease-out"
              style={{ width: `${Math.min(100, Math.max(0, pctGreen))}%` }}
            />
            <div
              className="h-full bg-[#ff003c] transition-all duration-700 ease-out"
              style={{ width: `${Math.min(100, Math.max(0, 100 - pctGreen))}%` }}
            />
          </div>
          <div className="flex justify-between text-gray-400">
            <span className="text-[#00ff00]">▲ {fmtInt(data.advancing)} G ({pctGreen.toFixed(0)}%)</span>
            <span className="text-[#ff003c]">▼ {fmtInt(data.declining)} R</span>
          </div>
        </div>

        {/* Participation Spectrum Stack */}
        <div className="mt-3 pt-2 border-t border-border-subtle">
          <div className="text-[10px] font-mono text-gray-500 uppercase font-bold tracking-wider mb-1.5">
            Participation Spectrum (% &gt; SMA)
          </div>
          <BreadthStack
            sma20={data.above_20sma_pct ?? null}
            sma50={data.above_50sma_pct ?? null}
            sma200={data.above_200sma_pct ?? null}
          />
        </div>
      </div>

      {/* Expanded Market Internals */}
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? 'max-h-56 opacity-100 mt-3 pt-2 border-t border-border-subtle' : 'max-h-0 opacity-0'}`}>
        <div className="font-mono text-[10px] space-y-2">
          <div className="text-gray-500 uppercase font-bold tracking-wider">Market Internals</div>

          <div className="flex justify-between text-gray-400">
            <span>Up/Down Volume Ratio</span>
            <span className="font-bold text-gray-200">
              {data.up_down_vol_ratio != null ? `${fmt(data.up_down_vol_ratio, 1)}x` : '—'}
            </span>
          </div>

          {data.net_new_highs != null && (
            <NetHistogram
              value={data.net_new_highs}
              label="Net New Highs (52W)"
              maxScale={50}
            />
          )}

          <div className="flex items-center justify-between pt-1">
            <span className="text-gray-400">High-Low Index</span>
            {data.high_low_index != null ? (
              <MiniGauge value={data.high_low_index} size={36} colorScale="red-green" showValue />
            ) : (
              <span className="text-gray-500">—</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
