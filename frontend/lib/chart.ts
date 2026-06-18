/**
 * Shared chart utilities and types.
 *
 * Source of truth for lightweight-charts time-series types and
 * color palette used by the dashboard's mini-charts and detail charts
 * (LiveGainers modal, alerts page, daily-charts grid).
 *
 * Colors match the original TradeStation-dark terminal theme:
 *   - neon green up / neon red down candles
 *   - cyan EMA 21, yellow EMA 50, magenta EMA 100
 *   - stark dotted grid on black
 */

import type { UTCTimestamp } from 'lightweight-charts'

export interface OhlcBar {
  time:   UTCTimestamp
  open:   number
  high:   number
  low:    number
  close:  number
}

export interface LinePt {
  time:  UTCTimestamp
  value: number
}

export interface HistoPt {
  time:   UTCTimestamp
  value:  number
  color?: string
}

export interface ChartData {
  ohlcv:    OhlcBar[]
  volume:   HistoPt[]
  ema_21:   LinePt[]
  ema_50?:  LinePt[]
  ema_100?: LinePt[]
}

export const CHART_BG   = '#000000'
export const GRID_COLOR = '#444444' // Stark dotted grids
export const TEXT_COLOR = '#8e8e8e'
export const UP_COLOR   = '#00ff00' // Neon bullish green
export const DOWN_COLOR = '#ff003c' // Neon bearish red
export const EMA21_COL  = '#00f0ff'
export const EMA50_COL  = '#ffff00' // Neon yellow
export const EMA100_COL = '#ff00ff' // Neon pink

/**
 * Sort ascending by time and remove duplicate timestamps (keep last occurrence).
 * Used before `setData` to defend against bar merges producing duplicates.
 */
export function dedupSort<T extends { time: UTCTimestamp }>(data: T[]): T[] {
  const map = new Map<number, T>()
  for (const bar of data) map.set(bar.time as number, bar)
  return Array.from(map.values()).sort((a, b) => (a.time as number) - (b.time as number))
}

/**
 * Shift every `time` in the chart payload by `offsetSec` seconds. Used to
 * align UTC bars with the viewer's local timezone when rendering intraday
 * charts server-side as UTC.
 */
export function shiftChartDataTime(data: ChartData, offsetSec: number): ChartData {
  if (offsetSec === 0) return data
  const shiftTime = (t: UTCTimestamp) =>
    (typeof t === 'number' ? (t + offsetSec) as UTCTimestamp : t)
  return {
    ohlcv:   data.ohlcv  ? data.ohlcv.map(x => ({ ...x, time: shiftTime(x.time) }))   : [],
    volume:  data.volume ? data.volume.map(x => ({ ...x, time: shiftTime(x.time) })) : [],
    ema_21:  data.ema_21 ? data.ema_21.map(x => ({ ...x, time: shiftTime(x.time) })) : [],
    ema_50:  data.ema_50 ? data.ema_50.map(x => ({ ...x, time: shiftTime(x.time) })) : [],
    ema_100: data.ema_100 ? data.ema_100.map(x => ({ ...x, time: shiftTime(x.time) })) : [],
  }
}
