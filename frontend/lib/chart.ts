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
  ema_9?:   LinePt[]
  ema_20?:  LinePt[]
  ema_50?:  LinePt[]
  vwap?:    LinePt[]
  ema_21?:  LinePt[]
  ema_55?:  LinePt[]
  ema_100?: LinePt[]
}

export const CHART_BG       = '#000000'
export const GRID_COLOR     = '#222222' // Muted dark grid
export const TEXT_COLOR     = '#8e8e8e'
export const UP_COLOR       = '#26a69a' // Mellow bullish teal-green (TradingView standard)
export const DOWN_COLOR     = '#ef5350' // Mellow bearish soft crimson (TradingView standard)
export const UP_VOL_COLOR   = 'rgba(38, 166, 154, 0.35)'
export const DOWN_VOL_COLOR = 'rgba(239, 83, 80, 0.35)'
export const EMA9_COL       = '#38bdf8' // Sky Blue (EMA 9)
export const EMA20_COL      = '#f59e0b' // Amber / Gold (EMA 20)
export const EMA50_COL      = '#ab47bc' // Purple (EMA 50)
export const EMA21_COL      = '#f59e0b'
export const EMA100_COL     = '#ec4899' // Pink
export const VWAP_COL       = '#ffffff' // White (VWAP)

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
    ohlcv:   data.ohlcv   ? data.ohlcv.map(x => ({ ...x, time: shiftTime(x.time) }))   : [],
    volume:  data.volume  ? data.volume.map(x => ({ ...x, time: shiftTime(x.time) })) : [],
    ema_9:   data.ema_9   ? data.ema_9.map(x => ({ ...x, time: shiftTime(x.time) }))   : [],
    ema_20:  data.ema_20  ? data.ema_20.map(x => ({ ...x, time: shiftTime(x.time) }))  : [],
    vwap:    data.vwap    ? data.vwap.map(x => ({ ...x, time: shiftTime(x.time) }))    : [],
    ema_21:  data.ema_21  ? data.ema_21.map(x => ({ ...x, time: shiftTime(x.time) }))  : [],
    ema_50:  data.ema_50  ? data.ema_50.map(x => ({ ...x, time: shiftTime(x.time) }))  : [],
    ema_100: data.ema_100 ? data.ema_100.map(x => ({ ...x, time: shiftTime(x.time) })) : [],
  }
}

/**
 * Calculate Exponential Moving Average (EMA) for a given span.
 */
export function calcEMA(bars: OhlcBar[], span: number): LinePt[] {
  if (!bars || bars.length === 0) return []
  const k = 2 / (span + 1)
  let ema = bars[0].close
  const result: LinePt[] = [{ time: bars[0].time, value: roundTo(ema, 4) }]
  for (let i = 1; i < bars.length; i++) {
    ema = bars[i].close * k + ema * (1 - k)
    result.push({ time: bars[i].time, value: roundTo(ema, 4) })
  }
  return result
}

/**
 * Calculate Simple Moving Average (SMA) for a given window.
 */
export function calcSMA(bars: OhlcBar[], window: number): LinePt[] {
  if (!bars || bars.length === 0) return []
  const result: LinePt[] = []
  let sum = 0
  for (let i = 0; i < bars.length; i++) {
    sum += bars[i].close
    if (i >= window) {
      sum -= bars[i - window].close
    }
    const count = Math.min(i + 1, window)
    result.push({ time: bars[i].time, value: roundTo(sum / count, 4) })
  }
  return result
}

function roundTo(val: number, decimals: number): number {
  const factor = Math.pow(10, decimals)
  return Math.round(val * factor) / factor
}
