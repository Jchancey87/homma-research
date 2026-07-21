'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getWatchlist, getWatchlistPrices, WatchlistItem, WatchlistPrice, markWatchlistViewed } from '@/lib/api'
import { ExternalLink, Bookmark, Flame } from 'lucide-react'
import { useAlertStream } from './live-gainers/useAlertStream'
import { useRef } from 'react'

function parseTags(raw: string): string[] {
  try { return JSON.parse(raw) } catch { return [] }
}

function pct(v: number | null) {
  if (v == null) return null
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

function pctColor(v: number | null) {
  if (v == null) return 'text-gray-600'
  return v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-gray-500'
}

interface WatchlistQuickAccessProps {
  initialItems?: WatchlistItem[]
  initialPrices?: Record<string, WatchlistPrice>
}

export default function WatchlistQuickAccess({ initialItems = [], initialPrices = {} }: WatchlistQuickAccessProps) {
  const router = useRouter()
  const [items,  setItems]  = useState<WatchlistItem[]>(initialItems)
  const [prices, setPrices] = useState<Record<string, WatchlistPrice>>(initialPrices)
  const [loading, setLoading] = useState(initialItems.length === 0)
  
  const { wsConnected, prices: wsPrices } = useAlertStream()
  const wsConnectedRef = useRef(wsConnected)
  useEffect(() => { wsConnectedRef.current = wsConnected }, [wsConnected])

  useEffect(() => {
    if (initialItems.length === 0) {
      Promise.all([
        getWatchlist().then(d => d.slice(0, 8)),
        getWatchlistPrices().catch(() => ({} as Record<string, WatchlistPrice>)),
      ]).then(([newItems, newPrices]) => {
        setItems(newItems)
        setPrices(newPrices)
      }).finally(() => setLoading(false))
    }

    let intervalId: ReturnType<typeof setInterval> | null = null

    const startPolling = () => {
      if (intervalId) clearInterval(intervalId)
      intervalId = setInterval(() => {
        if (document.visibilityState === 'visible' && !wsConnectedRef.current) {
          getWatchlistPrices()
            .then(p => setPrices(p))
            .catch(() => {})
        }
      }, 3000)
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        getWatchlistPrices()
          .then(p => setPrices(p))
          .catch(() => {})
        startPolling()
      } else {
        if (intervalId) {
          clearInterval(intervalId)
          intervalId = null
        }
      }
    }

    if (document.visibilityState === 'visible') {
      startPolling()
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      if (intervalId) clearInterval(intervalId)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [initialItems.length])

  const handleResearch = async (ticker: string) => {
    await markWatchlistViewed(ticker).catch(() => {})
    router.push(`/research?ticker=${ticker}`)
  }

  if (loading) return (
    <div className="space-y-1.5 animate-pulse">
      {[1,2,3].map(i => <div key={i} className="h-9 bg-gray-800/60 rounded-lg" />)}
    </div>
  )

  if (items.length === 0) return (
    <div className="flex flex-col items-center justify-center py-6 gap-2">
      <Bookmark size={22} className="text-gray-700" />
      <p className="text-gray-600 text-xs">Watchlist is empty</p>
      <a href="/watchlist" className="text-xs text-emerald-400 hover:text-emerald-300">Add tickers →</a>
    </div>
  )

  return (
    <div className="space-y-0.5">
      {/* Header row */}
      <div className="flex items-center text-[10px] text-gray-700 uppercase tracking-wide font-semibold px-3 pb-1">
        <span className="flex-1">Ticker</span>
        <span className="w-16 text-right">Price</span>
        <span className="w-14 text-right">Chg</span>
        <span className="w-6" />
      </div>

      {items.map(item => {
        const tags  = parseTags(item.tags).slice(0, 2)
        const price = wsPrices[item.ticker] ? { ...prices[item.ticker], price: wsPrices[item.ticker].price } : prices[item.ticker]
        const isMoving = price?.chg_pct != null && Math.abs(price.chg_pct) >= 5

        return (
          <div
            key={item.ticker}
            className={`group flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-gray-800/50 border border-transparent transition-all cursor-pointer ${isMoving ? 'border-emerald-500/15 bg-emerald-500/5' : ''}`}
            onClick={() => handleResearch(item.ticker)}
          >
            {/* Ticker */}
            <div className="flex items-center gap-1.5 flex-1 min-w-0">
              {isMoving && <Flame size={11} className="text-orange-400 shrink-0" />}
              <span className="text-sm font-bold text-white font-mono">{item.ticker}</span>
              <div className="flex gap-1 ml-1 hidden sm:flex">
                {tags.map(t => (
                  <span key={t} className="px-1.5 py-0.5 rounded text-[10px] bg-gray-800 text-gray-500">{t}</span>
                ))}
              </div>
            </div>

            {/* Price */}
            <span className="text-xs font-mono text-gray-300 w-16 text-right">
              {price?.price != null ? `$${price.price.toFixed(2)}` : '—'}
            </span>

            {/* % Change */}
            <span className={`text-xs font-mono font-semibold w-14 text-right ${pctColor(price?.chg_pct ?? null)}`}>
              {pct(price?.chg_pct ?? null) ?? '—'}
            </span>

            {/* Research link */}
            <button
              id={`quick-research-${item.ticker}`}
              onClick={e => { e.stopPropagation(); handleResearch(item.ticker) }}
              className="w-6 flex items-center justify-center text-gray-700 hover:text-emerald-400 opacity-0 group-hover:opacity-100 transition-all"
            >
              <ExternalLink size={11} />
            </button>
          </div>
        )
      })}

      <a
        href="/watchlist"
        className="block text-center text-[10px] text-gray-700 hover:text-gray-500 pt-2 transition-colors"
      >
        View full watchlist →
      </a>
    </div>
  )
}
