'use client'

import { useEffect, useState, useCallback } from 'react'
import { getMomentumBreadth, MomentumBreadthData } from '@/lib/api'
import { Activity, Gauge, Layers, AlertOctagon, RefreshCw } from 'lucide-react'

export default function MomentumBreadthBanner() {
  const [data, setData] = useState<MomentumBreadthData | null>(null)
  const [loading, setLoading] = useState(true)
  const [priceFilterEnabled, setPriceFilterEnabled] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const loadData = useCallback(async (filter: boolean) => {
    try {
      const res = await getMomentumBreadth(filter)
      setData(res)
      setLastUpdated(new Date())
    } catch (err) {
      console.error('Failed to load momentum breadth data', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Sync price filter from local storage
  useEffect(() => {
    const val = localStorage.getItem('price-filter-enabled')
    const currentFilter = val !== null ? val === 'true' : true
    setPriceFilterEnabled(currentFilter)
    loadData(currentFilter)

    const handleSync = () => {
      const syncedVal = localStorage.getItem('price-filter-enabled')
      const newFilter = syncedVal !== null ? syncedVal === 'true' : true
      setPriceFilterEnabled(newFilter)
      setLoading(true)
      loadData(newFilter)
    }

    window.addEventListener('price-filter-changed', handleSync)
    return () => window.removeEventListener('price-filter-changed', handleSync)
  }, [loadData])

  // Polling every 60 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      loadData(priceFilterEnabled)
    }, 60000)
    return () => clearInterval(timer)
  }, [priceFilterEnabled, loadData])

  // Helper to render Dominant Float theme classes
  const getFloatThemeBadge = (theme: string) => {
    const isMicro = theme.includes('MICRO')
    const isMid = theme.includes('MID')
    
    if (isMicro) {
      return 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
    } else if (isMid) {
      return 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
    } else {
      return 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
    }
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 w-full bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800/80 rounded-2xl p-4 shadow-sm hover:shadow-md dark:hover:shadow-black/30 hover:border-gray-300 dark:hover:border-gray-700/80 transition-all duration-300">
      
      {/* Block 1: Small-Cap Market Breadth */}
      <div className="flex flex-col justify-between p-2 border-b sm:border-b-0 sm:border-r border-gray-100 dark:border-gray-900/60 pr-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
            <Activity size={12} className="text-gray-400" />
            Small-Cap A/D Ratio
          </span>
        </div>
        {loading || !data ? (
          <div className="h-9 w-24 bg-gray-100 dark:bg-gray-900 animate-pulse rounded-lg mt-1" />
        ) : (
          <div className="flex flex-col mt-0.5">
            <span className={`text-2xl font-black font-mono tracking-tight leading-none ${data.small_cap_ad.is_bullish ? 'text-emerald-500 dark:text-emerald-450' : 'text-gray-900 dark:text-white'}`}>
              {data.small_cap_ad.ratio_str}
            </span>
            <span className="text-[10px] text-gray-400 dark:text-gray-500 mt-1 font-medium font-mono">
              <span className="text-emerald-500">{data.small_cap_ad.advancing} G</span> / <span className="text-red-500">{data.small_cap_ad.declining} R</span>
            </span>
          </div>
        )}
      </div>

      {/* Block 2: Aggregated RVOL Factor */}
      <div className="flex flex-col justify-between p-2 border-b sm:border-b-0 lg:border-r border-gray-100 dark:border-gray-900/60 px-2 lg:pr-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
            <Gauge size={12} className="text-gray-400" />
            Top-5 Avg RVOL
          </span>
        </div>
        {loading || !data ? (
          <div className="h-9 w-24 bg-gray-100 dark:bg-gray-900 animate-pulse rounded-lg mt-1" />
        ) : (
          <div className="flex flex-col mt-0.5">
            <span className={`text-2xl font-black font-mono tracking-tight leading-none ${data.top5_avg_rvol.is_high ? 'text-emerald-500 dark:text-emerald-450' : 'text-gray-900 dark:text-white'}`}>
              {data.top5_avg_rvol.avg_rvol.toFixed(1)}x
            </span>
            <span className={`text-[10px] mt-1 font-semibold leading-none ${data.top5_avg_rvol.is_high ? 'text-emerald-500/80 dark:text-emerald-400/80' : 'text-gray-400 dark:text-gray-500'}`}>
              {data.top5_avg_rvol.status}
            </span>
          </div>
        )}
      </div>

      {/* Block 3: Float Theme Identifier */}
      <div className="flex flex-col justify-between p-2 border-b sm:border-b-0 sm:border-r border-gray-100 dark:border-gray-900/60 px-2 lg:pr-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
            <Layers size={12} className="text-gray-400" />
            Dominant Float Theme
          </span>
        </div>
        {loading || !data ? (
          <div className="h-9 w-24 bg-gray-100 dark:bg-gray-900 animate-pulse rounded-lg mt-1" />
        ) : (
          <div className="flex flex-col items-start mt-0.5">
            <span className={`inline-flex px-2.5 py-1 rounded-lg text-xs font-black uppercase tracking-wider ${getFloatThemeBadge(data.dominant_float_theme.theme)}`}>
              {data.dominant_float_theme.theme}
            </span>
            <span className="text-[9px] text-gray-400 dark:text-gray-500 mt-1 font-mono">
              Small: {data.dominant_float_theme.counts['MICRO-FLOAT (<2M)'] || 0} · Mid: {data.dominant_float_theme.counts['MID-FLOAT (2M-20M)'] || 0} · Large: {data.dominant_float_theme.counts['LARGE-FLOAT (>20M)'] || 0}
            </span>
          </div>
        )}
      </div>

      {/* Block 4: Volatility Halts Tracker */}
      <div className="flex flex-col justify-between p-2 px-2">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
            <AlertOctagon size={12} className="text-gray-400" />
            Active Volatility Halts
          </span>
          {lastUpdated && (
            <button
              onClick={() => {
                setLoading(true)
                loadData(priceFilterEnabled)
              }}
              className="text-gray-400 hover:text-emerald-400 transition-colors"
              title="Refresh banner statistics"
            >
              <RefreshCw size={10} className={loading ? 'animate-spin' : ''} />
            </button>
          )}
        </div>
        {loading || !data ? (
          <div className="h-9 w-24 bg-gray-100 dark:bg-gray-900 animate-pulse rounded-lg mt-1" />
        ) : (
          <div className="flex flex-col mt-0.5">
            <span className={`text-2xl font-black font-mono tracking-tight leading-none ${data.active_halts.count > 0 ? 'text-amber-500 dark:text-amber-400' : 'text-gray-950 dark:text-white'}`}>
              {data.active_halts.count} {data.active_halts.count === 1 ? 'Halt' : 'Halts'} Active
            </span>
            <div className="flex items-center gap-1 flex-wrap mt-1">
              {data.active_halts.tickers.length === 0 ? (
                <span className="text-[10px] text-gray-400 dark:text-gray-500 font-medium">No halts in watch list</span>
              ) : (
                data.active_halts.tickers.map(ticker => (
                  <span
                    key={ticker}
                    className="inline-flex items-center px-1.5 py-0.5 rounded font-mono text-[9px] font-bold bg-amber-500/10 text-amber-500 dark:bg-amber-500/10 dark:text-amber-400 border border-amber-500/20"
                  >
                    {ticker}
                  </span>
                ))
              )}
            </div>
          </div>
        )}
      </div>

    </div>
  )
}
