'use client'

import React from 'react'
import { MTFInPlayItem } from '@/lib/api'

interface MTFScannerWidgetProps {
  items: MTFInPlayItem[]
  onSelectTicker?: (ticker: string) => void
}

export const MTFScannerWidget: React.FC<MTFScannerWidgetProps> = ({ items, onSelectTicker }) => {
  if (!items || items.length === 0) {
    return (
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4 text-center text-slate-400 text-xs">
        <span className="font-semibold text-slate-300">MTF S/R Scanner:</span> No stocks currently testing levels (Score ≥ 50).
      </div>
    )
  }

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <h3 className="text-sm font-bold text-slate-100 tracking-wide">
            MTF S/R Momentum Scanner <span className="text-xs text-slate-400 font-normal">({items.length} In Play)</span>
          </h3>
        </div>
        <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
          60s Live
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {items.map((item) => {
          const isHighConviction = item.score >= 75
          const isCoincident = item.is_coincident

          let badgeColor = 'bg-amber-500/20 text-amber-300 border-amber-500/40'
          if (isHighConviction) {
            badgeColor = 'bg-rose-500/20 text-rose-300 border-rose-500/40'
          }

          return (
            <div
              key={item.ticker}
              onClick={() => onSelectTicker?.(item.ticker)}
              className={`cursor-pointer border rounded-md p-3 transition-all duration-150 hover:border-sky-500/60 ${
                isHighConviction ? 'bg-rose-950/20 border-rose-800/40' : 'bg-slate-800/40 border-slate-700/60'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="font-mono font-bold text-slate-100 text-sm">{item.ticker}</span>
                  <span className="text-xs text-slate-400 font-mono">${item.price.toFixed(2)}</span>
                </div>

                <div className="flex items-center space-x-1.5">
                  {isCoincident && (
                    <span
                      title="Coincident Level: 5m S/R aligns with Daily S/R"
                      className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40"
                    >
                      ⚡ CONFLUENCE
                    </span>
                  )}
                  <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${badgeColor}`}>
                    {item.score} pts
                  </span>
                </div>
              </div>

              {item.sr_price && (
                <div className="mt-1.5 text-xs text-slate-300 flex items-center justify-between font-mono">
                  <span className="text-slate-400 text-[11px]">{item.sr_type} LEVEL:</span>
                  <span>${item.sr_price.toFixed(2)}</span>
                </div>
              )}

              <div className="mt-2 flex flex-wrap gap-1">
                {item.signals.map((sig) => (
                  <span
                    key={sig}
                    className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700"
                  >
                    {sig}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
