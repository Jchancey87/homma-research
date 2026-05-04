import { getGainersSummary, GainerSummary } from '@/lib/api'
import Link from 'next/link'

function fmt(n: number | null, decimals = 1, suffix = '') {
  if (n == null) return '—'
  return n.toFixed(decimals) + suffix
}

function fmtFloat(n: number | null) {
  if (n == null) return '—'
  const m = n / 1_000_000
  return m >= 1000 ? `${(m / 1000).toFixed(1)}B` : `${m.toFixed(1)}M`
}

function NewsBadge({ fresh }: { fresh: boolean | null }) {
  if (fresh == null) return null
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold ${
      fresh ? 'bg-emerald-500/20 text-emerald-400' : 'bg-gray-700 text-gray-500'
    }`}>
      {fresh ? '🗞 Fresh' : 'Stale'}
    </span>
  )
}

export default async function TodayGainers() {
  let summary: GainerSummary | null = null
  try { summary = await getGainersSummary() } catch { /* backend may be down */ }

  if (!summary || !summary.date) {
    return (
      <div className="text-gray-600 text-sm py-6 text-center">
        No ingest data yet — run the ingestion job to populate today&apos;s gainers.
      </div>
    )
  }

  const { date, total, gainers } = summary
  const dateLabel = new Date(date + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric'
  })

  return (
    <div className="space-y-4">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-gray-200">{dateLabel}</span>
          <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-500/15 text-emerald-400 font-medium">
            {total} gainers ingested
          </span>
        </div>
        <Link
          href={`/gainers?date=${date}`}
          className="text-xs text-gray-500 hover:text-emerald-400 transition-colors"
        >
          View all →
        </Link>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b border-gray-800">
              <th className="pb-2 pr-4 font-medium">Ticker</th>
              <th className="pb-2 pr-4 font-medium text-right">Gap %</th>
              <th className="pb-2 pr-4 font-medium text-right">Float</th>
              <th className="pb-2 pr-4 font-medium text-right">RVOL</th>
              <th className="pb-2 pr-4 font-medium">Sector</th>
              <th className="pb-2 font-medium">Catalyst</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {gainers.map((g, i) => (
              <tr key={g.ticker} className="hover:bg-gray-800/40 transition-colors group">
                <td className="py-2.5 pr-4">
                  <Link
                    href={`/research?ticker=${g.ticker}&date=${date}`}
                    className="font-bold text-white group-hover:text-emerald-400 transition-colors flex items-center gap-2"
                  >
                    <span className="text-gray-600 text-xs w-4">{i + 1}</span>
                    {g.ticker}
                  </Link>
                </td>
                <td className="py-2.5 pr-4 text-right font-mono">
                  <span className="text-emerald-400 font-semibold">
                    +{fmt(g.gap_pct)}%
                  </span>
                </td>
                <td className="py-2.5 pr-4 text-right font-mono text-gray-400">
                  {fmtFloat(g.float_shares)}
                </td>
                <td className="py-2.5 pr-4 text-right font-mono">
                  <span className={g.rvol_15m != null && g.rvol_15m >= 5 ? 'text-amber-400' : 'text-gray-400'}>
                    {fmt(g.rvol_15m)}x
                  </span>
                </td>
                <td className="py-2.5 pr-4 text-gray-500 text-xs">{g.sector ?? '—'}</td>
                <td className="py-2.5">
                  <div className="flex items-center gap-2">
                    <NewsBadge fresh={g.news_fresh} />
                    {g.news_headline && (
                      <span className="text-gray-500 text-xs truncate max-w-[240px]" title={g.news_headline}>
                        {g.news_headline}
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
