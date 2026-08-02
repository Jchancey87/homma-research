import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import {
  createChart, IChartApi,
  CandlestickSeries, LineSeries, HistogramSeries,
  CrosshairMode, SeriesMarker, Time, createSeriesMarkers,
} from 'lightweight-charts'
import { Loader2, AlertTriangle } from 'lucide-react'
import { getChartData, AlertReviewSymbol } from '@/lib/api'
import {
  CHART_BG, GRID_COLOR, TEXT_COLOR, UP_COLOR, DOWN_COLOR, UP_VOL_COLOR, DOWN_VOL_COLOR,
  EMA9_COL, EMA20_COL, EMA50_COL, VWAP_COL,
  ChartData, OhlcBar, LinePt, HistoPt,
  dedupSort, shiftChartDataTime, calcEMA,
} from '@/lib/chart'
import { fmt1 } from '@/lib/format'

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

  const sma200Info = useMemo(() => {
    if (!data?.ohlcv || data.ohlcv.length === 0) return null
    const bars = data.ohlcv
    const len = bars.length
    const windowSize = Math.min(len, 200)
    let sum = 0
    for (let i = len - windowSize; i < len; i++) {
      sum += bars[i].close
    }
    const currentSma200 = sum / windowSize
    const latestClose = bars[len - 1].close
    const isAbove = latestClose >= currentSma200
    const diffPct = ((latestClose - currentSma200) / currentSma200) * 100
    return { value: currentSma200, isAbove, diffPct }
  }, [data?.ohlcv])

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
        ema_50: json.ema_50 as LinePt[] ?? [],
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
        background: { color: 'transparent' },
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

    const ohlcMap = new Map<number, OhlcBar>()
    data.ohlcv.forEach(c => ohlcMap.set(c.time as number, c))

    const volData = data.volume.map(v => {
      const candle = ohlcMap.get(v.time as number)
      const isUp = candle ? candle.close >= candle.open : true
      return {
        time: v.time,
        value: v.value,
        color: isUp ? UP_VOL_COLOR : DOWN_VOL_COLOR,
      }
    })
    vol.setData(dedupSort(volData))

    // Indicators: EMA 9, 20, 50, VWAP
    const localOffset = -new Date().getTimezoneOffset() * 60

    const ema9Data = data.ema_9?.length ? data.ema_9 : calcEMA(data.ohlcv, 9)
    if (ema9Data.length) {
      const ema9 = chart.addSeries(LineSeries, {
        color: EMA9_COL, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      })
      ema9.setData(dedupSort(ema9Data))
    }

    const ema20Data = data.ema_20?.length ? data.ema_20 : calcEMA(data.ohlcv, 20)
    if (ema20Data.length) {
      const ema20 = chart.addSeries(LineSeries, {
        color: EMA20_COL, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      })
      ema20.setData(dedupSort(ema20Data))
    }

    const ema50Data = data.ema_50?.length ? data.ema_50 : calcEMA(data.ohlcv, 50)
    if (ema50Data.length) {
      const ema50 = chart.addSeries(LineSeries, {
        color: EMA50_COL, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      })
      ema50.setData(dedupSort(ema50Data))
    }

    if (data.vwap?.length) {
      const vwapSeries = chart.addSeries(LineSeries, {
        color: VWAP_COL, lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      })
      vwapSeries.setData(dedupSort(data.vwap))
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
              ? '#ef5350'
              : a.priority_tier === 'Tier 2'
              ? '#f59e0b'
              : '#38bdf8'

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
      className="relative bg-black rounded-none overflow-hidden hover:border-[#26a69a]/50 border border-[#222222] transition-colors font-mono cursor-pointer select-none"
      style={{ height: height }}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
    >
      {/* Chart Canvas */}
      <div ref={containerRef} className="w-full h-full relative z-0" />

      {/* Large Transparent Stock Ticker Symbol Watermark (z-5 overlay) */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-5 select-none overflow-hidden">
        <span className="text-5xl sm:text-6xl font-black text-white/[0.12] tracking-widest uppercase scale-125">
          {symbol}
        </span>
      </div>

      {/* HUD Header */}
      <div className="absolute top-1 left-1.5 right-1.5 z-10 pointer-events-none flex justify-between select-none">
        <div className="flex items-center gap-1.5 bg-black/90 px-1.5 py-0.5 border border-[#333333]">
          <span className="font-bold text-white text-xs uppercase tracking-wider">{symbol}</span>
          {gap_pct != null && (
            <span className={`font-bold text-[10px] ${gap_pct >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'}`}>
              {gap_pct >= 0 ? '+' : ''}{fmt1(gap_pct)}%
            </span>
          )}
          {sma200Info != null && (
            <span
              className={`inline-flex items-center gap-1 px-1 py-[1px] rounded-none text-[8px] font-black uppercase tracking-wider border ${
                sma200Info.isAbove
                  ? 'bg-emerald-950/40 text-[#26a69a] border-[#26a69a]/40'
                  : 'bg-red-950/40 text-[#ef5350] border-[#ef5350]/40'
              }`}
              title={`200 SMA: $${sma200Info.value.toFixed(2)} (${sma200Info.diffPct >= 0 ? '+' : ''}${sma200Info.diffPct.toFixed(1)}%)`}
            >
              <span>200 SMA</span>
              <span>{sma200Info.isAbove ? '▲ ABOVE' : '▼ BELOW'}</span>
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
                <strong className={best_15m_mfe >= 2.0 ? 'text-[#26a69a]' : 'text-yellow-400'}>
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
      <div className="absolute bottom-1 left-1.5 z-10 pointer-events-none bg-black/85 px-1 py-0.25 border border-[#222222] text-[8px] text-gray-500 flex items-center gap-2">
        <span>{date}</span>
        <span className="text-gray-600">|</span>
        <span className="flex items-center gap-1 font-bold">
          <span className="text-[#38bdf8]">9</span>
          <span className="text-[#f59e0b]">20</span>
          <span className="text-[#ab47bc]">50 EMA</span>
        </span>
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
    </div>
  )
}
