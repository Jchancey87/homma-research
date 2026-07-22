'use client'

import React from 'react'

interface MiniGaugeProps {
  value: number | null        // 0-100
  label?: string
  size?: number               // default 48
  colorScale?: 'green-red' | 'red-green' | 'amber'
  thickness?: number          // default 4
  showValue?: boolean
}

export default function MiniGauge({
  value,
  label,
  size = 48,
  colorScale = 'green-red',
  thickness = 4,
  showValue = true,
}: MiniGaugeProps) {
  const val = value == null ? 0 : Math.max(0, Math.min(100, value))
  const radius = (size - thickness) / 2
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (val / 100) * circumference

  let strokeColor = '#10b981' // green
  if (colorScale === 'green-red') {
    if (val > 70) strokeColor = '#ef4444'      // red
    else if (val > 40) strokeColor = '#f59e0b' // amber
    else strokeColor = '#10b981'               // green
  } else if (colorScale === 'red-green') {
    if (val > 70) strokeColor = '#10b981'      // green
    else if (val > 40) strokeColor = '#f59e0b' // amber
    else strokeColor = '#ef4444'               // red
  } else if (colorScale === 'amber') {
    strokeColor = '#f59e0b'
  }

  return (
    <div className="inline-flex flex-col items-center justify-center select-none" title={label ? `${label}: ${val}%` : `${val}%`}>
      <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="#1f2937"
            strokeWidth={thickness}
            fill="transparent"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={strokeColor}
            strokeWidth={thickness}
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        </svg>
        {showValue && (
          <span className="absolute font-mono text-[10px] font-bold text-gray-200">
            {value != null ? `${Math.round(val)}` : '—'}
          </span>
        )}
      </div>
      {label && (
        <span className="text-[9px] font-mono text-gray-500 uppercase tracking-tight mt-0.5">
          {label}
        </span>
      )}
    </div>
  )
}
