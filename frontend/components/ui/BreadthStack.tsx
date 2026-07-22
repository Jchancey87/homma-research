'use client'

import React from 'react'

interface BreadthStackProps {
  sma20: number | null
  sma50: number | null
  sma200: number | null
}

function getBarColor(val: number | null): string {
  if (val == null) return 'bg-gray-800'
  if (val >= 70) return 'bg-emerald-500'
  if (val >= 40) return 'bg-amber-500'
  return 'bg-red-500'
}

export default function BreadthStack({ sma20, sma50, sma200 }: BreadthStackProps) {
  const items = [
    { label: '20D', val: sma20 },
    { label: '50D', val: sma50 },
    { label: '200D', val: sma200 },
  ]

  return (
    <div className="space-y-1.5 w-full font-mono text-[10px]">
      {items.map(({ label, val }) => {
        const pct = val == null ? 0 : Math.max(0, Math.min(100, val))
        return (
          <div key={label} className="flex items-center gap-2">
            <span className="w-8 shrink-0 text-gray-400 font-bold">{label}</span>
            <div className="flex-1 relative h-2 bg-[#131B24] border border-border-subtle rounded-none overflow-hidden">
              {/* Threshold indicator lines at 30% and 70% */}
              <div className="absolute top-0 bottom-0 left-[30%] w-[1px] bg-gray-700/50 z-10" />
              <div className="absolute top-0 bottom-0 left-[70%] w-[1px] bg-gray-700/50 z-10" />
              <div
                className={`h-full transition-all duration-700 ease-out ${getBarColor(val)}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="w-10 text-right font-bold text-gray-200">
              {val != null ? `${val.toFixed(0)}%` : '—'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
