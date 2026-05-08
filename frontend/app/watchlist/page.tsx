'use client'
import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  getWatchlist, addToWatchlist, removeFromWatchlist,
  getContinuationPicks, deactivateContinuationPick, addContinuationPick,
  type WatchlistItem, type ContinuationPick,
} from '@/lib/api'
import {
  Bookmark, Plus, Trash2, Search, RefreshCw, ExternalLink,
  TrendingUp, Trophy, X, ChevronDown, ChevronUp, Zap,
  BarChart2, AlertTriangle, CheckCircle2, Circle,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

const SENTIMENT_TAGS = ['momentum', 'breakout', 'reversal', 'squeeze', 'catalyst', 'earnings', 'watchonly']

const TAG_COLORS: Record<string, string> = {
  momentum:  'bg-blue-500/20 text-blue-300 border-blue-500/30',
  breakout:  'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  reversal:  'bg-orange-500/20 text-orange-300 border-orange-500/30',
  squeeze:   'bg-violet-500/20 text-violet-300 border-violet-500/30',
  catalyst:  'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  earnings:  'bg-pink-500/20 text-pink-300 border-pink-500/30',
  watchonly: 'bg-gray-500/20 text-gray-400 border-gray-600/30',
}

function parseTags(raw: string): string[] {
  try { return JSON.parse(raw) } catch { return [] }
}

function fmt(n: number | null | undefined, suffix = '', decimals = 1): string {
  if (n == null) return '—'
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(1)}M${suffix}`
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K${suffix}`
  return `${n.toFixed(decimals)}${suffix}`
}

// ── Tag Badge ─────────────────────────────────────────────────────────────────

function TagBadge({ tag, onRemove }: { tag: string; onRemove?: () => void }) {
  const colorClass = TAG_COLORS[tag] ?? 'bg-gray-700/50 text-gray-400 border-gray-600/30'
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${colorClass}`}>
      {tag}
      {onRemove && (
        <button onClick={onRemove} className="hover:text-white transition-colors ml-0.5">
          <X size={10} />
        </button>
      )}
    </span>
  )
}

// ── Metric Pill ───────────────────────────────────────────────────────────────

function MetricPill({ label, value, color = 'text-gray-300' }: {
  label: string; value: string; color?: string
}) {
  return (
    <span className="flex items-center gap-1 text-[11px] bg-gray-800/60 rounded-md px-2 py-0.5 border border-gray-700/50">
      <span className="text-gray-500 font-medium">{label}</span>
      <span className={`font-bold ${color}`}>{value}</span>
    </span>
  )
}

// ── Rank Badge ────────────────────────────────────────────────────────────────

function RankBadge({ rank }: { rank: number }) {
  const colors = ['text-yellow-400', 'text-gray-300', 'text-amber-600']
  const labels = ['🥇', '🥈', '🥉']
  return (
    <span className="text-base" title={`Rank #${rank}`}>
      {labels[rank - 1] ?? `#${rank}`}
    </span>
  )
}

// ── Watchlist Row ─────────────────────────────────────────────────────────────

