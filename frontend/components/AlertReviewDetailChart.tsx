'use client'

import { useMemo, useEffect, useRef, useState } from 'react'
import {
  createChart, IChartApi,
  CandlestickSeries, LineSeries, HistogramSeries,
  CrosshairMode, SeriesMarker, Time, createSeriesMarkers,
} from 'lightweight-charts'
import { AlertReviewItem } from '@/lib/api'
import {
  CHART_BG, GRID_COLOR, TEXT_COLOR, UP_COLOR, DOWN_COLOR, UP_VOL_COLOR, DOWN_VOL_COLOR,
  EMA9_COL, EMA20_COL, EMA50_COL, VWAP_COL,
  ChartData, OhlcBar, LinePt, HistoPt, dedupSort, shiftChartDataTime, calcEMA,
} from '@/lib/chart'
import { Zap } from 'lucide-react'

interface Props {
  symbol: string
  date: string
  chartData: Record<string, unknown>
  alerts: AlertReviewItem[]
}

export default function AlertReviewDetailChart({
  symbol,
  date,
  chartData,
  alerts,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const [selectedAlert, setSelectedAlert] = useState<AlertReviewItem | null>(
    alerts.length > 0 ? alerts[0] : null
  )

  const sma200Info = useMemo(() => {
    if (!chartData?.ohlcv) return null
    const bars = chartData.ohlcv as OhlcBar[]
    if (!bars || bars.length === 0) return null
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
  }, [chartData?.ohlcv])

  useEffect(() => {
    if (!chartData || !containerRef.current) return

    chartRef.current?.remove()

    const localOffset = -new Date().getTimezoneOffset() * 60
    const rawData = {
      ohlcv: chartData.ohlcv as OhlcBar[],
      volume: chartData.volume as HistoPt[],
      ema_9: (chartData.ema_9 as LinePt[]) ?? [],
      ema_20: (chartData.ema_20 as LinePt[]) ?? [],
      ema_50: (chartData.ema_50 as LinePt[]) ?? [],
      vwap: (chartData.vwap as LinePt[]) ?? [],
    }
    const data = shiftChartDataTime(rawData as unknown as ChartData, localOffset)

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: 'transparent' },
        textColor: TEXT_COLOR,
        fontSize: 11,
        fontFamily: "Consolas, 'Roboto Mono', Monaco, ui-monospace, monospace",
      },
      grid: {
        vertLines: { color: GRID_COLOR, style: 1 },
        horzLines: { color: GRID_COLOR, style: 1 },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#262626', textColor: TEXT_COLOR },
      timeScale: {
        borderColor: '#262626',
        timeVisible: true,
        secondsVisible: false,
      },
      width: containerRef.current.clientWidth,
      height: 480,
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
    const ema9Data = data.ema_9?.length ? data.ema_9 : calcEMA(data.ohlcv, 9)
    if (ema9Data.length) {
      const s = chart.addSeries(LineSeries, { color: EMA9_COL, lineWidth: 1, title: 'EMA 9' })
      s.setData(dedupSort(ema9Data))
    }

    const ema20Data = data.ema_20?.length ? data.ema_20 : calcEMA(data.ohlcv, 20)
    if (ema20Data.length) {
      const s = chart.addSeries(LineSeries, { color: EMA20_COL, lineWidth: 1, title: 'EMA 20' })
      s.setData(dedupSort(ema20Data))
    }

    const ema50Data = data.ema_50?.length ? data.ema_50 : calcEMA(data.ohlcv, 50)
    if (ema50Data.length) {
      const s = chart.addSeries(LineSeries, { color: EMA50_COL, lineWidth: 1, title: 'EMA 50' })
      s.setData(dedupSort(ema50Data))
    }

    if (data.vwap?.length) {
      const s = chart.addSeries(LineSeries, { color: VWAP_COL, lineWidth: 1, lineStyle: 2, title: 'VWAP' })
      s.setData(dedupSort(data.vwap))
    }

    // Set Alert Markers
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
            text: `${a.alert_type} (${a.priority_tier})`,
          })
        } catch {
          // ignore
        }
      })
      if (markers.length) {
        createSeriesMarkers(candles, markers)
      }
    }

    // Price lines for selected Tier 1 alert (Entry & Stop lines)
    if (selectedAlert && selectedAlert.priority_tier === 'Tier 1') {
      if (selectedAlert.trigger_price) {
        candles.createPriceLine({
          price: selectedAlert.trigger_price,
          color: '#26a69a',
          lineWidth: 1,
          lineStyle: 0,
          title: `Trigger $${selectedAlert.trigger_price.toFixed(2)}`,
        })
      }
      if (selectedAlert.stop_price) {
        candles.createPriceLine({
          price: selectedAlert.stop_price,
          color: '#ef5350',
          lineWidth: 1,
          lineStyle: 2,
          title: `Stop $${selectedAlert.stop_price.toFixed(2)}`,
        })
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
  }, [chartData, alerts, selectedAlert])

  return (
    <div className="flex flex-col gap-4 font-mono">
      {/* Chart Canvas */}
      <div className="relative bg-black border border-[#262626] p-2 overflow-hidden select-none">
        <div className="relative z-10 flex items-center justify-between px-2 py-1 mb-1 border-b border-[#222222] text-xs">
          <div className="flex items-center gap-3">
            <span className="font-black text-white text-sm uppercase tracking-wider">{symbol}</span>
            <span className="text-gray-400">Date: {date}</span>
            {sma200Info != null && (
              <span
                className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-none text-[9px] font-black uppercase tracking-wider border ${
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
          <div className="flex items-center gap-3 text-[10px]">
            <span className="text-[#38bdf8]">■ EMA 9</span>
            <span className="text-[#f59e0b]">■ EMA 20</span>
            <span className="text-[#ab47bc]">■ EMA 50</span>
            <span className="text-[#ffffff]">-- VWAP</span>
          </div>
        </div>

        {/* Chart Canvas */}
        <div ref={containerRef} className="w-full h-[480px] relative z-0" />

        {/* Large Transparent Stock Ticker Symbol Watermark */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-5 select-none overflow-hidden">
          <span className="text-7xl sm:text-8xl font-black text-white/[0.12] tracking-widest uppercase scale-125">
            {symbol}
          </span>
        </div>
      </div>

      {/* Alert Breakdown & MFE/MAE Table */}
      <div className="bg-[#080808] border border-[#262626] p-3 flex flex-col gap-3">
        <div className="flex items-center justify-between border-b border-[#1f1f1f] pb-2">
          <span className="font-bold text-xs uppercase tracking-wider text-white flex items-center gap-1.5">
            <Zap size={14} className="text-yellow-400" />
            Alert Post-Mortem Analysis ({alerts.length} Trigger{alerts.length === 1 ? '' : 's'})
          </span>
          <span className="text-[10px] text-gray-500">
            Select an alert below to overlay entry/stop levels
          </span>
        </div>

        {alerts.length === 0 ? (
          <div className="text-xs text-gray-500 p-4 text-center">
            No alerts logged for {symbol} on {date}.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[#222222] text-gray-400 text-[11px] uppercase tracking-wider">
                  <th className="py-2 px-2">Time</th>
                  <th className="py-2 px-2">Type</th>
                  <th className="py-2 px-2">Tier</th>
                  <th className="py-2 px-2">Score</th>
                  <th className="py-2 px-2">Price</th>
                  <th className="py-2 px-2">RVOL</th>
                  <th className="py-2 px-2">5m MFE</th>
                  <th className="py-2 px-2">15m MFE</th>
                  <th className="py-2 px-2">30m MFE</th>
                  <th className="py-2 px-2">EOD MFE</th>
                  <th className="py-2 px-2">15m MAE</th>
                  <th className="py-2 px-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#181818]">
                {alerts.map((a) => {
                  const isSelected = selectedAlert?.id === a.id
                  const mfe15 = a.mfe_mae?.['15m']?.mfe_pct ?? 0
                  const mae15 = a.mfe_mae?.['15m']?.mae_pct ?? 0
                  const timeStr = a.alert_time
                    ? new Date(a.alert_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : '--'

                  return (
                    <tr
                      key={a.id}
                      onClick={() => setSelectedAlert(a)}
                      className={`cursor-pointer transition-colors ${
                        isSelected ? 'bg-[#181818] border-l-2 border-l-[#00ff00]' : 'hover:bg-[#111111]'
                      }`}
                    >
                      <td className="py-2 px-2 font-bold text-white">{timeStr}</td>
                      <td className="py-2 px-2">
                        <span className="font-bold text-[#00f0ff]">{a.alert_type}</span>
                      </td>
                      <td className="py-2 px-2">
                        <span
                          className={`px-1.5 py-0.5 text-[10px] font-bold ${
                            a.priority_tier === 'Tier 1'
                              ? 'bg-red-950/60 text-red-400 border border-red-800/40'
                              : a.priority_tier === 'Tier 2'
                              ? 'bg-yellow-950/60 text-yellow-400 border border-yellow-800/40'
                              : 'bg-blue-950/60 text-blue-400 border border-blue-800/40'
                          }`}
                        >
                          {a.priority_tier}
                        </span>
                      </td>
                      <td className="py-2 px-2 font-bold text-gray-300">{a.priority_score}</td>
                      <td className="py-2 px-2 text-white">${a.trigger_price?.toFixed(2)}</td>
                      <td className="py-2 px-2 text-gray-300">{a.rel_vol?.toFixed(1)}x</td>
                      <td className="py-2 px-2 text-gray-300">
                        +{a.mfe_mae?.['5m']?.mfe_pct.toFixed(1)}%
                      </td>
                      <td className="py-2 px-2 font-bold">
                        <span className={mfe15 >= 2.0 ? 'text-[#00ff00]' : 'text-yellow-400'}>
                          +{mfe15.toFixed(1)}%
                        </span>
                      </td>
                      <td className="py-2 px-2 text-gray-300">
                        +{a.mfe_mae?.['30m']?.mfe_pct.toFixed(1)}%
                      </td>
                      <td className="py-2 px-2 text-gray-300">
                        +{a.mfe_mae?.['eod']?.mfe_pct.toFixed(1)}%
                      </td>
                      <td className="py-2 px-2 text-[#ff003c] font-bold">
                        {mae15.toFixed(1)}%
                      </td>
                      <td className="py-2 px-2">
                        {a.suppressed_reason ? (
                          <span className="text-gray-500 text-[10px] italic">
                            {a.suppressed_reason}
                          </span>
                        ) : (
                          <span className="text-[#00ff00] text-[10px] font-bold">DISPATCHED</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
