'use client'
import { useEffect, useState } from 'react'
import { getFloatBuckets, FloatBucket } from '@/lib/api'

const BUCKET_CONFIG: Record<string, { color: string; label: string; sub: string }> = {
  Nano:  { color: 'text-violet-400', label: 'Nano',  sub: '<10M' },
  Micro: { color: 'text-sky-400',    label: 'Micro', sub: '10–50M' },
  Small: { color: 'text-emerald-400',label: 'Small', sub: '50–200M' },
  'Mid+':{ color: 'text-gray-500',   label: 'Mid+',  sub: '>200M' },
}

const BUCKET_ORDER = ['Nano', 'Micro', 'Small', 'Mid+']

export default function FloatBucketSummary() {
  const [data, setData]       = useState<{ date: string; buckets: FloatBucket[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getFloatBuckets()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="grid grid-cols-3 gap-3 animate-pulse">
      {[1,2,3].map(i => <div key={i} className="h-16 bg-gray-800/60 rounded-lg" />)}
    </div>
  )

  const buckets = data?.buckets ?? []
  const bucketMap = Object.fromEntries(buckets.map(b => [b.bucket, b]))

  return (
    <div className="space-y-1">
      {BUCKET_ORDER.filter(b => bucketMap[b]).map(key => {
        const b = bucketMap[key]
        const cfg = BUCKET_CONFIG[key]
        return (
          <div
            key={key}
            className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-800/40 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold ${cfg.color}`}>{cfg.label}</span>
              <span className="text-[10px] text-gray-700">{cfg.sub}</span>
            </div>
            <div className="flex items-center gap-4 text-xs">
              <span className="text-gray-500 font-mono">{b.count} tickers</span>
              <span className="text-emerald-400 font-mono font-semibold w-16 text-right">
                +{b.avg_gap_pct?.toFixed(1) ?? '—'}% avg
              </span>
            </div>
          </div>
        )
      })}
      {buckets.length === 0 && (
        <div className="text-center py-6 text-gray-700 text-xs">
          No ingest data for today yet
        </div>
      )}
    </div>
  )
}
