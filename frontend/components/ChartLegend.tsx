'use client'

/**
 * ChartLegend
 *
 * Floating OHLCV + indicator legend rendered as an absolute-positioned
 * overlay in the top-left of the chart container. Driven by the
 * `useChartLegend` hook's `legend` state; renders nothing when null
 * (crosshair not on chart).
 *
 * Visual goal: replicates the trading-vue-js crosshair data panel —
 * color-coded OHLC values + live indicator readings at a glance.
 */

import { EMA9_COL, EMA20_COL, EMA50_COL, VWAP_COL } from '@/lib/chart'
import type { LegendBar } from '@/lib/useChartLegend'

interface Props {
  legend: LegendBar | null
  /** Show VWAP row. Default true. */
  showVwap?: boolean
  /** Show EMA rows. Default true. */
  showEmas?: boolean
}

function val(n: number, decimals = 2) {
  return n.toFixed(decimals)
}

export default function ChartLegend({ legend, showVwap = true, showEmas = true }: Props) {
  if (!legend) return null

  const isUp     = legend.close >= legend.open
  const closeCol = isUp ? '#26a69a' : '#ef5350'
  const chgSign  = legend.changePct >= 0 ? '+' : ''

  return (
    <div
      className="absolute top-7 left-1.5 z-20 pointer-events-none select-none"
      style={{ fontFamily: "JetBrains Mono, Consolas, 'Roboto Mono', ui-monospace, monospace" }}
    >
      <div
        className="flex flex-col gap-[2px] px-2 py-1.5 rounded-none"
        style={{ background: 'rgba(0,0,0,0.82)', border: '1px solid #2a2a2a' }}
      >
        {/* Time */}
        <div className="text-[9px] text-gray-500 font-bold tracking-wider mb-0.5">
          {legend.time}
        </div>

        {/* OHLC row */}
        <div className="flex items-center gap-2 text-[9.5px] font-bold leading-none">
          <span className="text-gray-500">O</span>
          <span className="text-gray-300">{val(legend.open)}</span>
          <span className="text-gray-500">H</span>
          <span className="text-[#26a69a]">{val(legend.high)}</span>
          <span className="text-gray-500">L</span>
          <span className="text-[#ef5350]">{val(legend.low)}</span>
          <span className="text-gray-500">C</span>
          <span style={{ color: closeCol }}>{val(legend.close)}</span>
          <span
            className="text-[8.5px] font-bold ml-0.5"
            style={{ color: closeCol }}
          >
            {chgSign}{val(legend.changePct, 2)}%
          </span>
        </div>

        {/* Indicator rows */}
        {showEmas && (legend.ema9 != null || legend.ema20 != null || legend.ema50 != null) && (
          <div className="flex items-center gap-2 text-[8.5px] leading-none mt-[3px]">
            {legend.ema9 != null && (
              <>
                <span className="font-bold" style={{ color: EMA9_COL }}>EMA9</span>
                <span className="text-gray-300">{val(legend.ema9)}</span>
              </>
            )}
            {legend.ema20 != null && (
              <>
                <span className="font-bold" style={{ color: EMA20_COL }}>EMA20</span>
                <span className="text-gray-300">{val(legend.ema20)}</span>
              </>
            )}
            {legend.ema50 != null && (
              <>
                <span className="font-bold" style={{ color: EMA50_COL }}>EMA50</span>
                <span className="text-gray-300">{val(legend.ema50)}</span>
              </>
            )}
          </div>
        )}

        {showVwap && legend.vwap != null && (
          <div className="flex items-center gap-2 text-[8.5px] leading-none">
            <span className="font-bold" style={{ color: VWAP_COL }}>VWAP</span>
            <span className="text-gray-300">{val(legend.vwap)}</span>
          </div>
        )}
      </div>
    </div>
  )
}
