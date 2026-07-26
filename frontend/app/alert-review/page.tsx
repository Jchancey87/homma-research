'use client'

import { useState, useEffect, useCallback, useMemo, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  getAlertReviewTop10,
  getAlertReviewDetail,
  getAlertDates,
  AlertReviewTop10Data,
  AlertReviewSymbol,
  AlertReviewDetailData,
} from '@/lib/api'
import AlertReviewSummaryBar from '@/components/AlertReviewSummaryBar'
import AlertReviewDetailChart from '@/components/AlertReviewDetailChart'
import { Loader2, Zap, Search, AlertOctagon, Flame, ArrowUpRight } from 'lucide-react'

function AlertReviewContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const todayStr = new Date().toISOString().split('T')[0]
  const dateParam = searchParams.get('date') || todayStr
  const initialSymbol = searchParams.get('symbol') || ''

  const [date, setDate] = useState<string>(dateParam)
  const [availableDates, setAvailableDates] = useState<string[]>([])
  const [top10Data, setTop10Data] = useState<AlertReviewTop10Data | null>(null)
  const [selectedSymbol, setSelectedSymbol] = useState<string>(initialSymbol)
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [detailData, setDetailData] = useState<AlertReviewDetailData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [detailLoading, setDetailLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getAlertDates()
      .then((dates) => {
        if (dates && dates.length > 0) {
          setAvailableDates(dates)
        }
      })
      .catch(() => {})
  }, [])

  const fetchTop10Data = useCallback(async (targetDate: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getAlertReviewTop10(targetDate)
      setTop10Data(data)
      if (data.top10_gainers && data.top10_gainers.length > 0) {
        // If current selected symbol is not in top 10, default to first top 10 symbol
        const exists = data.top10_gainers.some((g: AlertReviewSymbol) => g.symbol === selectedSymbol)
        if (!exists) {
          setSelectedSymbol(data.top10_gainers[0].symbol)
        }
      }
    } catch (e) {
      const err = e as Error
      setError(err.message || 'Failed to load Top 10 alert review')
    } finally {
      setLoading(false)
    }
  }, [selectedSymbol])

  useEffect(() => {
    fetchTop10Data(date)
  }, [date, fetchTop10Data])

  const fetchSymbolDetail = useCallback(async (sym: string, targetDate: string) => {
    if (!sym) return
    setDetailLoading(true)
    try {
      const detail = await getAlertReviewDetail(sym, targetDate)
      setDetailData(detail)
    } catch (e) {
      setDetailData(null)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedSymbol) {
      fetchSymbolDetail(selectedSymbol, date)
    }
  }, [selectedSymbol, date, fetchSymbolDetail])

  const handleDateChange = (newDate: string) => {
    setDate(newDate)
    router.push(`/alert-review?date=${newDate}`)
  }

  const handleSelectSymbol = (sym: string) => {
    setSelectedSymbol(sym)
    router.push(`/alert-review?date=${date}&symbol=${sym}`)
  }

  const filteredGainers = useMemo(() => {
    if (!top10Data?.top10_gainers) return []
    if (!searchQuery.trim()) return top10Data.top10_gainers
    const query = searchQuery.trim().toUpperCase()
    return top10Data.top10_gainers.filter((g) => g.symbol.includes(query))
  }, [top10Data, searchQuery])

  const selectedGainer = useMemo(() => {
    return top10Data?.top10_gainers.find((g) => g.symbol === selectedSymbol)
  }, [top10Data, selectedSymbol])

  return (
    <div className="space-y-4 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#222222] pb-3">
        <div>
          <h1 className="text-lg font-black tracking-wider text-white uppercase flex items-center gap-2">
            <Zap className="text-yellow-400" size={20} />
            Alert Review Post-Mortem (Top 10 Gainers)
          </h1>
          <p className="text-xs text-gray-400 mt-0.5">
            End-of-day alert performance review strictly for the day&apos;s Top 10 Gainers (excluding noisy NEAR_HOD pings)
          </p>
        </div>
      </div>

      {/* Summary Statistics Bar */}
      <AlertReviewSummaryBar
        summary={top10Data?.summary ?? null}
        selectedDate={date}
        availableDates={availableDates}
        onDateChange={handleDateChange}
      />

      {loading && !top10Data && (
        <div className="flex items-center justify-center py-24 text-gray-500 gap-2">
          <Loader2 className="animate-spin" size={20} />
          <span className="text-xs">Computing Top 10 gainers alert performance & MFE metrics...</span>
        </div>
      )}

      {error && !loading && (
        <div className="bg-red-950/40 border border-red-800/50 p-4 text-xs text-red-400 flex items-center gap-2">
          <AlertOctagon size={16} />
          <span>{error}</span>
        </div>
      )}

      {!loading && top10Data && (
        <div className="space-y-4">
          {/* Top 10 Gainers Selector Bar & Search Input */}
          <div className="bg-[#0b0b0b] border border-[#1f1f1f] p-3 space-y-3">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-[#181818] pb-2">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-white">
                <Flame size={15} className="text-yellow-400" />
                <span>Top 10 Gainers on {date}</span>
                <span className="text-[10px] text-gray-500 font-normal">
                  ({top10Data.top10_gainers.length} symbols)
                </span>
              </div>

              {/* Stock Search Input */}
              <div className="relative w-full sm:w-64">
                <Search size={14} className="absolute left-2.5 top-2.5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search stock..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-[#141414] border border-[#262626] text-white placeholder-gray-500 pl-8 pr-3 py-1 text-xs focus:outline-none focus:border-yellow-500 uppercase font-mono"
                />
              </div>
            </div>

            {/* Ticker Pills Bar */}
            {filteredGainers.length === 0 ? (
              <div className="text-xs text-gray-500 py-2">
                No Top 10 stock matching &quot;{searchQuery}&quot;
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {filteredGainers.map((gainer) => {
                  const isSelected = gainer.symbol === selectedSymbol
                  const hasAlerts = gainer.alert_count > 0
                  return (
                    <button
                      key={gainer.symbol}
                      onClick={() => handleSelectSymbol(gainer.symbol)}
                      className={`px-3 py-2 text-xs font-mono border transition-all flex items-center gap-2 ${
                        isSelected
                          ? 'bg-yellow-500/10 border-yellow-500 text-yellow-400 font-bold'
                          : 'bg-[#111111] border-[#222222] text-gray-300 hover:border-gray-600 hover:text-white'
                      }`}
                    >
                      <span className="font-bold">{gainer.symbol}</span>

                      {gainer.gap_pct !== null && (
                        <span className="text-[10px] text-gray-400">
                          +{gainer.gap_pct.toFixed(0)}%
                        </span>
                      )}

                      {hasAlerts ? (
                        <span className="bg-[#00ff00]/10 text-[#00ff00] border border-[#00ff00]/30 text-[9px] px-1 py-0.5 font-bold">
                          {gainer.alert_count} alert{gainer.alert_count > 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span className="bg-yellow-500/10 text-yellow-400 border border-yellow-500/30 text-[9px] px-1 py-0.5">
                          Missed
                        </span>
                      )}

                      {gainer.best_15m_mfe > 0 && (
                        <span className="text-[10px] font-bold text-[#00ff00] flex items-center">
                          <ArrowUpRight size={10} />
                          +{gainer.best_15m_mfe.toFixed(1)}%
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          {/* Selected Symbol Detail Workspace */}
          {detailLoading && (
            <div className="flex items-center justify-center py-20 text-gray-500 gap-2 bg-[#090909] border border-[#1f1f1f]">
              <Loader2 className="animate-spin" size={20} />
              <span className="text-xs">Loading chart & alert data for {selectedSymbol}...</span>
            </div>
          )}

          {!detailLoading && detailData && (
            <div className="space-y-3">
              {/* Selected Header Bar */}
              <div className="bg-[#0d0d0d] border border-[#1f1f1f] p-3 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <h2 className="text-base font-black text-white uppercase tracking-wider">
                    {detailData.symbol} Post-Mortem
                  </h2>
                  <span className="text-xs text-gray-400">({date})</span>
                </div>

                {selectedGainer && (
                  <div className="flex items-center gap-4 text-xs font-mono">
                    {selectedGainer.gap_pct !== null && (
                      <div>
                        <span className="text-gray-500">Gap: </span>
                        <span className="text-white font-bold">+{selectedGainer.gap_pct.toFixed(1)}%</span>
                      </div>
                    )}

                    <div>
                      <span className="text-gray-500">Alerts: </span>
                      <span className="text-yellow-400 font-bold">{selectedGainer.alert_count}</span>
                    </div>

                    {selectedGainer.best_15m_mfe > 0 && (
                      <div>
                        <span className="text-gray-500">Best 15m MFE: </span>
                        <span className="text-[#00ff00] font-bold">+{selectedGainer.best_15m_mfe.toFixed(1)}%</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Full Interactive Chart + MFE/MAE Breakdown Table */}
              <AlertReviewDetailChart
                symbol={detailData.symbol}
                date={date}
                chartData={detailData.chart}
                alerts={detailData.alerts}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AlertReviewPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-24 text-gray-500 gap-2 font-mono text-xs">
          <Loader2 className="animate-spin" size={20} />
          <span>Loading Alert Review...</span>
        </div>
      }
    >
      <AlertReviewContent />
    </Suspense>
  )
}
