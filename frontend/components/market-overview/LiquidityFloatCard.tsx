'use client'

import React from 'react'
import { Gauge } from 'lucide-react'
import { CommandSummaryData, CardBaseProps } from './types'
import { CardHeader, fmt } from './shared'

interface LiquidityFloatCardProps extends CardBaseProps {
  data: CommandSummaryData['liquidity']
}

function getFloatThemeStyle(theme: string) {
  if (theme.includes('MICRO'))
    return 'bg-red-custom/15 text-red-custom border-red-custom/30'
  if (theme.includes('MID'))
    return 'bg-amber-custom/15 text-amber-custom border-amber-custom/30'
  return 'bg-info-custom/15 text-info-custom border-info-custom/30'
}

const BUCKET_COLORS: Record<string, string> = {
  Micro: 'bg-violet-500',
  Mid: 'bg-sky-500',
  Large: 'bg-emerald-500',
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
    <div className="bg-[#0D1218] border border-border-subtle p-3 shadow-sm flex flex-col justify-between transition-all duration-300">
      <div>
        <CardHeader
          icon={Gauge}
          title="Liquidity & Float"
          expanded={expanded}
          onToggle={onToggle}
        />

        {/* Hero RVOL & Status */}
        <div className="flex items-baseline justify-between mb-1">
          <div
            className={`text-2xl font-mono font-black tracking-tight leading-none ${data.is_high ? 'text-[#00ff00]' : 'text-gray-300'}`}
          >
            {fmt(data.avg_rvol_top5, 1)}x
          </div>
          <span className={`px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider ${
            data.is_high ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-gray-800 text-gray-400'
          }`}>
            {data.status}
          </span>
        </div>

        <div className="text-[10px] font-mono text-gray-500 mb-2">
          Top-5 Avg RVOL · Median {data.median_rvol != null ? `${fmt(data.median_rvol, 1)}x` : '—'}
        </div>

        {/* Float Profile Bar Chart */}
        <div className="my-2 space-y-1.5 font-mono text-[10px]">
          <div className="flex items-center justify-between">
            <span className="text-gray-500 font-bold uppercase tracking-wider">Float Profile</span>
            <span className={`px-1.5 py-0.5 text-[9px] font-bold uppercase border ${getFloatThemeStyle(data.float_theme)}`}>
              {data.float_theme}
            </span>
          </div>

          {/* Stacked Float Proportional Bar */}
          <div className="w-full h-2 bg-[#131B24] border border-border-subtle flex overflow-hidden">
            <div
              className={`h-full ${BUCKET_COLORS.Micro} transition-all duration-700`}
              style={{ width: `${(microCount / totalFloat) * 100}%` }}
              title={`Micro: ${microCount}`}
            />
            <div
              className={`h-full ${BUCKET_COLORS.Mid} transition-all duration-700`}
              style={{ width: `${(midCount / totalFloat) * 100}%` }}
              title={`Mid: ${midCount}`}
            />
            <div
              className={`h-full ${BUCKET_COLORS.Large} transition-all duration-700`}
              style={{ width: `${(largeCount / totalFloat) * 100}%` }}
              title={`Large: ${largeCount}`}
            />
          </div>

          <div className="flex justify-between text-[9px] text-gray-400">
            <span className="text-violet-400">Micro (&lt;2M): {microCount}</span>
            <span className="text-sky-400">Mid (2-20M): {midCount}</span>
            <span className="text-emerald-400">Large (&gt;20M): {largeCount}</span>
          </div>
        </div>
      </div>

      {/* Expanded Sector Rotation Breakdown */}
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? 'max-h-56 opacity-100 mt-2 pt-2 border-t border-border-subtle' : 'max-h-0 opacity-0'}`}>
        <div className="font-mono text-[10px] space-y-1.5">
          <div className="text-gray-500 uppercase font-bold tracking-wider mb-1">Top Sector Clusters</div>
          {topSectors.length > 0 ? (
            topSectors.map(([sector, count], i) => (
              <div key={sector} className="flex items-center justify-between text-gray-300 py-0.5">
                <div className="flex items-center gap-1.5 truncate">
                  <span className="text-gray-500 font-bold text-[9px]">#{i + 1}</span>
                  <span className="truncate">{sector}</span>
                </div>
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
