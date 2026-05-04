'use client'
import { useEffect, useRef, useState, useCallback } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5000'

import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  CrosshairMode,
  LineStyle,
  Time,
} from 'lightweight-charts'
import { Loader2, TrendingUp, BarChart2, Activity, Zap, Eye, EyeOff, Settings2 } from 'lucide-react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface OhlcBar  { time: Time; open: number; high: number; low: number; close: number }
interface LinePt   { time: Time; value: number }
interface HistoPt  { time: Time; value: number; color?: string }

/** Sort ascending by time and remove duplicate timestamps (keep last occurrence). */
function dedupSort<T extends { time: Time }>(data: T[]): T[] {
  const map = new Map<any, T>()
  for (const bar of data) map.set(bar.time, bar)
  return Array.from(map.values()).sort((a, b) => (a.time as any) - (b.time as any))
}

export interface ChartData {
  ohlcv:   OhlcBar[]
  volume:  HistoPt[]
  rvol:    LinePt[]
  ema_8:   LinePt[]
  ema_13:  LinePt[]
  ema_21:  LinePt[]
  ema_34:  LinePt[]
  ema_55:  LinePt[]
  adx:     LinePt[]
  plus_di: LinePt[]
  minus_di: LinePt[]
  atr:     LinePt[]
}

interface Props {
  ticker: string
  date:   string
}

// ─── Color palette ────────────────────────────────────────────────────────────

const EMA_COLORS = ['#00f5d4', '#00bbf9', '#4361ee', '#7209b7', '#f72585']
const CHART_BG   = '#0d0d14'
const GRID_COLOR = '#1e1e2e'
const TEXT_COLOR = '#94a3b8'
const UP_COLOR   = '#22d3a7'
const DOWN_COLOR = '#f04d5a'

// ─── Main Component ───────────────────────────────────────────────────────────

