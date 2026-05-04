'use client'
import { useEffect, useRef, useState, useCallback } from 'react'
import {
  createChart, IChartApi, ISeriesApi,
  CandlestickSeries, LineSeries, HistogramSeries,
  CrosshairMode, UTCTimestamp,
} from 'lightweight-charts'
import { Loader2, AlertTriangle } from 'lucide-react'

const API_BASE   = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5000'
const CHART_BG   = '#0d0d14'
const GRID_COLOR = '#1a1a2a'
const TEXT_COLOR = '#64748b'
const UP_COLOR   = '#22d3a7'
const DOWN_COLOR = '#f04d5a'
const EMA21_COL  = '#4361ee'

interface OhlcBar { time: UTCTimestamp; open: number; high: number; low: number; close: number }
interface LinePt  { time: UTCTimestamp; value: number }
interface HistoPt { time: UTCTimestamp; value: number; color?: string }

interface ChartData {
  ohlcv:  OhlcBar[]
  volume: HistoPt[]
  ema_21: LinePt[]
}

/** Sort ascending by time and remove duplicate timestamps (keep last occurrence). */
function dedupSort<T extends { time: UTCTimestamp }>(data: T[]): T[] {
  const map = new Map<number, T>()
  for (const bar of data) map.set(bar.time as number, bar)
  return Array.from(map.values()).sort((a, b) => (a.time as number) - (b.time as number))
}

interface Props {
  ticker:   string
  date:     string
  gapPct:   number | null
  float:    number | null
  rvol:     number | null
  onExpand: (ticker: string) => void
}

function fmt1(n: number | null) {
  if (n == null) return '—'
  return n.toFixed(1)
}
function fmtFloat(n: number | null) {
  if (n == null) return '—'
  const m = n / 1_000_000
  return m >= 1000 ? `${(m / 1000).toFixed(1)}B` : `${m.toFixed(1)}M`
}

export default function MiniSessionChart({ ticker, date, gapPct, float: floatShares, rvol, onExpand }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef     = useRef<IChartApi | null>(null)
  const [data,    setData]    = useState<ChartData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [hovered, setHovered] = useState<{ o: number; h: number; l: number; c: number } | null>(null)
  const loaded = useRef(false)

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
  }, [ticker, date])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res  = await fetch(`${API_BASE}/api/research/chart-data?ticker=${ticker}&date=${date}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      // Only extract what we need to keep memory low
      setData({ ohlcv: json.ohlcv, volume: json.volume, ema_21: json.ema_21 })
    } catch (e: any) {
      setError(e.message ?? 'No data')
    } finally {
      setLoading(false)
    }
  }, [ticker, date])

  // Build chart
  useEffect(() => {
    if (!data || !containerRef.current) return

    // Destroy previous instance if any
    chartRef.current?.remove()

    const chart = createChart(containerRef.current, {
      layout:    { background: { color: CHART_BG }, textColor: TEXT_COLOR, fontSize: 10 },
      grid:      { vertLines: { color: GRID_COLOR }, horzLines: { color: GRID_COLOR } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: GRID_COLOR, textColor: TEXT_COLOR },
      timeScale: {
        borderColor:     GRID_COLOR,
        timeVisible:     true,
        secondsVisible:  false,
        fixLeftEdge:     true,
        fixRightEdge:    true,
      },
      handleScroll: true,
      handleScale:  true,
      width:  containerRef.current.clientWidth,
      height: 200,
    })
    chartRef.current = chart

    // Candles
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOR, downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR, borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR, wickDownColor: DOWN_COLOR,
    })
    candles.setData(dedupSort(data.ohlcv))

    // Volume (overlaid, small scale)
    const vol = chart.addSeries(HistogramSeries, {
      color: 'rgba(100,116,139,0.3)',
      priceFormat:     { type: 'volume' },
      priceScaleId:    'vol',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.80, bottom: 0 }, visible: false })
    vol.setData(dedupSort(data.volume))

    // EMA 21
    if (data.ema_21?.length) {
      const ema = chart.addSeries(LineSeries, {
        color: EMA21_COL, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      ema.setData(dedupSort(data.ema_21))
    }

    // Crosshair readout
    chart.subscribeCrosshairMove((param) => {
      if (param.time) {
        const bar = param.seriesData.get(candles) as any
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

    return () => { ro.disconnect(); chart.remove() }
  }, [data])

  return (
    <div
      className="bg-[#0d0d14] border border-gray-800 rounded-xl overflow-hidden
                 hover:border-emerald-500/40 transition-colors group cursor-pointer"
      onClick={() => onExpand(ticker)}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800/80">
        <div className="flex items-center gap-2">
          <span className="font-bold text-white text-sm font-mono">{ticker}</span>
          <span className="text-xs text-emerald-400 font-mono font-semibold">
            {gapPct != null ? `+${fmt1(gapPct)}%` : ''}
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-gray-500 font-mono">
          <span>Float {fmtFloat(floatShares)}</span>
          {rvol != null && (
            <span className={rvol >= 5 ? 'text-amber-400' : ''}>{fmt1(rvol)}x RVOL</span>
          )}
          {hovered && (
            <span className="hidden group-hover:flex items-center gap-1.5 text-[10px] font-mono">
              <span className="text-gray-500">O<span className="text-gray-300 ml-0.5">{hovered.o.toFixed(2)}</span></span>
              <span className="text-gray-500">H<span className="text-emerald-400 ml-0.5">{hovered.h.toFixed(2)}</span></span>
              <span className="text-gray-500">L<span className="text-red-400 ml-0.5">{hovered.l.toFixed(2)}</span></span>
              <span className="text-gray-500">C<span className="text-gray-200 ml-0.5">{hovered.c.toFixed(2)}</span></span>
            </span>
          )}
        </div>
      </div>

      {/* Chart area */}
      <div className="relative" style={{ height: 200 }}>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0d0d14]">
            <Loader2 size={16} className="animate-spin text-gray-600" />
          </div>
        )}
        {error && !loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 text-gray-600">
            <AlertTriangle size={16} />
            <span className="text-[10px]">{error}</span>
          </div>
        )}
        <div ref={containerRef} className="w-full h-full" />
      </div>

      {/* Footer hint */}
      <div className="px-3 py-1.5 border-t border-gray-900/80 flex items-center justify-between">
        <span className="text-[10px] text-gray-700">1m · click to research</span>
        <span className="text-[10px] text-gray-700">{date}</span>
      </div>
    </div>
  )
}
