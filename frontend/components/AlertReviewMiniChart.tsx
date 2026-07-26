'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import {
  createChart, IChartApi,
  CandlestickSeries, LineSeries, HistogramSeries,
  CrosshairMode, SeriesMarker, Time, createSeriesMarkers,
} from 'lightweight-charts'
import { Loader2, AlertTriangle } from 'lucide-react'
import { getChartData, AlertReviewSymbol } from '@/lib/api'
import {
  CHART_BG, GRID_COLOR, TEXT_COLOR, UP_COLOR, DOWN_COLOR,
  ChartData, OhlcBar, LinePt, HistoPt,
  dedupSort, shiftChartDataTime,
} from '@/lib/chart'
import { fmt1 } from '@/lib/format'

const EMA9_COL = '#00ffff'  // Cyan (EMA 9)
const EMA20_COL = '#ffff00' // Yellow (EMA 20)
const EMA55_COL = '#ff00ff' // Magenta (EMA 55)
const VWAP_COL = '#ffffff'  // White (VWAP)

interface Props {
  symbolData: AlertReviewSymbol
  date: string
  height?: number
  onExpand: (symbol: string) => void
}

export default function AlertReviewMiniChart({
  symbolData,
  date,
  height = 250,
  onExpand,
}: Props) {
  const { symbol, gap_pct, alert_count, best_15m_mfe, alerts } = symbolData
  const [clickStart, setClickStart] = useState<{ x: number; y: number } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const [data, setData] = useState<ChartData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const loaded = useRef(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const json = await getChartData(symbol, date, true)
      const rawData = {
        ohlcv: json.ohlcv as OhlcBar[],
        volume: json.volume as HistoPt[],
        ema_9: json.ema_9 as LinePt[] ?? [],
        ema_20: json.ema_20 as LinePt[] ?? [],
        ema_55: json.ema_55 as LinePt[] ?? [],
        vwap: json.vwap as LinePt[] ?? [],
      } as unknown as ChartData
      const localOffset = -new Date().getTimezoneOffset() * 60
      setData(shiftChartDataTime(rawData, localOffset))
    } catch (e) {
      const err = e as Error
      setError(err.message ?? 'No chart data')
    } finally {
      setLoading(false)
    }
  }, [symbol, date])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !loaded.current) {
          loaded.current = true
          observer.disconnect()
          fetchData()
        }
      },
      { rootMargin: '200px' }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [fetchData])

  useEffect(() => {
    if (!data || !containerRef.current) return

    chartRef.current?.remove()

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: CHART_BG },
        textColor: TEXT_COLOR,
        fontSize: 10,
        fontFamily: "Consolas, 'Roboto Mono', Monaco, ui-monospace, monospace",
      },
      grid: {
        vertLines: { color: GRID_COLOR, style: 1 },
        horzLines: { color: GRID_COLOR, style: 1 },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: { borderColor: '#262626', textColor: TEXT_COLOR },
      timeScale: {
        borderColor: '#262626',
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      width: containerRef.current.clientWidth,
      height: height,
    })
    chartRef.current = chart

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOR, downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR, borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR, wickDownColor: DOWN_COLOR,
    })
    candles.setData(dedupSort(data.ohlcv))

    const vol = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.80, bottom: 0 }, visible: false })

    const volData = data.volume.map(v => ({
      time: v.time,
      value: v.value,
      color: 'rgba(255, 255, 255, 0.15)',
    }))
    vol.setData(dedupSort(volData))

    // Indicators: EMA 9, 20, 55, VWAP
    const localOffset = -new Date().getTimezoneOffset() * 60
    const rawDataAny = data as unknown as Record<string, LinePt[]>

    if (rawDataAny.ema_9?.length) {
      const ema9 = chart.addSeries(LineSeries, {
        color: EMA9_COL, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      })
      ema9.setData(dedupSort(rawDataAny.ema_9))
    }

    if (rawDataAny.ema_20?.length) {
      const ema20 = chart.addSeries(LineSeries, {
        color: EMA20_COL, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      })
      ema20.setData(dedupSort(rawDataAny.ema_20))
    }

    if (rawDataAny.ema_55?.length) {
      const ema55 = chart.addSeries(LineSeries, {
        color: EMA55_COL, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      })
      ema55.setData(dedupSort(rawDataAny.ema_55))
    }

    if (rawDataAny.vwap?.length) {
      const vwapSeries = chart.addSeries(LineSeries, {
        color: VWAP_COL, lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      })
      vwapSeries.setData(dedupSort(rawDataAny.vwap))
    }

    // Overlay Alert Markers
    if (alerts?.length && data.ohlcv.length) {
      const markers: SeriesMarker<Time>[] = []
      alerts.forEach(a => {
        if (!a.alert_time) return
        try {
          const dt = new Date(a.alert_time)
          const tsSec = Math.floor(dt.getTime() / 1000) + localOffset
          const color =
            a.priority_tier === 'Tier 1'
              ? '#ff003c'
              : a.priority_tier === 'Tier 2'
              ? '#ffff00'
              : '#00f0ff'

          markers.push({
            time: tsSec as Time,
            position: 'aboveBar',
            color: color,
            shape: 'arrowDown',
            text: '',
          })
        } catch {
          // Ignore invalid timestamps
        }
      })
      if (markers.length) {
        createSeriesMarkers(candles, markers)
      }
    }

    chart.timeScale().fitContent()

    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [data, height, alerts])

  const handleMouseDown = (e: React.MouseEvent) => {
    setClickStart({ x: e.clientX, y: e.clientY })
  }

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!clickStart) return
    const dx = Math.abs(e.clientX - clickStart.x)
    const dy = Math.abs(e.clientY - clickStart.y)
    if (dx < 5 && dy < 5) {
      onExpand(symbol)
    }
    setClickStart(null)
  }

  return (
    <div
      className="relative bg-black rounded-none overflow-hidden hover:border-[#00ff00]/50 border border-[#222222] transition-colors font-mono cursor-pointer select-none"
      style={{ height: height }}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
    >
      {/* HUD Header */}
      <div className="absolute top-1 left-1.5 right-1.5 z-10 pointer-events-none flex justify-between select-none">
        <div className="flex items-center gap-1.5 bg-black/90 px-1.5 py-0.5 border border-[#333333]">
          <span className="font-bold text-white text-xs uppercase tracking-wider">{symbol}</span>
          {gap_pct != null && (
            <span className={`font-bold text-[10px] ${gap_pct >= 0 ? 'text-[#00ff00]' : 'text-[#ff003c]'}`}>
              {gap_pct >= 0 ? '+' : ''}{fmt1(gap_pct)}%
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 bg-black/90 px-1.5 py-0.5 border border-[#333333] text-[9.5px]">
          {alert_count > 0 ? (
            <>
              <span className="bg-red-950/80 text-red-400 border border-red-800/60 px-1 py-0.25 font-bold">
                {alert_count} alert{alert_count > 1 ? 's' : ''}
              </span>
              <span className="text-gray-300">
                15m MFE:{' '}
                <strong className={best_15m_mfe >= 2.0 ? 'text-[#00ff00]' : 'text-yellow-400'}>
                  +{fmt1(best_15m_mfe)}%
                </strong>
              </span>
            </>
          ) : (
            <span className="text-gray-500 font-bold">No Alerts</span>
          )}
        </div>
      </div>

      {/* Date badge bottom-left */}
      <div className="absolute bottom-1 left-1.5 z-10 pointer-events-none bg-black/85 px-1 py-0.25 border border-[#222222] text-[8px] text-gray-500">
        {date}
      </div>

      {loading && !data && (
        <div className="absolute inset-0 flex items-center justify-center bg-black z-20">
          <Loader2 size={16} className="animate-spin text-gray-700" />
        </div>
      )}

      {error && !loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-gray-700 z-20">
          <AlertTriangle size={14} />
          <span className="text-[9px]">{error}</span>
        </div>
      )}

      <div ref={containerRef} className="w-full h-full" />
    </div>
  )
}
