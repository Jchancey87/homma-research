'use client'

import React from 'react'
import { AlertReviewSummary } from '@/lib/api'
import { ShieldAlert, Zap, TrendingUp, Crosshair } from 'lucide-react'

interface Props {
  summary: AlertReviewSummary | null
  selectedDate: string
  availableDates: string[]
  onDateChange: (date: string) => void
}

export default function AlertReviewSummaryBar({
  summary,
  selectedDate,
  availableDates,
  onDateChange,
}: Props) {
  if (!summary) {
    return (
      <div className="bg-[#0a0a0a] border border-[#222222] p-4 text-xs font-mono text-gray-500 animate-pulse">
        Loading summary stats...
      </div>
    )
  }

  const {
    total_alerts,
    unique_symbols,
    tier_counts,
    alert_type_counts,
    suppressed_count,
    mfe_15m_hit_rate,
    avg_mae_15m,
  } = summary

  return (
    <div className="bg-[#080808] border border-[#262626] p-3 font-mono text-xs flex flex-col gap-3">
      {/* Top Row: Date Selector & Key Metrics */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1f1f1f] pb-2.5">
        <div className="flex items-center gap-2">
          <label className="text-gray-400 font-bold uppercase tracking-wider text-[11px] flex items-center gap-1.5">
            <Crosshair size={14} className="text-[#00ff00]" />
            Alert Review Date:
          </label>
          <select
            value={selectedDate}
            onChange={(e) => onDateChange(e.target.value)}
            className="bg-black border border-[#333333] text-white px-2 py-1 text-xs font-mono font-bold focus:outline-none focus:border-[#00ff00]"
          >
            {availableDates.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
            {!availableDates.includes(selectedDate) && (
              <option value={selectedDate}>{selectedDate}</option>
            )}
          </select>
        </div>

        {/* Metric Badges */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 bg-[#121212] px-2.5 py-1 border border-[#222222]">
            <Zap size={13} className="text-yellow-400" />
            <span className="text-gray-400">Total Alerts:</span>
            <span className="text-white font-bold">{total_alerts}</span>
          </div>

          <div className="flex items-center gap-1.5 bg-[#121212] px-2.5 py-1 border border-[#222222]">
            <span className="text-gray-400">Symbols:</span>
            <span className="text-white font-bold">{unique_symbols}</span>
          </div>

          <div className="flex items-center gap-1.5 bg-[#121212] px-2.5 py-1 border border-[#222222]">
            <TrendingUp size={13} className="text-[#00ff00]" />
            <span className="text-gray-400">15m MFE Hit Rate:</span>
            <span
              className={`font-black ${
                mfe_15m_hit_rate >= 60.0
                  ? 'text-[#00ff00]'
                  : mfe_15m_hit_rate >= 40.0
                  ? 'text-yellow-400'
                  : 'text-[#ff003c]'
              }`}
            >
              {mfe_15m_hit_rate.toFixed(1)}%
            </span>
          </div>

          <div className="flex items-center gap-1.5 bg-[#121212] px-2.5 py-1 border border-[#222222]">
            <span className="text-gray-400">Avg 15m MAE:</span>
            <span className="text-[#ff003c] font-bold">{avg_mae_15m.toFixed(2)}%</span>
          </div>

          <div className="flex items-center gap-1.5 bg-[#121212] px-2.5 py-1 border border-[#222222]">
            <ShieldAlert size={13} className="text-gray-500" />
            <span className="text-gray-400">Suppressed:</span>
            <span className="text-gray-300 font-bold">{suppressed_count}</span>
          </div>
        </div>
      </div>

      {/* Bottom Row: Tiers & Alert Types Breakdown */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-[11px]">
        {/* Tier Distribution */}
        <div className="flex items-center gap-2">
          <span className="text-gray-400 font-bold">Priority Tiers:</span>
          <span className="px-2 py-0.5 bg-red-950/40 border border-red-800/40 text-red-400 font-bold">
            T1: {tier_counts['Tier 1'] || 0}
          </span>
          <span className="px-2 py-0.5 bg-yellow-950/40 border border-yellow-800/40 text-yellow-400 font-bold">
            T2: {tier_counts['Tier 2'] || 0}
          </span>
          <span className="px-2 py-0.5 bg-blue-950/40 border border-blue-800/40 text-blue-400 font-bold">
            T3: {tier_counts['Tier 3'] || 0}
          </span>
        </div>

        {/* Alert Type Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-gray-400 font-bold mr-1">Types:</span>
          {Object.keys(alert_type_counts).length === 0 ? (
            <span className="text-gray-600">None</span>
          ) : (
            Object.entries(alert_type_counts).map(([type, count]) => (
              <span
                key={type}
                className="px-1.5 py-0.5 bg-[#161616] border border-[#2a2a2a] text-gray-300 font-mono text-[10px]"
              >
                {type}: <strong className="text-white">{count}</strong>
              </span>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
