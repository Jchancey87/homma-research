'use client'

import { useState, useEffect, useCallback, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  getAlertReviewGrid,
  getAlertDates,
  AlertReviewGridData,
} from '@/lib/api'
import AlertReviewSummaryBar from '@/components/AlertReviewSummaryBar'
import AlertReviewMiniChart from '@/components/AlertReviewMiniChart'
import { Loader2, Zap, AlertOctagon } from 'lucide-react'

function AlertReviewContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const todayStr = new Date().toISOString().split('T')[0]
  const dateParam = searchParams.get('date') || todayStr

  const [date, setDate] = useState<string>(dateParam)
  const [availableDates, setAvailableDates] = useState<string[]>([])
  const [gridData, setGridData] = useState<AlertReviewGridData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
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

  const fetchGridData = useCallback(async (targetDate: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getAlertReviewGrid(targetDate)
      setGridData(data)
    } catch (e) {
      const err = e as Error
      setError(err.message || 'Failed to load alert review grid')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchGridData(date)
  }, [date, fetchGridData])

  const handleDateChange = (newDate: string) => {
    setDate(newDate)
    router.push(`/alert-review?date=${newDate}`)
  }

  const handleExpandSymbol = (symbol: string) => {
    router.push(`/alert-review/${symbol}?date=${date}`)
  }

  return (
    <div className="space-y-4 font-mono">
      {/* Title Header */}
      <div className="flex items-center justify-between border-b border-[#222222] pb-3">
        <div>
          <h1 className="text-lg font-black tracking-wider text-white uppercase flex items-center gap-2">
            <Zap className="text-yellow-400" size={20} />
            Alert Review Post-Mortem
          </h1>
          <p className="text-xs text-gray-400 mt-0.5">
            End-of-day overview of alert accuracy, 15m MFE performance, and missed momentum runners
          </p>
        </div>
      </div>

      {/* Summary Statistics Bar */}
      <AlertReviewSummaryBar
        summary={gridData?.summary ?? null}
        selectedDate={date}
        availableDates={availableDates}
        onDateChange={handleDateChange}
      />

      {loading && !gridData && (
        <div className="flex items-center justify-center py-24 text-gray-500 gap-2">
          <Loader2 className="animate-spin" size={20} />
          <span className="text-xs">Computing alert performance & MFE metrics...</span>
        </div>
      )}

      {error && !loading && (
        <div className="bg-red-950/40 border border-red-800/50 p-4 text-xs text-red-400 flex items-center gap-2">
          <AlertOctagon size={16} />
          <span>{error}</span>
        </div>
      )}

      {!loading && gridData && (
        <div className="space-y-6">
          {/* Section 1: Alerted Symbols */}
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-[#1f1f1f] pb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#00ff00]" />
                <h2 className="text-xs font-black text-white uppercase tracking-wider">
                  Section 1: Alerted Symbols ({gridData.alerted_symbols.length})
                </h2>
              </div>
              <span className="text-[10px] text-gray-400">Sorted by best 15m MFE %</span>
            </div>

            {gridData.alerted_symbols.length === 0 ? (
              <div className="bg-[#090909] border border-[#1f1f1f] p-6 text-center text-xs text-gray-500">
                No alerts logged on {date}.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {gridData.alerted_symbols.map((symData) => (
                  <AlertReviewMiniChart
                    key={symData.symbol}
                    symbolData={symData}
                    date={date}
                    onExpand={handleExpandSymbol}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Section 2: Remaining Top Gainers */}
          <div className="space-y-3 pt-4 border-t border-[#222222]">
            <div className="flex items-center justify-between border-b border-[#1f1f1f] pb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-yellow-400" />
                <h2 className="text-xs font-black text-white uppercase tracking-wider">
                  Section 2: Remaining Top Gainers (Missed Opportunities) ({gridData.remaining_gainers.length})
                </h2>
              </div>
              <span className="text-[10px] text-gray-400">Sorted by intraday Gap %</span>
            </div>

            {gridData.remaining_gainers.length === 0 ? (
              <div className="bg-[#090909] border border-[#1f1f1f] p-6 text-center text-xs text-gray-500">
                No additional un-alerted gainers found for {date}.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {gridData.remaining_gainers.map((symData) => (
                  <AlertReviewMiniChart
                    key={symData.symbol}
                    symbolData={symData}
                    date={date}
                    onExpand={handleExpandSymbol}
                  />
                ))}
              </div>
            )}
          </div>
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
