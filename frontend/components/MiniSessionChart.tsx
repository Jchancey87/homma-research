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
  CHART_BG, GRID_COLOR, TEXT_COLOR, UP_COLOR, DOWN_COLOR,
  EMA21_COL, EMA50_COL, EMA100_COL,
  ChartData, OhlcBar, LinePt, HistoPt,
  dedupSort, shiftChartDataTime,
} from '@/lib/chart'
import { fmt1, fmtFloat } from '@/lib/format'

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

export default function MiniSessionChart({ ticker, date, gapPct, float: floatShares, rvol, rank, pipe, height = 250, mom_2m = null, autoRefreshMs, onExpand }: Props) {
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
  // without recapturing `data` in its closure. Without this, an in-flight
  // tick from a previous auto-refresh cycle can land after the chart has
  // been rebuilt with a newer last bar, and candles.update() throws
  // "Cannot update oldest data" (lightweight-charts v5 guard).
  const dataRef = useRef<ChartData | null>(null)
  dataRef.current = data

  // In-place tick of the latest candle's close (and high/low) with the
  // current live price from the screener. No chart rebuild — the existing
  // candle is just .update()'d so the wick grows in real time.
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

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const json = await getChartData(ticker, date, true)
      // Only extract what we need to keep memory low. The `as ChartData`
      // cast is safe — `time: number` from the API is structurally
      // identical to `time: UTCTimestamp` at runtime (lightweight-charts
      // uses a brand on the type only).
      const rawData = {
        ohlcv:   json.ohlcv   as OhlcBar[],
        volume:  json.volume  as HistoPt[],
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

  // Lazy-load via IntersectionObserver — only fetch when scrolled into view
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

  // Auto-refresh + tick — two cadences in live mode:
  //   • autoRefreshMs (e.g. 15s) → re-fetch OHLCV bars (new minute, new row)
  //   • TICK_MS (5s)            → pull the single ticker's last_price from
  //                                /api/chart/live-price and update the last
  //                                candle's close in place
  // The tick keeps the chart "alive" between completed-minute bar fetches.
  // Page-level 30s interval handles the ticker list rotation separately.
  useEffect(() => {
    if (!autoRefreshMs || autoRefreshMs <= 0) return

    const TICK_MS = 5_000
    const fetchId = setInterval(() => {
      loaded.current = true   // bypass IntersectionObserver gate
      fetchData()
    }, autoRefreshMs)

    const tickId = setInterval(async () => {
      try {
        const prices = await getLivePrices([ticker])
        const price  = prices[ticker]
        if (price != null) tickLatestBar(price)
      } catch {
        // Tick is best-effort — the next bar poll will resync the close.
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

    // Destroy previous instance if any
    chartRef.current?.remove()

    const chart = createChart(containerRef.current, {
      layout: { 
        background: { color: CHART_BG }, 
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
          style: 1, // Dotted
          labelBackgroundColor: '#00ff00',
        },
        horzLine: {
          color: '#555555',
          width: 1,
          style: 1, // Dotted
          labelBackgroundColor: '#ff003c',
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

    // Candles
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOR, downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR, borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR, wickDownColor: DOWN_COLOR,
    })
    candles.setData(dedupSort(data.ohlcv))
    candlesRef.current = candles

    // Volume (overlaid, small scale, colored by up/down candle)
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
        color: isUp ? 'rgba(0, 255, 0, 0.3)' : 'rgba(255, 0, 60, 0.3)',
      }
    })
    vol.setData(dedupSort(volData))

    // EMA 21
    if (data.ema_21?.length) {
      const ema = chart.addSeries(LineSeries, {
        color: EMA21_COL, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      ema.setData(dedupSort(data.ema_21))
    }

    // EMA 50 (neon yellow)
    if (data.ema_50?.length) {
      const ema50 = chart.addSeries(LineSeries, {
        color: EMA50_COL, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      ema50.setData(dedupSort(data.ema_50))
    }

    // EMA 100 (neon pink)
    if (data.ema_100?.length) {
      const ema100 = chart.addSeries(LineSeries, {
        color: EMA100_COL, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      ema100.setData(dedupSort(data.ema_100))
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
    // If mouse moved less than 5px, it's a click, not a drag
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
      {/* HUD / Overlay */}
      <div className="absolute top-1 left-1.5 right-1.5 z-10 pointer-events-none flex justify-between select-none">
        {/* Left Side: Rank, Ticker, Gap, Timeframe, Momentum, PIPE */}
        <div className="flex items-center gap-1.5 bg-black/85 px-1 py-0.5 border border-[#333333] rounded-none">
          {rank != null && <span className="text-gray-500 text-[9px] font-bold">#{rank}</span>}
          <span className="font-bold text-white text-[10px] uppercase tracking-wider">{ticker}</span>
          <span className={`font-bold text-[9.5px] ${gapPct != null && gapPct >= 0 ? 'text-[#00ff00]' : 'text-[#ff003c]'}`}>
            {gapPct != null ? `${gapPct >= 0 ? '+' : ''}${fmt1(gapPct)}%` : ''}
          </span>
          <span className="text-gray-400 text-[8.5px] border border-gray-800 px-0.5">1m</span>
          
          {mom_2m != null && (
            <span
              className={`inline-flex items-center gap-0.5 px-1 py-[1px] rounded-none text-[8px] font-black uppercase tracking-wider border border-black/40 ${getMomStyle(mom_2m)}`}
              title="Server-computed 2-min momentum (live screener)"
            >
              MOM {fmtMom(mom_2m)}
            </span>
          )}

          {mom_2m == null && hasMomentumSpike && (
            <span className="inline-flex items-center gap-0.5 px-0.5 py-[1px] rounded-none text-[8px] font-black uppercase tracking-wider bg-[#ff003c]/20 text-[#ff003c] border border-[#ff003c]/30 animate-pulse">
              MOM +{priceMomentum.toFixed(1)}%
            </span>
          )}

          {pipe?.is_pipe && (
            <span
              className={`text-[8px] px-0.5 py-[1px] rounded-none uppercase tracking-wider border font-bold ${
                (pipe.deal_score ?? 0) >= 4 ? 'bg-emerald-950/45 text-[#00ff00] border-[#00ff00]/30'
                : (pipe.deal_score ?? 0) <= 2 ? 'bg-red-950/45 text-[#ff003c] border-[#ff003c]/30'
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
              O:<span className="text-[#00ff00]">{hovered.o.toFixed(2)}</span>{' '}
              H:<span className="text-[#00ff00]">{hovered.h.toFixed(2)}</span>{' '}
              L:<span className="text-[#ff003c]">{hovered.l.toFixed(2)}</span>{' '}
              C:<span className={hovered.c >= hovered.o ? 'text-[#00ff00]' : 'text-[#ff003c]'}>{hovered.c.toFixed(2)}</span>
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

      {/* Date overlay in bottom-left corner */}
      <div className="absolute bottom-1 left-1.5 z-10 pointer-events-none bg-black/85 px-1 py-0.25 border border-[#222222] rounded-none text-[8px] text-gray-500 font-mono select-none">
        {date}
      </div>

      {/* Live auto-refresh indicator (bottom-right) */}
      {autoRefreshMs && data && !loading && !error && (
        <div className="absolute bottom-1 right-1.5 z-10 pointer-events-none flex items-center gap-1 bg-black/85 px-1.5 py-0.5 border border-[#00ff00]/30 rounded-none text-[8px] text-[#00ff00] font-mono select-none">
          <span className="w-1.5 h-1.5 bg-[#00ff00] rounded-full animate-pulse" />
          LIVE {Math.round(autoRefreshMs / 1000)}s
        </div>
      )}

      {/* Loading & Error States */}
      {loading && (
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

      {/* Chart Canvas */}
      <div ref={containerRef} className="w-full h-full" />
    </div>
  )
}
