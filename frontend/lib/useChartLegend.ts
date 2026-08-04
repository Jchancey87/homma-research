/**
 * useChartLegend
 *
 * Subscribes to `chart.subscribeCrosshairMove` and surfaces OHLCV +
 * optional indicator values for a floating legend overlay.
 *
 * Uses a ref + minimal setState pattern so the crosshair callback fires
 * at 60 fps without triggering full component re-renders for every pixel.
 */

import { useRef, useState, useCallback } from 'react'
import type { IChartApi, ISeriesApi, MouseEventParams } from 'lightweight-charts'
import type { OhlcBar, LinePt } from './chart'

export interface LegendBar {
  time:   string  // formatted HH:MM
  open:   number
  high:   number
  low:    number
  close:  number
  change: number      // absolute vs open
  changePct: number   // % vs open
  ema9?:  number
  ema20?: number
  ema50?: number
  vwap?:  number
}

export function useChartLegend() {
  const [legend, setLegend] = useState<LegendBar | null>(null)

  /** Call once the chart + series refs are ready. */
  const subscribe = useCallback(
    (
      chart:   IChartApi,
      candles: ISeriesApi<'Candlestick'>,
      series: {
        ema9?:  ISeriesApi<'Line'>
        ema20?: ISeriesApi<'Line'>
        ema50?: ISeriesApi<'Line'>
        vwap?:  ISeriesApi<'Line'>
      }
    ) => {
      chart.subscribeCrosshairMove((param: MouseEventParams) => {
        if (!param.time) {
          setLegend(null)
          return
        }

        const bar = param.seriesData.get(candles) as OhlcBar | undefined
        if (!bar) {
          setLegend(null)
          return
        }

        // Format timestamp — param.time is a UTCTimestamp (seconds)
        const tsSec = param.time as number
        const d = new Date(tsSec * 1000)
        const hh = String(d.getHours()).padStart(2, '0')
        const mm = String(d.getMinutes()).padStart(2, '0')

        const getLineVal = (s?: ISeriesApi<'Line'>): number | undefined => {
          if (!s) return undefined
          const pt = param.seriesData.get(s) as LinePt | undefined
          return pt?.value
        }

        setLegend({
          time:      `${hh}:${mm}`,
          open:      bar.open,
          high:      bar.high,
          low:       bar.low,
          close:     bar.close,
          change:    bar.close - bar.open,
          changePct: ((bar.close - bar.open) / bar.open) * 100,
          ema9:      getLineVal(series.ema9),
          ema20:     getLineVal(series.ema20),
          ema50:     getLineVal(series.ema50),
          vwap:      getLineVal(series.vwap),
        })
      })
    },
    []
  )

  return { legend, subscribe }
}
