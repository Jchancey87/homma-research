'use client'

import React from 'react'

interface NetHistogramProps {
  value: number | null
  maxScale?: number
  label?: string
}

export default function NetHistogram({ value, maxScale = 50, label }: NetHistogramProps) {
  const val = value == null ? 0 : value
  const absVal = Math.min(Math.abs(val), maxScale)
  const pct = (absVal / maxScale) * 50 // max 50% left or right

  const isPositive = val >= 0

  return (
    <div className="w-full flex flex-col gap-0.5 font-mono text-[10px]">
      {label && (
        <div className="flex items-center justify-between text-gray-400">
          <span>{label}</span>
          <span className={`font-bold ${isPositive ? 'text-[#00ff00]' : 'text-[#ff003c]'}`}>
            {isPositive ? '+' : ''}{val}
          </span>
        </div>
      )}
      <div className="relative h-2.5 bg-[#131B24] border border-border-subtle overflow-hidden flex items-center">
        {/* Center Zero Line */}
        <div className="absolute top-0 bottom-0 left-1/2 w-[1px] bg-gray-600 z-10" />

        {/* Bar */}
        {isPositive ? (
          <div
            className="h-full bg-[#00ff00] transition-all duration-700 ease-out absolute left-1/2"
            style={{ width: `${pct}%` }}
          />
        ) : (
          <div
            className="h-full bg-[#ff003c] transition-all duration-700 ease-out absolute right-1/2"
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  )
}
