'use client'

import React from 'react'

export interface MacroTileData {
  label: string
  value: number | null
  chg_pct?: number | null
  prefix?: string
  suffix?: string
  decimals?: number
}

interface MacroStripProps {
  tiles?: MacroTileData[]
}

function chgColor(v: number | null) {
  if (v == null) return 'text-gray-500'
  return v > 0 ? 'text-[#00ff00]' : v < 0 ? 'text-[#ff003c]' : 'text-gray-400'
}

function fmtVal(val: number | null, decimals = 2): string {
  if (val == null) return '—'
  return val.toFixed(decimals)
}

export default function MacroStrip({ tiles }: MacroStripProps) {
  const defaultTiles: MacroTileData[] = [
    { label: 'US 10Y', value: 4.25, chg_pct: -0.5, suffix: '%' },
    { label: 'DXY', value: 104.20, chg_pct: 0.1 },
    { label: 'CRUDE', value: 78.50, chg_pct: -1.2, prefix: '$' },
    { label: 'GOLD', value: 182.30, chg_pct: 0.3, prefix: '$' },
    { label: 'PUT/CALL', value: 0.85, decimals: 2 },
  ]

  const list = tiles && tiles.length > 0 ? tiles : defaultTiles

  return (
    <div className="w-full bg-[#0D1218] border border-border-subtle p-2 flex items-center justify-between gap-2 overflow-x-auto scrollbar-none font-mono text-[11px]">
      {list.map((t, idx) => (
        <div
          key={t.label}
          className={`flex items-center gap-2 px-3 py-1 ${
            idx < list.length - 1 ? 'border-r border-border-subtle' : ''
          } flex-1 min-w-[120px] justify-between`}
        >
          <span className="text-gray-500 font-bold text-[10px] tracking-wider">{t.label}</span>
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-gray-200">
              {t.prefix}{fmtVal(t.value, t.decimals ?? 2)}{t.suffix}
            </span>
            {t.chg_pct != null && (
              <span className={`text-[10px] font-medium ${chgColor(t.chg_pct)}`}>
                {t.chg_pct > 0 ? '+' : ''}{t.chg_pct.toFixed(1)}%
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
