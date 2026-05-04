'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getWatchlist, WatchlistItem, markWatchlistViewed } from '@/lib/api'
import { ExternalLink, Bookmark } from 'lucide-react'

function parseTags(raw: string): string[] {
  try { return JSON.parse(raw) } catch { return [] }
}

export default function WatchlistQuickAccess() {
  const router = useRouter()
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getWatchlist()
      .then(data => setItems(data.slice(0, 6)))
      .finally(() => setLoading(false))
  }, [])

  const handleResearch = async (ticker: string) => {
    await markWatchlistViewed(ticker).catch(() => {})
    router.push(`/research?ticker=${ticker}`)
  }

  if (loading) return <p className="text-gray-600 text-sm">Loading…</p>

  if (items.length === 0) {
    return (
      <div className="text-center py-6">
        <Bookmark size={28} className="text-gray-700 mx-auto mb-2" />
        <p className="text-gray-600 text-sm">Your watchlist is empty.</p>
        <a href="/watchlist" className="text-xs text-emerald-400 hover:text-emerald-300 mt-1 inline-block">
          Add tickers →
        </a>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {items.map(item => {
        const tags = parseTags(item.tags).slice(0, 2)
        return (
          <div
            key={item.ticker}
            className="flex items-center justify-between px-3 py-2.5 rounded-xl bg-gray-800/50 hover:bg-gray-800 border border-transparent hover:border-gray-700 transition-all group"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="font-bold text-white text-sm w-14 shrink-0">{item.ticker}</span>
              <div className="flex gap-1 flex-wrap">
                {tags.map(t => (
                  <span key={t} className="px-1.5 py-0.5 rounded-full text-[10px] bg-gray-700 text-gray-400">
                    {t}
                  </span>
                ))}
              </div>
              {item.notes && (
                <span className="text-xs text-gray-500 truncate hidden sm:block">{item.notes}</span>
              )}
            </div>
            <button
              id={`quick-research-${item.ticker}`}
              onClick={() => handleResearch(item.ticker)}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-emerald-400 opacity-0 group-hover:opacity-100 transition-all shrink-0 ml-2"
            >
              <ExternalLink size={12} />
              Research
            </button>
          </div>
        )
      })}
      <a
        href="/watchlist"
        className="block text-center text-xs text-gray-600 hover:text-gray-400 pt-1 transition-colors"
      >
        View full watchlist →
      </a>
    </div>
  )
}