function WatchlistRow({
  item, onRemove, onResearch,
}: {
  item: WatchlistItem
  onRemove: (ticker: string) => void
  onResearch: (ticker: string) => void
}) {
  const tags    = parseTags(item.tags)
  const added   = new Date(item.added_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  const viewed  = item.last_viewed_at
    ? new Date(item.last_viewed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : null

  return (
    <div className="group flex items-center gap-4 px-4 py-3 bg-gray-900/60 border border-gray-800 rounded-xl hover:border-gray-700 hover:bg-gray-900 transition-all">
      {/* Ticker */}
      <div className="w-20 shrink-0">
        <span className="text-base font-bold text-white tracking-wide">{item.ticker}</span>
        {item.sector && (
          <p className="text-[10px] text-gray-500 truncate mt-0.5">{item.sector}</p>
        )}
      </div>

      {/* Notes */}
      <div className="flex-1 min-w-0">
        {item.notes ? (
          <p className="text-xs text-gray-400 truncate">{item.notes}</p>
        ) : (
          <p className="text-xs text-gray-600 italic">No notes</p>
        )}
      </div>

      {/* Tags */}
      <div className="hidden md:flex items-center gap-1.5 flex-wrap">
        {tags.length > 0
          ? tags.map(t => <TagBadge key={t} tag={t} />)
          : <span className="text-[11px] text-gray-600">—</span>
        }
      </div>

      {/* Meta */}
      <div className="hidden lg:flex flex-col items-end text-[10px] text-gray-600 shrink-0">
        <span>Added {added}</span>
        {viewed && <span>Viewed {viewed}</span>}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button
          id={`research-${item.ticker}`}
          onClick={() => onResearch(item.ticker)}
          title="Open Research"
          className="p-1.5 rounded-lg text-gray-500 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
        >
          <ExternalLink size={14} />
        </button>
        <button
          id={`remove-${item.ticker}`}
          onClick={() => onRemove(item.ticker)}
          title="Remove"
          className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  )
}

// ── Continuation Pick Row ─────────────────────────────────────────────────────

function PickRow({
  pick, onDismiss, onResearch,
}: {
  pick: ContinuationPick
  onDismiss: (id: number) => void
  onResearch: (ticker: string) => void
}) {
  const date = new Date(pick.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

  const gapColor = (pick.gap_pct ?? 0) >= 50 ? 'text-emerald-400'
    : (pick.gap_pct ?? 0) >= 20 ? 'text-yellow-400'
    : 'text-gray-300'

  const rvolColor = (pick.rvol_15m ?? 0) >= 10 ? 'text-emerald-400'
    : (pick.rvol_15m ?? 0) >= 5 ? 'text-yellow-400'
    : 'text-gray-300'

  return (
    <div className="group flex items-center gap-4 px-4 py-3 bg-gradient-to-r from-yellow-500/5 to-transparent border border-yellow-500/20 rounded-xl hover:border-yellow-500/40 hover:from-yellow-500/10 transition-all">
      {/* Rank */}
      <div className="shrink-0 w-8 text-center">
        <RankBadge rank={pick.rank} />
      </div>

      {/* Ticker + date */}
      <div className="w-24 shrink-0">
        <span className="text-base font-bold text-white tracking-wide">{pick.ticker}</span>
        <p className="text-[10px] text-gray-500 mt-0.5">{date}</p>
      </div>

      {/* Reason */}
      <div className="flex-1 min-w-0">
        <p className="text-xs text-gray-400 leading-relaxed line-clamp-2">{pick.reason ?? '—'}</p>
      </div>

      {/* Metrics */}
      <div className="hidden md:flex items-center gap-1.5 shrink-0">
        {pick.gap_pct != null && (
          <MetricPill label="Gap" value={`${pick.gap_pct.toFixed(1)}%`} color={gapColor} />
        )}
        {pick.float_shares != null && (
          <MetricPill label="Float" value={fmt(pick.float_shares)} color="text-blue-300" />
        )}
        {pick.rvol_15m != null && (
          <MetricPill label="RVOL" value={`${pick.rvol_15m.toFixed(1)}x`} color={rvolColor} />
        )}
        {pick.sector && (
          <MetricPill label="" value={pick.sector} />
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button
          onClick={() => onResearch(pick.ticker)}
          title="Run Research"
          className="p-1.5 rounded-lg text-gray-500 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
        >
          <ExternalLink size={14} />
        </button>
        <button
          onClick={() => onDismiss(pick.id)}
          title="Dismiss Pick"
          className="p-1.5 rounded-lg text-gray-500 hover:text-orange-400 hover:bg-orange-500/10 transition-colors"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function WatchlistPage() {
  const router = useRouter()

  const [items,   setItems]   = useState<WatchlistItem[]>([])
  const [picks,   setPicks]   = useState<ContinuationPick[]>([])
  const [loading, setLoading] = useState(true)
  const [search,  setSearch]  = useState('')
  const [tagFilter, setTagFilter] = useState('')
  const [showHistory, setShowHistory] = useState(false)

  // Add form
  const [showAdd,   setShowAdd]   = useState(false)
  const [newTicker, setNewTicker] = useState('')
  const [newNotes,  setNewNotes]  = useState('')
  const [newSector, setNewSector] = useState('')
  const [newTags,   setNewTags]   = useState<string[]>([])
  const [adding,    setAdding]    = useState(false)
  const [addError,  setAddError]  = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [w, p] = await Promise.all([
        getWatchlist(),
        getContinuationPicks(showHistory),
      ])
      setItems(w)
      setPicks(p)
    } finally {
      setLoading(false)
    }
  }, [showHistory])

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

  const handleDismissPick = async (id: number) => {
    await deactivateContinuationPick(id, 'manually dismissed')
    setPicks(prev => prev.filter(p => p.id !== id))
  }

  const handleResearch = (ticker: string) => {
    router.push(`/research?ticker=${ticker}`)
  }

  const toggleTag = (tag: string) => {
    setNewTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag])
  }

  const filteredItems = items.filter(item => {
    const tags = parseTags(item.tags)
    if (tagFilter && !tags.includes(tagFilter)) return false
    if (search && !item.ticker.includes(search.toUpperCase()) && !item.notes?.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const activePicks  = picks.filter(p => p.is_active)
  const inactivePicks = picks.filter(p => !p.is_active)

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-20">

      {/* ── AI Continuation Watch ─────────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Trophy className="text-yellow-400" size={20} />
            <div>
              <h2 className="text-lg font-bold text-white leading-tight">AI Continuation Watch</h2>
              <p className="text-xs text-gray-500">Top picks from the nightly report — auto-populated each evening</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowHistory(v => !v)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                showHistory ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              {showHistory ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {showHistory ? 'Hide dismissed' : 'Show history'}
            </button>
            <button
              onClick={load}
              className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-8 text-gray-600 text-sm animate-pulse">Loading picks…</div>
        ) : activePicks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 bg-gray-900/40 border border-dashed border-gray-800 rounded-xl gap-3">
            <Trophy size={28} className="text-gray-700" />
            <p className="text-sm text-gray-500">No active continuation picks yet.</p>
            <p className="text-xs text-gray-600">They populate automatically after the 8 PM nightly report runs.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {activePicks.map(pick => (
              <PickRow
                key={pick.id}
                pick={pick}
                onDismiss={handleDismissPick}
                onResearch={handleResearch}
              />
            ))}
          </div>
        )}

        {/* Dismissed history */}
        {showHistory && inactivePicks.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-xs text-gray-600 uppercase tracking-wide font-semibold pl-1">Dismissed / Expired</p>
            {inactivePicks.map(pick => (
              <div
                key={pick.id}
                className="flex items-center gap-4 px-4 py-2.5 bg-gray-900/30 border border-gray-800/50 rounded-xl opacity-50"
              >
                <span className="w-8 text-center text-xs text-gray-600">#{pick.rank}</span>
                <span className="w-24 text-sm font-bold text-gray-500 line-through">{pick.ticker}</span>
                <span className="flex-1 text-xs text-gray-600 truncate">{pick.reason}</span>
                <span className="text-[10px] text-gray-700">{pick.deactivated_reason}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── My Watchlist ─────────────────────────────────────────────── */}
      <section>
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Bookmark className="text-emerald-400" size={20} />
            <div>
              <h2 className="text-lg font-bold text-white leading-tight">My Watchlist</h2>
              <p className="text-xs text-gray-500">Manually tracked tickers — one click to full research</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              id="refresh-watchlist"
              onClick={load}
              className="p-2 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
            >
              <RefreshCw size={14} />
            </button>
            <button
              id="add-ticker-btn"
              onClick={() => setShowAdd(v => !v)}
              className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm rounded-lg transition-colors shadow"
            >
              <Plus size={14} />
              Add Ticker
            </button>
          </div>
        </div>

        {/* Add form */}
        {showAdd && (
          <div className="mb-4 bg-gray-900 border border-gray-700 rounded-xl p-4 space-y-4">
            <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">Add to Watchlist</h3>
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
                  className={`px-2.5 py-1 rounded-full text-xs font-semibold border transition-colors ${
                    newTags.includes(tag)
                      ? (TAG_COLORS[tag] ?? 'bg-gray-700 text-white border-gray-500')
                      : 'bg-gray-800 text-gray-500 border-gray-700 hover:border-gray-500'
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
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-sm rounded-lg transition-colors"
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
        <div className="flex items-center gap-3 mb-3">
          <div className="relative flex-1 max-w-xs">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              id="watchlist-search"
              placeholder="Search ticker or notes…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-8 pr-3 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {SENTIMENT_TAGS.map(tag => (
              <button
                key={tag}
                id={`filter-tag-${tag}`}
                onClick={() => setTagFilter(prev => prev === tag ? '' : tag)}
                className={`px-2.5 py-1 rounded-full text-xs font-semibold border transition-colors ${
                  tagFilter === tag
                    ? (TAG_COLORS[tag] ?? 'bg-gray-700 text-white border-gray-500')
                    : 'bg-gray-800/60 text-gray-500 border-gray-700 hover:border-gray-500'
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

        {/* Column header */}
        {filteredItems.length > 0 && (
          <div className="grid grid-cols-[80px_1fr_auto_auto_auto] gap-4 px-4 mb-1 text-[10px] text-gray-600 uppercase tracking-wide font-semibold">
            <span>Ticker</span>
            <span>Notes</span>
            <span className="hidden md:block">Tags</span>
            <span className="hidden lg:block">Added</span>
            <span />
          </div>
        )}

        {/* List */}
        {loading ? (
          <div className="text-center py-8 text-gray-600 text-sm animate-pulse">Loading…</div>
        ) : filteredItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 bg-gray-900/40 border border-dashed border-gray-800 rounded-xl gap-3">
            <Bookmark size={28} className="text-gray-700" />
            <p className="text-sm text-gray-500">
              {items.length === 0
                ? 'Your watchlist is empty. Add a ticker to get started.'
                : 'No tickers match the current filter.'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredItems.map(item => (
              <WatchlistRow
                key={item.ticker}
                item={item}
                onRemove={handleRemove}
                onResearch={handleResearch}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
