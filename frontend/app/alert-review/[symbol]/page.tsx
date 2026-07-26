'use client'

import { useEffect, useState, useCallback, use, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { getAlertReviewDetail, AlertReviewDetailData } from '@/lib/api'
import AlertReviewDetailChart from '@/components/AlertReviewDetailChart'
import { ArrowLeft, Loader2, Zap, AlertTriangle } from 'lucide-react'

interface Params {
  symbol: string
}

function AlertReviewDetailContent({ params }: { params: Promise<Params> }) {
  const { symbol } = use(params)
  const searchParams = useSearchParams()

  const todayStr = new Date().toISOString().split('T')[0]
  const date = searchParams.get('date') || todayStr

  const [detailData, setDetailData] = useState<AlertReviewDetailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getAlertReviewDetail(symbol, date)
      setDetailData(data)
    } catch (e) {
      const err = e as Error
      setError(err.message || `No chart or alert data for ${symbol}`)
    } finally {
      setLoading(false)
    }
  }, [symbol, date])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return (
    <div className="space-y-4 font-mono">
      {/* Back Button & Header */}
      <div className="flex items-center justify-between border-b border-[#222222] pb-3">
        <div className="flex items-center gap-3">
          <Link
            href={`/alert-review?date=${date}`}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-white border border-[#333333] px-2 py-1 transition-colors"
          >
            <ArrowLeft size={14} />
            Back to Grid
          </Link>
          <h1 className="text-lg font-black tracking-wider text-white uppercase flex items-center gap-2">
            <Zap className="text-yellow-400" size={20} />
            {symbol.toUpperCase()} — Alert Review ({date})
          </h1>
        </div>
      </div>

      {loading && !detailData && (
        <div className="flex items-center justify-center py-24 text-gray-500 gap-2">
          <Loader2 className="animate-spin" size={20} />
          <span className="text-xs">Loading detail chart & alert post-mortem...</span>
        </div>
      )}

      {error && !loading && (
        <div className="bg-red-950/40 border border-red-800/50 p-4 text-xs text-red-400 flex items-center gap-2">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {!loading && detailData && (
        <AlertReviewDetailChart
          symbol={symbol.toUpperCase()}
          date={date}
          chartData={detailData.chart}
          alerts={detailData.alerts}
        />
      )}
    </div>
  )
}

export default function AlertReviewDetailPage({ params }: { params: Promise<Params> }) {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-24 text-gray-500 gap-2 font-mono text-xs">
          <Loader2 className="animate-spin" size={20} />
          <span>Loading detail view...</span>
        </div>
      }
    >
      <AlertReviewDetailContent params={params} />
    </Suspense>
  )
}
