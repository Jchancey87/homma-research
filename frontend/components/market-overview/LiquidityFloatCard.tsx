'use client'

import React from 'react'
import { Gauge } from 'lucide-react'
import { CommandSummaryData, CardBaseProps } from './types'
import { CardHeader, fmt } from './shared'

interface LiquidityFloatCardProps extends CardBaseProps {
  data: CommandSummaryData['liquidity']
}

export default function LiquidityFloatCard({ data, expanded, onToggle }: LiquidityFloatCardProps) {
  const topSectors = Object.entries(data.sector_clusters || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5)

  const floatCounts = data.float_counts || {}
  const microCount = floatCounts['MICRO-FLOAT (<2M)'] || 0
  const midCount = floatCounts['MID-FLOAT (2M-20M)'] || 0
  const largeCount = floatCounts['LARGE-FLOAT (>20M)'] || 0
  const totalFloat = microCount + midCount + largeCount || 1

  return (
    <div className="bg-[#0D1218] border border-border-subtle p-3.5 shadow-sm flex flex-col justify-between hover:border-gray-700 transition-colors">
      <div>
        <CardHeader
          icon={Gauge}
          title="Liquidity & Float"
          expanded={expanded}
          onToggle={onToggle}
        />

        {/* Hero RVOL & Status */}
        <div className="flex items-center justify-between mb-3">
          <div className={`text-xl font-mono font-black tracking-tight leading-none ${data.is_high ? 'text-[#00ff00]' : 'text-gray-300'}`}>
            {fmt(data.avg_rvol_top5, 1)}x <span className="text-[10px] text-gray-500 font-normal">RVOL</span>
          </div>
          <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider ${
            data.is_high ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-gray-800 text-gray-400 border border-gray-700'
          }`}>
            {data.status}
          </span>
        </div>

        {/* Stacked Float Profile Segment */}
        <div className="space-y-1.5 font-mono text-[10px] tabular-nums">
          <div className="flex items-center justify-between text-gray-400 text-[9px]">
            <span className="text-gray-500 font-bold uppercase tracking-wider">Float Profile</span>
            <span className="text-amber-400 font-bold uppercase">{data.float_theme}</span>
          </div>

          <div className="w-full h-1.5 bg-[#131B24] border border-border-subtle flex overflow-hidden">
            <div
              className="h-full bg-violet-500 transition-all duration-700"
              style={{ width: `${(microCount / totalFloat) * 100}%` }}
              title={`Micro: ${microCount}`}
            />
            <div
              className="h-full bg-sky-500 transition-all duration-700"
              style={{ width: `${(midCount / totalFloat) * 100}%` }}
              title={`Mid: ${midCount}`}
            />
            <div
              className="h-full bg-emerald-500 transition-all duration-700"
              style={{ width: `${(largeCount / totalFloat) * 100}%` }}
              title={`Large: ${largeCount}`}
            />
          </div>

          <div className="flex justify-between text-[9px] text-gray-400 pt-0.5">
            <span className="text-violet-400">Micro (&lt;2M): {microCount}</span>
            <span className="text-sky-400">Mid (2-20M): {midCount}</span>
            <span className="text-emerald-400">Large: {largeCount}</span>
          </div>
        </div>

        {/* Median RVOL Sub-Line */}
        <div className="mt-2.5 pt-2 border-t border-border-subtle flex justify-between font-mono text-[10px] text-gray-400 tabular-nums">
          <span className="text-gray-500">Median Screener RVOL</span>
          <span className="font-bold text-gray-200">{data.median_rvol != null ? `${fmt(data.median_rvol, 1)}x` : '—'}</span>
        </div>
      </div>

      {/* Expanded Sector Clusters */}
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? 'max-h-48 opacity-100 mt-2.5 pt-2 border-t border-border-subtle' : 'max-h-0 opacity-0'}`}>
        <div className="font-mono text-[10px] space-y-1 tabular-nums">
          <div className="text-gray-500 uppercase font-bold tracking-wider text-[9px] mb-1">Top Active Sectors</div>
          {topSectors.length > 0 ? (
            topSectors.map(([sector, count], i) => (
              <div key={sector} className="flex items-center justify-between text-gray-300 py-0.5">
                <span className="text-gray-400 truncate">#{i + 1} {sector}</span>
                <span className="font-bold text-emerald-400 shrink-0 ml-2">{count}x</span>
              </div>
            ))
          ) : (
            <div className="text-gray-500 italic">No active sector clusters</div>
          )}
        </div>
      </div>
    </div>
  )
}
