'use client'
import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import {
  createChart, IChartApi, ISeriesApi,
  CandlestickSeries, LineSeries, HistogramSeries,
  CrosshairMode,
} from 'lightweight-charts'
import { Loader2, AlertTriangle } from 'lucide-react'
import { PipeScanResult, getLivePrices, getChartData } from '@/lib/api'
import { getMomStyle, fmtMom } from '@/lib/momentum'
import {
  CHART_BG, GRID_COLOR, TEXT_COLOR, UP_COLOR, DOWN_COLOR, UP_VOL_COLOR, DOWN_VOL_COLOR,
  EMA9_COL, EMA20_COL, EMA50_COL, VWAP_COL,
  ChartData, OhlcBar, LinePt, HistoPt,
  dedupSort, shiftChartDataTime, calcEMA,
} from '@/lib/chart'
import { fmt1, fmtFloat } from '@/lib/format'
import { isMarketOpen } from '@/lib/market'

interface Props {
  ticker:   string
  date:     string
  gapPct:   number | null
  float:    number | null
  rvol:     number | null
  rank?:    number
  pipe?:    PipeScanResult | undefined
  height?:  number
  mom_2m?:  number | null
  autoRefreshMs?: number
  onExpand: (ticker: string) => void
}

export default function MiniSessionChart({ ticker, date, gapPct, float: floatShares, rvol, rank, pipe, height = 360, mom_2m = null, autoRefreshMs, onExpand }: Props) {
  const [clickStart, setClickStart] = useState<{ x: number; y: number } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef     = useRef<IChartApi | null>(null)
  const candlesRef   = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const [data,    setData]    = useState<ChartData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [hovered, setHovered] = useState<{ o: number; h: number; l: number; c: number } | null>(null)
  const loaded = useRef(false)

  // Ref mirror of `data` so the tick callback can read the latest bars
  // without recapturing `data` in its closure.
  const dataRef = useRef<ChartData | null>(null)
  dataRef.current = data

  const tickLatestBar = useCallback((price: number) => {
    const candles = candlesRef.current
    const cur = dataRef.current?.ohlcv
    if (!candles || !cur?.length) return
    const last = cur[cur.length - 1]
    candles.update({
      time:  last.time,
      open:  last.open,
      high:  Math.max(last.high, price),
      low:   Math.min(last.low,  price),
      close: price,
    })
  }, [])

  const priceMomentum = useMemo(() => {
    if (!data?.ohlcv || data.ohlcv.length < 3) return null
    const len = data.ohlcv.length
    const current = data.ohlcv[len - 1].close
    const prev2 = data.ohlcv[len - 3].close
    if (!prev2) return 0
    return ((current - prev2) / prev2) * 100
  }, [data?.ohlcv])

  const hasMomentumSpike = priceMomentum !== null && priceMomentum >= 1.0

  // 200 SMA calculation and status relative to close price
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
    return {
      value: currentSma200,
      isAbove,
      diffPct,
    }
  }, [data?.ohlcv])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const json = await getChartData(ticker, date, true)
      const rawData = {
        ohlcv:   json.ohlcv   as OhlcBar[],
        volume:  json.volume  as HistoPt[],
        ema_9:   json.ema_9   as LinePt[] ?? [],
        ema_20:  json.ema_20  as LinePt[] ?? [],
        vwap:    json.vwap    as LinePt[] ?? [],
        ema_21:  json.ema_21  as LinePt[] ?? [],
        ema_50:  json.ema_50  as LinePt[] ?? [],
        ema_100: json.ema_100 as LinePt[] ?? [],
      } as ChartData
      const localOffset = -new Date().getTimezoneOffset() * 60
      setData(shiftChartDataTime(rawData, localOffset))
    } catch (e) {
      const err = e as Error
      setError(err.message ?? 'No data')
    } finally {
      setLoading(false)
    }
  }, [ticker, date])

  // Load immediately on mount for top items, observe with large rootMargin for rest
  useEffect(() => {
    if (loaded.current) return
    if (rank != null && rank <= 6) {
      loaded.current = true
      fetchData()
      return
    }

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
      { rootMargin: '600px' }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [fetchData, rank])

  // Auto-refresh + tick (only run during active trading hours: Mon-Fri 4am-8pm ET)
  useEffect(() => {
    if (!autoRefreshMs || autoRefreshMs <= 0) return
    if (!isMarketOpen()) return

    const TICK_MS = 5_000
    const fetchId = setInterval(() => {
      loaded.current = true
      fetchData()
    }, autoRefreshMs)

    const tickId = setInterval(async () => {
      try {
        const prices = await getLivePrices([ticker])
        const price  = prices[ticker]
        if (price != null) tickLatestBar(price)
      } catch {
        // Tick is best-effort
      }
    }, TICK_MS)

    return () => {
      clearInterval(fetchId)
      clearInterval(tickId)
    }
  }, [autoRefreshMs, fetchData, ticker, tickLatestBar])

  // Build chart
  useEffect(() => {
    if (!data || !containerRef.current) return

    chartRef.current?.remove()

    const chart = createChart(containerRef.current, {
      layout: { 
        background: { color: 'transparent' }, 
        textColor: TEXT_COLOR, 
        fontSize: 10,
        fontFamily: "Consolas, 'Roboto Mono', Monaco, ui-monospace, monospace"
      },
      grid: { 
        vertLines: { color: GRID_COLOR, style: 1 }, 
        horzLines: { color: GRID_COLOR, style: 1 } 
      },
      crosshair: { 
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#555555',
          width: 1,
          style: 1,
          labelBackgroundColor: UP_COLOR,
        },
        horzLine: {
          color: '#555555',
          width: 1,
          style: 1,
          labelBackgroundColor: DOWN_COLOR,
        }
      },
      rightPriceScale: { borderColor: '#262626', textColor: TEXT_COLOR },
      timeScale: {
        borderColor:     '#262626',
        timeVisible:     true,
        secondsVisible:  false,
        fixLeftEdge:     true,
        fixRightEdge:    true,
      },
      handleScroll: true,
      handleScale:  true,
      width:  containerRef.current.clientWidth,
      height: height,
    })
    chartRef.current = chart

    // Candles with mellow colors
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOR, downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR, borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR, wickDownColor: DOWN_COLOR,
    })
    candles.setData(dedupSort(data.ohlcv))
    candlesRef.current = candles

    // Volume histogram with matching mellow translucent fills
    const vol = chart.addSeries(HistogramSeries, {
      priceFormat:     { type: 'volume' },
      priceScaleId:    'vol',
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

    // EMA 9 (Sky Blue)
    const ema9Data = data.ema_9?.length ? data.ema_9 : calcEMA(data.ohlcv, 9)
    if (ema9Data.length) {
      const ema9 = chart.addSeries(LineSeries, {
        color: EMA9_COL, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      ema9.setData(dedupSort(ema9Data))
    }

    // EMA 20 (Amber / Gold)
    const ema20Data = data.ema_20?.length ? data.ema_20 : calcEMA(data.ohlcv, 20)
    if (ema20Data.length) {
      const ema20 = chart.addSeries(LineSeries, {
        color: EMA20_COL, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      ema20.setData(dedupSort(ema20Data))
    }

    // EMA 50 (Purple)
    const ema50Data = data.ema_50?.length ? data.ema_50 : calcEMA(data.ohlcv, 50)
    if (ema50Data.length) {
      const ema50 = chart.addSeries(LineSeries, {
        color: EMA50_COL, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      ema50.setData(dedupSort(ema50Data))
    }

    // VWAP (white dashed)
    if (data.vwap?.length) {
      const vwapSeries = chart.addSeries(LineSeries, {
        color: VWAP_COL, lineWidth: 1, lineStyle: 2,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      vwapSeries.setData(dedupSort(data.vwap))
    }

    // Crosshair readout
    chart.subscribeCrosshairMove((param) => {
      if (param.time) {
        const bar = param.seriesData.get(candles) as OhlcBar | undefined
        if (bar) setHovered({ o: bar.open, h: bar.high, l: bar.low, c: bar.close })
      } else {
        setHovered(null)
      }
    })

    chart.timeScale().fitContent()

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      candlesRef.current = null
    }
  }, [data, height])

  const handleMouseDown = (e: React.MouseEvent) => {
    setClickStart({ x: e.clientX, y: e.clientY })
  }

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!clickStart) return
    const dx = Math.abs(e.clientX - clickStart.x)
    const dy = Math.abs(e.clientY - clickStart.y)
    if (dx < 5 && dy < 5) {
      onExpand(ticker)
    }
    setClickStart(null)
  }

  return (
    <div
      className="relative bg-black rounded-none overflow-hidden hover:bg-[#050505] transition-colors group font-mono cursor-pointer select-none"
      style={{ height: height }}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
    >
      {/* Chart Canvas */}
      <div ref={containerRef} className="w-full h-full relative z-0" />

      {/* Large Transparent Stock Ticker Symbol Watermark (z-5 overlay) */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-5 select-none overflow-hidden">
        <span className="text-6xl sm:text-7xl font-black text-white/[0.12] tracking-widest uppercase scale-125">
          {ticker}
        </span>
      </div>

      {/* HUD / Overlay */}
      <div className="absolute top-1 left-1.5 right-1.5 z-10 pointer-events-none flex justify-between select-none">
        {/* Left Side: Rank, Ticker, Gap, Timeframe, 200 SMA Indicator, Momentum, PIPE */}
        <div className="flex items-center gap-1.5 bg-black/85 px-1.5 py-0.5 border border-[#333333] rounded-none flex-wrap">
          {rank != null && <span className="text-gray-500 text-[9px] font-bold">#{rank}</span>}
          <span className="font-bold text-white text-[10.5px] uppercase tracking-wider">{ticker}</span>
          <span className={`font-bold text-[9.5px] ${gapPct != null && gapPct >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'}`}>
            {gapPct != null ? `${gapPct >= 0 ? '+' : ''}${fmt1(gapPct)}%` : ''}
          </span>
          <span className="text-gray-400 text-[8.5px] border border-gray-800 px-0.5">1m</span>
          
          {/* 200 SMA Above/Below Indicator */}
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

          {mom_2m != null && (
            <span
              className={`inline-flex items-center gap-0.5 px-1 py-[1px] rounded-none text-[8px] font-black uppercase tracking-wider border border-black/40 ${getMomStyle(mom_2m)}`}
              title="Server-computed 2-min momentum (live screener)"
            >
              MOM {fmtMom(mom_2m)}
            </span>
          )}

          {mom_2m == null && hasMomentumSpike && (
            <span className="inline-flex items-center gap-0.5 px-0.5 py-[1px] rounded-none text-[8px] font-black uppercase tracking-wider bg-[#ef5350]/20 text-[#ef5350] border border-[#ef5350]/30 animate-pulse">
              MOM +{priceMomentum.toFixed(1)}%
            </span>
          )}

          {pipe?.is_pipe && (
            <span
              className={`text-[8px] px-0.5 py-[1px] rounded-none uppercase tracking-wider border font-bold ${
                (pipe.deal_score ?? 0) >= 4 ? 'bg-emerald-950/45 text-[#26a69a] border-[#26a69a]/30'
                : (pipe.deal_score ?? 0) <= 2 ? 'bg-red-950/45 text-[#ef5350] border-[#ef5350]/30'
                : 'bg-yellow-950/45 text-yellow-400 border-yellow-500/30'
              }`}
            >
              PIPE {pipe.deal_score}/5
            </span>
          )}
        </div>

        {/* Right Side: Data stats / Hover coordinates */}
        <div className="flex flex-col items-end gap-0.5 bg-black/85 px-1 py-0.5 border border-[#333333] rounded-none text-[9px]">
          {hovered ? (
            <div className="text-[8.5px] text-gray-300 font-bold tracking-tight">
              O:<span className="text-[#26a69a]">{hovered.o.toFixed(2)}</span>{' '}
              H:<span className="text-[#26a69a]">{hovered.h.toFixed(2)}</span>{' '}
              L:<span className="text-[#ef5350]">{hovered.l.toFixed(2)}</span>{' '}
              C:<span className={hovered.c >= hovered.o ? 'text-[#26a69a]' : 'text-[#ef5350]'}>{hovered.c.toFixed(2)}</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-gray-400">
              <span>FLT:{fmtFloat(floatShares)}</span>
              {rvol != null && (
                <span className={rvol >= 5 ? 'text-[#fff000] font-bold' : ''}>RV:{fmt1(rvol)}x</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Date & EMA legend overlay in bottom-left corner */}
      <div className="absolute bottom-1 left-1.5 z-10 pointer-events-none bg-black/85 px-1.5 py-0.5 border border-[#222222] rounded-none text-[8px] text-gray-400 font-mono flex items-center gap-2 select-none">
        <span>{date}</span>
        <span className="text-gray-600">|</span>
        <span className="flex items-center gap-1 font-bold">
          <span className="text-[#38bdf8]">9</span>
          <span className="text-[#f59e0b]">20</span>
          <span className="text-[#ab47bc]">50 EMA</span>
        </span>
      </div>

      {/* Live / Market status indicator (bottom-right) */}
      {autoRefreshMs && data && !error && (
        <div className={`absolute bottom-1 right-1.5 z-10 pointer-events-none flex items-center gap-1 bg-black/85 px-1.5 py-0.5 border rounded-none text-[8px] font-mono select-none transition-colors duration-200 ${
          !isMarketOpen()
            ? 'border-gray-800 text-gray-500'
            : loading
            ? 'border-yellow-500/40 text-yellow-400'
            : 'border-[#26a69a]/30 text-[#26a69a]'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${
            !isMarketOpen()
              ? 'bg-gray-600'
              : loading
              ? 'bg-yellow-400 animate-pulse'
              : 'bg-[#26a69a] animate-pulse'
          }`} />
          {!isMarketOpen() ? 'MARKET CLOSED' : loading ? 'UPDATING' : `LIVE ${Math.round(autoRefreshMs / 1000)}s`}
        </div>
      )}

      {/* Loading & Error States */}
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