export default function InteractiveSessionChart({ ticker, date }: Props) {
  const mainRef  = useRef<HTMLDivElement>(null)
  const adxRef   = useRef<HTMLDivElement>(null)
  const atrRef   = useRef<HTMLDivElement>(null)

  const mainChart = useRef<IChartApi | null>(null)
  const adxChart  = useRef<IChartApi | null>(null)
  const atrChart  = useRef<IChartApi | null>(null)

  const emaSeriesRefs  = useRef<ISeriesApi<"Line">[]>([])
  const volSeriesRef   = useRef<ISeriesApi<"Histogram"> | null>(null)
  const rvolSeriesRef  = useRef<ISeriesApi<"Line"> | null>(null)
  const adxSeriesRefs  = useRef<ISeriesApi<"Line">[]>([])
  const atrSeriesRef   = useRef<ISeriesApi<"Line"> | null>(null)

  const [loading, setLoading]   = useState(true)
  const [error,   setError]     = useState<string | null>(null)
  const [data,    setData]      = useState<ChartData | null>(null)
  const [ohlcInfo, setOhlcInfo] = useState<{ o: number; h: number; l: number; c: number; v: number } | null>(null)

  // Indicator Visibility State
  const [showEma, setShowEma] = useState(true)
  const [showVol, setShowVol] = useState(true)
  const [showAdx, setShowAdx] = useState(true)
  const [showAtr, setShowAtr] = useState(true)
  const [showSettings, setShowSettings] = useState(false)

  // ── Fetch chart data from backend ────────────────────────────────────────

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/research/chart-data?ticker=${ticker}&date=${date}`)
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error ?? `HTTP ${res.status}`)
      }
      const json: ChartData = await res.json()
      setData(json)
    } catch (e: any) {
      setError(e.message ?? 'Failed to load chart data')
    } finally {
      setLoading(false)
    }
  }, [ticker, date])

  useEffect(() => { fetchData() }, [fetchData])

  // ── Build charts once data is ready ──────────────────────────────────────

  useEffect(() => {
    if (!data || !mainRef.current || !adxRef.current || !atrRef.current) return

    // Shared chart options
    const baseOpts = {
      layout:    { background: { color: CHART_BG }, textColor: TEXT_COLOR, fontSize: 11 },
      grid:      { vertLines: { color: GRID_COLOR }, horzLines: { color: GRID_COLOR } },
      rightPriceScale: { borderColor: GRID_COLOR },
      timeScale: { borderColor: GRID_COLOR, timeVisible: true, secondsVisible: false },
      handleScroll: true,
      handleScale:  true,
    }

    // ── Main chart (price + EMAs + Volume + RVOL) ──────────────────────────
    const mc = createChart(mainRef.current, {
      ...baseOpts,
      crosshair: { mode: CrosshairMode.Normal },
      width:  mainRef.current.clientWidth,
      height: 420,
    })
    mainChart.current = mc

    // Candlestick series
    const candles = mc.addSeries(CandlestickSeries, {
      upColor:         UP_COLOR,
      downColor:       DOWN_COLOR,
      borderUpColor:   UP_COLOR,
      borderDownColor: DOWN_COLOR,
      wickUpColor:     UP_COLOR,
      wickDownColor:   DOWN_COLOR,
    })
    candles.setData(dedupSort(data.ohlcv))

    // EMA Ribbon
    emaSeriesRefs.current = []
    const emaData = [data.ema_8, data.ema_13, data.ema_21, data.ema_34, data.ema_55]
    const emaLabels = ['EMA 8', 'EMA 13', 'EMA 21', 'EMA 34', 'EMA 55']
    emaData.forEach((pts, i) => {
      const line = mc.addSeries(LineSeries, {
        color:      EMA_COLORS[i],
        lineWidth:  1,
        lineStyle:  LineStyle.Solid,
        title:      emaLabels[i],
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        visible: showEma,
      })
      line.setData(dedupSort(pts))
      emaSeriesRefs.current.push(line)
    })

    // Volume histogram
    const volSeries = mc.addSeries(HistogramSeries, {
      color:              'rgba(100,116,139,0.4)',
      priceFormat:        { type: 'volume' },
      priceScaleId:       'volume',
      lastValueVisible:   false,
      priceLineVisible:   false,
      visible:            showVol,
    })
    mc.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    volSeries.setData(dedupSort(data.volume))
    volSeriesRef.current = volSeries

    // RVOL line on volume scale
    const rvolSeries = mc.addSeries(LineSeries, {
      color:            '#f0abfc',
      lineWidth:        1,
      priceScaleId:     'rvol',
      title:            'RVOL',
      lastValueVisible: false,
      priceLineVisible: false,
      visible:          showVol,
    })
    mc.priceScale('rvol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 }, visible: false })
    rvolSeries.setData(dedupSort(data.rvol))
    rvolSeriesRef.current = rvolSeries

    // Crosshair data readout
    mc.subscribeCrosshairMove((param) => {
      if (param.time && candles) {
        const bar = param.seriesData.get(candles) as any
        if (bar) {
          setOhlcInfo({ o: bar.open, h: bar.high, l: bar.low, c: bar.close, v: bar.customValues?.volume ?? 0 })
        }
      }
    })

    // ── ADX chart ──────────────────────────────────────────────────────────
    const ac = createChart(adxRef.current, {
      ...baseOpts,
      crosshair: { mode: CrosshairMode.Normal },
      width:  adxRef.current.clientWidth,
      height: 130,
    })
    adxChart.current = ac

    const adxSeries = ac.addSeries(LineSeries, {
      color: '#a78bfa', lineWidth: 2, title: 'ADX',
      priceLineVisible: false, lastValueVisible: true,
    })
    adxSeries.setData(dedupSort(data.adx))

    const plusDiSeries = ac.addSeries(LineSeries, {
      color: UP_COLOR, lineWidth: 1, lineStyle: LineStyle.Dashed,
      title: '+DI', priceLineVisible: false, lastValueVisible: false,
    })
    plusDiSeries.setData(dedupSort(data.plus_di))

    const minusDiSeries = ac.addSeries(LineSeries, {
      color: DOWN_COLOR, lineWidth: 1, lineStyle: LineStyle.Dashed,
      title: '-DI', priceLineVisible: false, lastValueVisible: false,
    })
    minusDiSeries.setData(dedupSort(data.minus_di))

    // ADX 25 reference line
    const refLine = ac.addSeries(LineSeries, {
      color: 'rgba(255,255,255,0.15)', lineWidth: 1, lineStyle: LineStyle.Dotted,
      priceLineVisible: false, lastValueVisible: false,
    })
    refLine.setData(dedupSort(data.adx.map(p => ({ time: p.time, value: 25 }))))

    adxSeriesRefs.current = [adxSeries, plusDiSeries, minusDiSeries, refLine]

    // ── ATR chart ──────────────────────────────────────────────────────────
    const atc = createChart(atrRef.current, {
      ...baseOpts,
      crosshair: { mode: CrosshairMode.Normal },
      width:  atrRef.current.clientWidth,
      height: 100,
    })
    atrChart.current = atc

    const atrSeries = atc.addSeries(LineSeries, {
      color: '#fb923c', lineWidth: 2, title: 'ATR',
      priceLineVisible: false, lastValueVisible: true,
    })
    atrSeries.setData(dedupSort(data.atr))
    atrSeriesRef.current = atrSeries

    // ── Sync timescale across all panes ────────────────────────────────────
    const charts = [mc, ac, atc]
    charts.forEach((src) => {
      src.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range) return
        charts.forEach(dst => {
          if (dst !== src) dst.timeScale().setVisibleLogicalRange(range)
        })
      })
    })

    // ── Sync crosshair across panes ────────────────────────────────────────
    mc.subscribeCrosshairMove((param) => {
      if (param.time) {
        if (ac && adxSeriesRefs.current[0]) {
          ac.setCrosshairPosition(0, param.time as any, adxSeriesRefs.current[0])
        }
        if (atc && atrSeriesRef.current) {
          atc.setCrosshairPosition(0, param.time as any, atrSeriesRef.current)
        }
      }
    })

    // Fit all to visible content
    charts.forEach(c => c.timeScale().fitContent())

    // ── Resize observer ────────────────────────────────────────────────────
    const ro = new ResizeObserver(() => {
      if (mainRef.current) mc.applyOptions({ width: mainRef.current.clientWidth })
      if (adxRef.current)  ac.applyOptions({ width: adxRef.current.clientWidth })
      if (atrRef.current)  atc.applyOptions({ width: atrRef.current.clientWidth })
    })
    if (mainRef.current) ro.observe(mainRef.current)

    return () => {
      ro.disconnect()
      mc.remove()
      ac.remove()
      atc.remove()
    }
  }, [data, showAdx, showAtr])

  // ── Sync Visibility ───────────────────────────────────────────────────────
  useEffect(() => {
    emaSeriesRefs.current.forEach(s => s.applyOptions({ visible: showEma }))
  }, [showEma])

  useEffect(() => {
    volSeriesRef.current?.applyOptions({ visible: showVol })
    rvolSeriesRef.current?.applyOptions({ visible: showVol })
  }, [showVol])

  useEffect(() => {
    adxSeriesRefs.current.forEach(s => s.applyOptions({ visible: showAdx }))
  }, [showAdx])

  useEffect(() => {
    atrSeriesRef.current?.applyOptions({ visible: showAtr })
  }, [showAtr])

  // Resize charts when panels are toggled
  useEffect(() => {
    if (mainChart.current && mainRef.current) mainChart.current.applyOptions({ width: mainRef.current.clientWidth })
    if (adxChart.current && adxRef.current)   adxChart.current.applyOptions({ width: adxRef.current.clientWidth })
    if (atrChart.current && atrRef.current)   atrChart.current.applyOptions({ width: atrRef.current.clientWidth })
  }, [showAdx, showAtr])

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-3 py-16 text-sky-400">
        <Loader2 size={22} className="animate-spin" />
        <span className="text-sm font-medium tracking-wide animate-pulse">LOADING INTERACTIVE CHART...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center gap-3 py-10 text-amber-400 bg-amber-400/5 rounded-xl border border-amber-400/20">
        <Activity size={18} />
        <span className="text-sm">{error}</span>
      </div>
    )
  }

  return (
    <div className="rounded-2xl overflow-hidden border border-gray-800/80 bg-[#0d0d14]">
      {/* ── Chart header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800/60 bg-[#0d0d14]">
        <div className="flex items-center gap-3">
          <TrendingUp size={15} className="text-sky-400" />
          <span className="text-xs font-bold text-gray-300 font-mono">{ticker}</span>
          <span className="text-[10px] text-gray-600">|</span>
          <span className="text-[10px] text-gray-500 font-mono">{date} · 1m Bars · ET</span>
        </div>
        {ohlcInfo && (
          <div className="flex items-center gap-3 text-[10px] font-mono">
            <span className="text-gray-500">O <span className="text-gray-200">{ohlcInfo.o.toFixed(2)}</span></span>
            <span className="text-gray-500">H <span className="text-emerald-400">{ohlcInfo.h.toFixed(2)}</span></span>
            <span className="text-gray-500">L <span className="text-red-400">{ohlcInfo.l.toFixed(2)}</span></span>
            <span className="text-gray-500">C <span className="text-gray-100">{ohlcInfo.c.toFixed(2)}</span></span>
          </div>
        )}
        <div className="flex items-center gap-2 ml-4 pl-4 border-l border-gray-800">
          <button 
            onClick={() => setShowSettings(!showSettings)}
            className={`p-1.5 rounded-lg transition-all ${showSettings ? 'bg-sky-500/20 text-sky-400' : 'text-gray-500 hover:bg-gray-800 hover:text-gray-300'}`}
          >
            <Settings2 size={14} />
          </button>
        </div>
      </div>

      {/* ── Settings Dropdown ────────────────────────────────────────── */}
      {showSettings && (
        <div className="flex flex-wrap items-center gap-6 px-4 py-3 bg-[#11111a] border-b border-gray-800/60 animate-in fade-in slide-in-from-top-1 duration-200">
          <label className="flex items-center gap-2 cursor-pointer group">
            <input type="checkbox" checked={showEma} onChange={e => setShowEma(e.target.checked)} className="sr-only" />
            <div className={`w-8 h-4 rounded-full p-0.5 transition-colors ${showEma ? 'bg-sky-500' : 'bg-gray-700'}`}>
              <div className={`w-3 h-3 bg-white rounded-full transition-transform ${showEma ? 'translate-x-4' : 'translate-x-0'}`} />
            </div>
            <span className="text-[10px] font-bold text-gray-400 group-hover:text-gray-200 transition-colors uppercase tracking-wider">EMA Ribbon</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer group">
            <input type="checkbox" checked={showVol} onChange={e => setShowVol(e.target.checked)} className="sr-only" />
            <div className={`w-8 h-4 rounded-full p-0.5 transition-colors ${showVol ? 'bg-sky-500' : 'bg-gray-700'}`}>
              <div className={`w-3 h-3 bg-white rounded-full transition-transform ${showVol ? 'translate-x-4' : 'translate-x-0'}`} />
            </div>
            <span className="text-[10px] font-bold text-gray-400 group-hover:text-gray-200 transition-colors uppercase tracking-wider">Volume & RVOL</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer group">
            <input type="checkbox" checked={showAdx} onChange={e => setShowAdx(e.target.checked)} className="sr-only" />
            <div className={`w-8 h-4 rounded-full p-0.5 transition-colors ${showAdx ? 'bg-sky-500' : 'bg-gray-700'}`}>
              <div className={`w-3 h-3 bg-white rounded-full transition-transform ${showAdx ? 'translate-x-4' : 'translate-x-0'}`} />
            </div>
            <span className="text-[10px] font-bold text-gray-400 group-hover:text-gray-200 transition-colors uppercase tracking-wider">ADX / DI Panel</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer group">
            <input type="checkbox" checked={showAtr} onChange={e => setShowAtr(e.target.checked)} className="sr-only" />
            <div className={`w-8 h-4 rounded-full p-0.5 transition-colors ${showAtr ? 'bg-sky-500' : 'bg-gray-700'}`}>
              <div className={`w-3 h-3 bg-white rounded-full transition-transform ${showAtr ? 'translate-x-4' : 'translate-x-0'}`} />
            </div>
            <span className="text-[10px] font-bold text-gray-400 group-hover:text-gray-200 transition-colors uppercase tracking-wider">ATR Panel</span>
          </label>
        </div>
      )}

      {/* ── EMA Legend ────────────────────────────────────────────────── */}
      {showEma && (
        <div className="flex items-center gap-4 px-4 py-2 bg-[#0d0d14] border-b border-gray-900">
          {['EMA 8', 'EMA 13', 'EMA 21', 'EMA 34', 'EMA 55'].map((label, i) => (
            <span key={label} className="flex items-center gap-1 text-[10px] font-mono">
              <span className="w-4 h-[2px] rounded-full inline-block" style={{ background: EMA_COLORS[i] }} />
              <span style={{ color: EMA_COLORS[i] }}>{label}</span>
            </span>
          ))}
          {showVol && (
            <span className="flex items-center gap-1 text-[10px] font-mono ml-2">
              <span className="w-4 h-[2px] rounded-full inline-block bg-fuchsia-300" />
              <span className="text-fuchsia-300">RVOL</span>
            </span>
          )}
        </div>
      )}

      {/* ── Candlestick + EMA + Volume pane ──────────────────────────── */}
      <div ref={mainRef} className="w-full" />

      {/* ── ADX/DI panel label ────────────────────────────────────────── */}
      {showAdx && (
        <>
          <div className="flex items-center gap-3 px-4 py-1.5 bg-[#0d0d14] border-t border-gray-900">
            <BarChart2 size={11} className="text-violet-400" />
            <span className="text-[10px] text-violet-400 font-mono font-bold">ADX / DI</span>
            <span className="flex items-center gap-1 text-[10px] font-mono">
              <span className="w-4 h-[2px] rounded-full inline-block bg-violet-400" />
              <span className="text-violet-400">ADX</span>
            </span>
            <span className="flex items-center gap-1 text-[10px] font-mono">
              <span className="w-4 h-[2px] rounded-full inline-block" style={{ background: UP_COLOR }} />
              <span style={{ color: UP_COLOR }}>+DI</span>
            </span>
            <span className="flex items-center gap-1 text-[10px] font-mono">
              <span className="w-4 h-[2px] rounded-full inline-block" style={{ background: DOWN_COLOR }} />
              <span style={{ color: DOWN_COLOR }}>-DI</span>
            </span>
            <span className="text-[10px] text-gray-600 ml-1">· dotted line = 25 threshold</span>
          </div>
          <div ref={adxRef} className="w-full" />
        </>
      )}

      {/* ── ATR panel label ───────────────────────────────────────────── */}
      {showAtr && (
        <>
          <div className="flex items-center gap-3 px-4 py-1.5 bg-[#0d0d14] border-t border-gray-900">
            <Activity size={11} className="text-orange-400" />
            <span className="text-[10px] text-orange-400 font-mono font-bold">ATR</span>
            <span className="text-[10px] text-gray-600">· Average True Range (volatility)</span>
          </div>
          <div ref={atrRef} className="w-full" />
        </>
      )}

      <div className="px-4 py-2 border-t border-gray-900 bg-[#0d0d14]">
        <p className="text-[10px] text-gray-700">Scroll to zoom · Drag to pan · Pre-market (4am) and post-market (8pm ET) included</p>
      </div>
    </div>
  )
}
