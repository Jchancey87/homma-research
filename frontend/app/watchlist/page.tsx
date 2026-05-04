'use client'
import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  getWatchlist, addToWatchlist, updateWatchlistItem,
  removeFromWatchlist, WatchlistItem
} from '@/lib/api'
import { Bookmark, Plus, Trash2, Search, Tag, RefreshCw, ExternalLink } from 'lucide-react'

const SENTIMENT_TAGS = ['momentum', 'breakout', 'reversal', 'squeeze', 'catalyst', 'earnings', 'watchonly']

function parseTags(raw: string): string[] {
  try { return JSON.parse(raw) } catch { return [] }
}

function SentimentBadge({ tag }: { tag: string }) {
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-700 text-gray-300">
      {tag}
    </span>
  )
}

function WatchCard({
  item,
  onRemove,
  onResearch,
}: {
  item: WatchlistItem
  onRemove: (ticker: string) => void
  onResearch: (ticker: string) => void
}) {
  const tags = parseTags(item.tags)
  const lastViewed = item.last_viewed_at
    ? new Date(item.last_viewed_at).toLocaleDateString()
    : null
  const added = new Date(item.added_at).toLocaleDateString()

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 flex flex-col gap-3 hover:border-emerald-500/40 transition-colors group">
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xl font-bold text-white tracking-tight">{item.ticker}</span>
          {item.sector && (
            <span className="ml-2 text-xs text-gray-400">{item.sector}</span>
          )}
        </div>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            id={`research-${item.ticker}`}
            onClick={() => onResearch(item.ticker)}
            title="Open Research"
            className="p-1.5 rounded-lg text-gray-400 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
          >
            <ExternalLink size={14} />
          </button>
          <button
            id={`remove-${item.ticker}`}
            onClick={() => onRemove(item.ticker)}
            title="Remove from watchlist"
            className="p-1.5 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {item.notes && (
        <p className="text-sm text-gray-400 leading-relaxed">{item.notes}</p>
      )}

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map(t => <SentimentBadge key={t} tag={t} />)}
        </div>
      )}

      <div className="flex items-center gap-3 text-xs text-gray-600 border-t border-gray-800 pt-2 mt-auto">
        <span>Added {added}</span>
        {lastViewed && <span>· Last viewed {lastViewed}</span>}
      </div>
    </div>
  )
}

export default function WatchlistPage() {
  const router = useRouter()
  const [items, setItems] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [tagFilter, setTagFilter] = useState('')
  const [search, setSearch] = useState('')

  // Add form state
  const [showAdd, setShowAdd] = useState(false)
  const [newTicker, setNewTicker] = useState('')
  const [newNotes, setNewNotes] = useState('')
  const [newSector, setNewSector] = useState('')
  const [newTags, setNewTags] = useState<string[]>([])
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await getWatchlist())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleAdd = async () => {
    const ticker = newTicker.trim().toUpperCase()
    if (!ticker) return setAddError('Ticker is required')
    setAdding(true); setAddError('')
    try {
      await addToWatchlist({ ticker, notes: newNotes || undefined, sector: newSector || undefined, tags: newTags })
      setNewTicker(''); setNewNotes(''); setNewSector(''); setNewTags([])
      setShowAdd(false)
      await load()
    } catch (e: any) {
      setAddError(e?.response?.data?.error || 'Failed to add ticker')
    } finally {
      setAdding(false)
    }
  }

  const handleRemove = async (ticker: string) => {
    if (!confirm(`Remove ${ticker} from watchlist?`)) return
    await removeFromWatchlist(ticker)
    setItems(prev => prev.filter(i => i.ticker !== ticker))
  }

  const handleResearch = (ticker: string) => {
    router.push(`/research?ticker=${ticker}`)
  }

  const toggleTag = (tag: string) => {
    setNewTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag])
  }

  const filtered = items.filter(item => {
    const tags = parseTags(item.tags)
    if (tagFilter && !tags.includes(tagFilter)) return false
    if (search && !item.ticker.includes(search.toUpperCase()) && !item.notes?.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Bookmark className="text-emerald-400" size={22} />
            Watchlist
          </h1>
          <p className="text-gray-400 text-sm mt-1">Tickers of interest — one click to full research</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            id="refresh-watchlist"
            onClick={load}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <RefreshCw size={16} />
          </button>
          <button
            id="add-ticker-btn"
            onClick={() => setShowAdd(v => !v)}
            className="flex items-center gap-1.5 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-black font-semibold text-sm rounded-lg transition-colors"
          >
            <Plus size={15} />
            Add Ticker
          </button>
        </div>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="bg-gray-900 border border-gray-700 rounded-2xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">Add to Watchlist</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              id="new-ticker-input"
              placeholder="Ticker (e.g. AAPL)"
              value={newTicker}
              onChange={e => setNewTicker(e.target.value.toUpperCase())}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-emerald-500"
            />
            <input
              id="new-sector-input"
              placeholder="Sector (optional)"
              value={newSector}
              onChange={e => setNewSector(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-emerald-500"
            />
            <input
              id="new-notes-input"
              placeholder="Notes (optional)"
              value={newNotes}
              onChange={e => setNewNotes(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {SENTIMENT_TAGS.map(tag => (
              <button
                key={tag}
                id={`tag-${tag}`}
                onClick={() => toggleTag(tag)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                  newTags.includes(tag)
                    ? 'bg-emerald-500/30 text-emerald-300 border border-emerald-500/50'
                    : 'bg-gray-800 text-gray-400 border border-gray-700 hover:border-gray-500'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
          {addError && <p className="text-red-400 text-sm">{addError}</p>}
          <div className="flex gap-2">
            <button
              id="confirm-add-btn"
              onClick={handleAdd}
              disabled={adding}
              className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-black font-semibold text-sm rounded-lg transition-colors"
            >
              {adding ? 'Adding…' : 'Add'}
            </button>
            <button
              onClick={() => setShowAdd(false)}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            id="watchlist-search"
            placeholder="Search ticker or notes…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-8 pr-3 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <Tag size={13} className="text-gray-500" />
          {SENTIMENT_TAGS.map(tag => (
            <button
              key={tag}
              id={`filter-tag-${tag}`}
              onClick={() => setTagFilter(prev => prev === tag ? '' : tag)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                tagFilter === tag
                  ? 'bg-emerald-500/30 text-emerald-300 border border-emerald-500/50'
                  : 'bg-gray-800 text-gray-400 border border-gray-700 hover:border-gray-500'
              }`}
            >
              {tag}
            </button>
          ))}
          {tagFilter && (
            <button onClick={() => setTagFilter('')} className="text-xs text-gray-500 hover:text-white ml-1">
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="text-gray-500 text-sm py-12 text-center">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="text-gray-600 text-sm py-16 text-center">
          {items.length === 0
            ? 'Your watchlist is empty. Add a ticker to get started.'
            : 'No tickers match the current filter.'}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(item => (
            <WatchCard
              key={item.ticker}
              item={item}
              onRemove={handleRemove}
              onResearch={handleResearch}
            />
          ))}
        </div>
      )}
    </div>
  )
}
