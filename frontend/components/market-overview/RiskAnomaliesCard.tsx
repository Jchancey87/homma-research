'use client'

import React from 'react'
import Link from 'next/link'
import { AlertOctagon } from 'lucide-react'
import { CommandSummaryData, CardBaseProps } from './types'
import { CardHeader, fmt } from './shared'

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
  let riskBadgeColor = 'text-info-custom bg-info-custom/10 border-info-custom/20'
  if (data.tag === 'elevated') riskBadgeColor = 'text-amber-400 bg-amber-500/10 border-amber-500/20'
  if (data.tag === 'high') riskBadgeColor = 'text-red-400 bg-red-500/10 border-red-500/20 font-black'

  return (
    <div className="bg-[#0D1218] border border-border-subtle p-3.5 shadow-sm flex flex-col justify-between hover:border-gray-700 transition-colors">
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

        {/* Hero Risk Level & Anomaly Count */}
        <div className="flex items-center justify-between mb-3">
          <div className={`px-2.5 py-1 text-xs font-mono font-bold uppercase tracking-wider border rounded-none ${riskBadgeColor}`}>
            {data.tag} RISK
          </div>
          {data.anomaly_count != null && data.anomaly_count > 0 ? (
            <span className="text-[10px] font-mono text-amber-400 font-bold bg-amber-500/10 px-1.5 py-0.5 border border-amber-500/20">
              {data.anomaly_count} Anomalies
            </span>
          ) : (
            <span className="text-[10px] font-mono text-gray-500">Normal Scan</span>
          )}
        </div>

        {/* Active Risk Signals */}
        <div className="space-y-1 font-mono text-[10px] tabular-nums">
          <div className="text-gray-500 font-bold uppercase tracking-wider text-[9px]">Active Risk Signals</div>
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
            <div className="text-gray-500 italic">No active risk flags</div>
          )}
        </div>

        {/* Halts Row */}
        {data.halt_tickers && data.halt_tickers.length > 0 && (
          <div className="mt-2.5 pt-2 border-t border-border-subtle font-mono text-[10px] tabular-nums">
            <div className="flex items-center justify-between text-gray-500 mb-1">
              <span className="font-bold uppercase tracking-wider text-[9px]">Trading Halts ({data.halt_count})</span>
              {data.halt_rate_per_hour != null && (
                <span className="text-[9px] text-gray-400">{fmt(data.halt_rate_per_hour, 1)}/hr</span>
              )}
            </div>
            <div className="flex items-center gap-1 flex-wrap">
              {data.halt_tickers.slice(0, 4).map(ticker => (
                <span
                  key={ticker}
                  className="px-1.5 py-0.5 text-[9px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20"
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

      {/* Expanded Anomalies Drawer */}
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? 'max-h-52 opacity-100 mt-2.5 pt-2 border-t border-border-subtle' : 'max-h-0 opacity-0'}`}>
        <div className="font-mono text-[10px] space-y-1.5 tabular-nums">
          {data.top_anomalies && data.top_anomalies.length > 0 && (
            <div>
              <div className="text-gray-500 uppercase font-bold tracking-wider text-[9px] mb-1">Top Volume Anomalies</div>
              <div className="space-y-1">
                {data.top_anomalies.map(a => (
                  <Link
                    key={a.ticker}
                    href={`/research?ticker=${a.ticker}`}
                    className="flex items-center justify-between p-1 bg-[#131B24] hover:bg-[#192431] transition-colors border border-border-subtle"
                  >
                    <span className="font-bold text-gray-200">{a.ticker}</span>
                    <span className="text-emerald-400">+{a.gap_pct}%</span>
                    <span className="text-amber-400 font-bold">{a.rvol}x</span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {data.confluence_score != null && (
            <div className="flex items-center justify-between text-gray-400 pt-1">
              <span>Confluence Risk Score</span>
              <span className="font-bold text-amber-400">{data.confluence_score} / 5</span>
            </div>
          )}

          {lastUpdated && (
            <div className="text-[9px] text-gray-600 pt-1 text-right">
              Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
