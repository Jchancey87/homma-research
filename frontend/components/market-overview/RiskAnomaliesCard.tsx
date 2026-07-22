'use client'

import React from 'react'
import Link from 'next/link'
import { AlertOctagon } from 'lucide-react'
import { CommandSummaryData, CardBaseProps } from './types'
import { CardHeader, RISK_STYLE, fmt } from './shared'
import MiniGauge from '../ui/MiniGauge'

interface RiskAnomaliesCardProps extends CardBaseProps {
  data: CommandSummaryData['risk']
  lastUpdated?: Date | null
  onRefresh?: () => void
  loading?: boolean
}

export default function RiskAnomaliesCard({
  data,
  lastUpdated,
  onRefresh,
  loading,
  expanded,
  onToggle,
}: RiskAnomaliesCardProps) {
  const riskStyle = RISK_STYLE[data.tag] ?? RISK_STYLE.normal

  return (
    <div className="bg-[#0D1218] border border-border-subtle p-3 shadow-sm flex flex-col justify-between transition-all duration-300">
      <div>
        <CardHeader
          icon={AlertOctagon}
          title="Risk & Anomalies"
          expanded={expanded}
          onToggle={onToggle}
          showRefresh
          onRefresh={onRefresh}
          loading={loading}
        />

        {/* Hero Risk Banner */}
        <div className={`p-2 border-l-4 mb-2.5 ${riskStyle.bg} ${riskStyle.border}`}>
          <div className="flex items-center justify-between font-mono font-black text-sm uppercase tracking-wider">
            <span className={riskStyle.text}>{data.tag.toUpperCase()} RISK</span>
            {data.anomaly_count != null && data.anomaly_count > 0 && (
              <span className="text-[10px] px-1.5 py-0.5 bg-amber-500/20 text-amber-400 font-bold rounded-none">
                {data.anomaly_count} ANOMALIES
              </span>
            )}
          </div>
          <div className="text-[10px] font-mono text-gray-400 mt-0.5">
            VIX {data.vix_value != null ? fmt(data.vix_value, 1) : '—'} {data.vix_direction === 'up' ? '↑' : '↓'} · {data.halt_count} Active Halts
          </div>
        </div>

        {/* Active Risk Signals */}
        <div className="my-2 space-y-1 font-mono text-[10px]">
          <div className="text-gray-500 font-bold uppercase tracking-wider">Active Signals</div>
          {data.signals && data.signals.length > 0 ? (
            <div className="space-y-0.5">
              {data.signals.map((sig, i) => (
                <div key={i} className="text-amber-400 font-medium flex items-center gap-1">
                  <span>•</span>
                  <span>{sig}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-500 italic">No active risk signals</div>
          )}
        </div>

        {/* Halted Tickers */}
        {data.halt_tickers && data.halt_tickers.length > 0 && (
          <div className="mt-2.5 pt-2 border-t border-border-subtle font-mono text-[10px]">
            <div className="flex items-center justify-between text-gray-500 mb-1">
              <span className="font-bold uppercase tracking-wider">Active Halts ({data.halt_count})</span>
              {data.halt_rate_per_hour != null && (
                <span>{fmt(data.halt_rate_per_hour, 1)}/hr</span>
              )}
            </div>
            <div className="flex items-center gap-1 flex-wrap">
              {data.halt_tickers.slice(0, 4).map(ticker => (
                <span
                  key={ticker}
                  className="px-1.5 py-0.5 text-[9px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30"
                >
                  {ticker}
                </span>
              ))}
              {data.halt_tickers.length > 4 && (
                <span className="text-[9px] text-gray-500 font-bold">+{data.halt_tickers.length - 4}</span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Expanded Anomalies & Confluence Score */}
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? 'max-h-64 opacity-100 mt-3 pt-2 border-t border-border-subtle' : 'max-h-0 opacity-0'}`}>
        <div className="font-mono text-[10px] space-y-2">
          {data.top_anomalies && data.top_anomalies.length > 0 && (
            <div>
              <div className="text-gray-500 uppercase font-bold tracking-wider mb-1">Top Volume Anomalies</div>
              <div className="space-y-1">
                {data.top_anomalies.map(a => (
                  <Link
                    key={a.ticker}
                    href={`/research?ticker=${a.ticker}`}
                    className="flex items-center justify-between p-1 bg-[#131B24] hover:bg-[#192431] transition-colors border border-border-subtle"
                  >
                    <span className="font-bold text-white">{a.ticker}</span>
                    <span className="text-[#00ff00]">+{a.gap_pct}%</span>
                    <span className="text-amber-400 font-bold">{a.rvol}x RVOL</span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {data.confluence_score != null && (
            <div className="flex items-center justify-between pt-1">
              <span className="text-gray-400">Confluence Risk Score</span>
              <MiniGauge value={(data.confluence_score / 5) * 100} size={36} colorScale="amber" showValue={false} />
            </div>
          )}

          {lastUpdated && (
            <div className="text-[9px] text-gray-600 pt-1">
              Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
