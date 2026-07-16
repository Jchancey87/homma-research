'use client'
import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  getWatchlist, addToWatchlist, removeFromWatchlist,
  getContinuationPicks, deactivateContinuationPick,
  exportWatchlistCsv, importWatchlistCsv,
  type WatchlistItem, type ContinuationPick,
} from '@/lib/api'
import {
  Bookmark, Plus, Trash2, Search, RefreshCw, ExternalLink,
  Trophy, X, ChevronDown, ChevronUp, Download, Upload,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

const SENTIMENT_TAGS = ['momentum', 'breakout', 'reversal', 'squeeze', 'catalyst', 'earnings', 'watchonly']

const TAG_COLORS: Record<string, string> = {
  momentum:  'bg-blue-950/20 text-blue-400 border-blue-500/25',
  breakout:  'bg-emerald-950/20 text-[#00ff00] border-[#00ff00]/25',
  reversal:  'bg-orange-950/20 text-orange-400 border-orange-500/25',
  squeeze:   'bg-purple-950/20 text-purple-400 border-purple-500/25',
  catalyst:  'bg-yellow-950/20 text-amber-400 border-yellow-500/25',
  earnings:  'bg-pink-950/20 text-pink-400 border-pink-500/25',
  watchonly: 'bg-[#111] text-gray-500 border-[#262626]',
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
  const colorClass = TAG_COLORS[tag] ?? 'bg-[#111] text-gray-500 border-[#262626]'
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 border text-[10px] font-mono rounded-none ${colorClass} uppercase`}>
      {tag}
      {onRemove && (
        <button onClick={onRemove} className="hover:text-[#ff003c] transition-colors ml-0.5">
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
    <span className="flex items-center gap-1 text-[10px] font-mono bg-[#111] border border-[#262626] rounded-none px-2 py-0.5">
      <span className="text-gray-500 uppercase">{label}</span>
      <span className={`font-bold ${color}`}>{value}</span>
    </span>
  )
}

// ── Rank Badge ────────────────────────────────────────────────────────────────

function RankBadge({ rank }: { rank: number }) {
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
    <tr className="group hover:bg-gray-100 dark:hover:bg-gray-800/40 transition-colors border-b border-gray-200 dark:border-gray-800/50 last:border-0">
      {/* Ticker */}
      <td className="px-4 py-3 align-top w-28">
        <span className="text-sm font-bold text-gray-900 dark:text-white tracking-wide font-mono">{item.ticker}</span>
        {item.sector && (
          <p className="text-[10px] text-gray-500 dark:text-gray-600 truncate mt-0.5 uppercase font-medium">{item.sector}</p>
        )}
      </td>

      {/* Notes */}
      <td className="px-4 py-3 align-top min-w-0 max-w-md">
        {item.notes ? (
          <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">{item.notes}</p>
        ) : (
          <p className="text-xs text-gray-400 dark:text-gray-650 italic">No notes</p>
        )}
      </td>

      {/* Tags */}
      <td className="px-4 py-3 align-top hidden md:table-cell">
        <div className="flex flex-wrap gap-1">
          {tags.length > 0
            ? tags.map(t => <TagBadge key={t} tag={t} />)
            : <span className="text-[11px] text-gray-400 dark:text-gray-600">—</span>
          }
        </div>
      </td>

      {/* Meta */}
      <td className="px-4 py-3 align-top hidden lg:table-cell w-32">
        <div className="flex flex-col text-[10px] text-gray-500 dark:text-gray-600">
          <span>Added {added}</span>
          {viewed && <span>Viewed {viewed}</span>}
        </div>
      </td>

      {/* Actions */}
      <td className="px-4 py-3 align-top w-20">
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity justify-end">
          <button
            id={`research-${item.ticker}`}
            onClick={() => onResearch(item.ticker)}
            title="Open Research"
            className="p-1.5 rounded-lg text-gray-500 hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
          >
            <ExternalLink size={14} />
          </button>
          <button
            id={`remove-${item.ticker}`}
            onClick={() => onRemove(item.ticker)}
            title="Remove"
            className="p-1.5 rounded-lg text-gray-500 hover:text-red-650 dark:hover:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </td>
    </tr>
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

  const gapColor = (pick.gap_pct ?? 0) >= 50 ? 'text-emerald-600 dark:text-emerald-400'
    : (pick.gap_pct ?? 0) >= 20 ? 'text-yellow-600 dark:text-yellow-400'
    : 'text-gray-600 dark:text-gray-300'

  const rvolColor = (pick.rvol_15m ?? 0) >= 10 ? 'text-emerald-600 dark:text-emerald-400'
    : (pick.rvol_15m ?? 0) >= 5 ? 'text-yellow-600 dark:text-yellow-400'
    : 'text-gray-600 dark:text-gray-300'

  return (
    <tr className="group hover:bg-yellow-500/5 transition-colors border-b border-gray-200 dark:border-gray-800/50 last:border-0">
      {/* Rank */}
      <td className="px-4 py-3 align-middle w-12 text-center">
        <RankBadge rank={pick.rank} />
      </td>

      {/* Ticker + date */}
      <td className="px-4 py-3 align-middle w-28">
        <span className="text-sm font-bold text-gray-900 dark:text-white tracking-wide font-mono">{pick.ticker}</span>
        <p className="text-[10px] text-gray-500 mt-0.5">{date}</p>
      </td>

      {/* Reason */}
      <td className="px-4 py-3 align-middle min-w-0 max-w-md">
        <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed line-clamp-2">{pick.reason ?? '—'}</p>
      </td>

      {/* Today */}
      <td className="px-4 py-3 align-middle w-24 text-right">
        {pick.today_change_pct != null ? (
          <div className="flex flex-col items-end">
            <span className={`text-xs font-mono font-bold leading-none ${pick.today_change_pct >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
              {pick.today_change_pct >= 0 ? '+' : ''}{pick.today_change_pct.toFixed(1)}%
            </span>
            {pick.today_last != null && (
              <span className="text-[10px] text-gray-500 dark:text-gray-400 font-mono mt-1">
                ${pick.today_last.toFixed(2)}
              </span>
            )}
          </div>
        ) : (
          <span className="text-xs font-mono text-gray-400 dark:text-gray-600">—</span>
        )}
      </td>

      {/* Metrics */}
      <td className="px-4 py-3 align-middle hidden md:table-cell">
        <div className="flex items-center gap-1.5">
          {pick.gap_pct != null && (
            <MetricPill label="Gap" value={`${pick.gap_pct.toFixed(1)}%`} color={gapColor} />
          )}
          {pick.float_shares != null && (
            <MetricPill label="Float" value={fmt(pick.float_shares)} color="text-blue-650 dark:text-blue-300" />
          )}
          {pick.rvol_15m != null && (
            <MetricPill label="RVOL" value={`${pick.rvol_15m.toFixed(1)}x`} color={rvolColor} />
          )}
        </div>
      </td>

      {/* Actions */}
      <td className="px-4 py-3 align-middle w-24">
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity justify-end">
          <button
            onClick={() => onResearch(pick.ticker)}
            title="Run Research"
            className="p-1.5 rounded-lg text-gray-500 hover:text-emerald-600 dark:hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
          >
            <ExternalLink size={14} />
          </button>
          <button
            onClick={() => onDismiss(pick.id)}
            title="Dismiss Pick"
            className="p-1.5 rounded-lg text-gray-500 hover:text-orange-600 dark:hover:text-orange-400 hover:bg-orange-500/10 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      </td>
    </tr>
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
    } catch (e) {
      const err = e as { response?: { data?: { error?: string } } }
      setAddError(err?.response?.data?.error || 'Failed to add ticker')
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

  const handleExport = async () => {
    try {
      const blob = await exportWatchlistCsv()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'watchlist_export.csv'
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Failed to export watchlist', err)
      alert('Failed to export watchlist')
    }
  }

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const res = await importWatchlistCsv(file)
      alert(`Import completed! ${res.inserted} tickers added, ${res.updated} tickers updated.`)
      await load()
    } catch (err) {
      console.error('Failed to import watchlist', err)
      alert('Failed to import watchlist CSV')
    }
    e.target.value = ''
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
            <Trophy className="text-yellow-500" size={20} />
            <div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white leading-tight">AI Continuation Watch</h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">Top picks from the nightly report — auto-populated each evening</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowHistory(v => !v)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                showHistory
                  ? 'bg-gray-250 dark:bg-gray-700 text-gray-900 dark:text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              {showHistory ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {showHistory ? 'Hide dismissed' : 'Show history'}
            </button>
            <button
              onClick={load}
              className="p-1.5 rounded-lg text-gray-500 hover:text-gray-950 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-8 text-gray-500 text-sm animate-pulse">Loading picks…</div>
        ) : activePicks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 bg-gray-50 dark:bg-gray-900/20 border border-dashed border-gray-200 dark:border-gray-800 rounded-2xl gap-3 text-center px-4 transition-all max-w-xl mx-auto mt-6">
            <Trophy size={36} className="text-amber-500 dark:text-amber-600 animate-pulse" />
            <div className="space-y-1">
              <h3 className="font-bold text-gray-900 dark:text-white text-base">No active continuation picks</h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 max-w-xs">
                They populate automatically after the 8:00 PM ET nightly AI analysis runs, or you can perform a manual research search.
              </p>
            </div>
            <div className="flex gap-2 flex-wrap justify-center mt-2">
              <Link
                href="/research"
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold rounded-xl transition-colors shadow-md shadow-emerald-500/10"
              >
                Research Ticker
              </Link>
              <Link
                href="/"
                className="px-4 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 text-xs font-bold rounded-xl transition-colors"
              >
                View Live Screener
              </Link>
            </div>
          </div>
        ) : (
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl overflow-hidden shadow-lg shadow-yellow-500/5">
            <table className="w-full text-left">
              <thead className="border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/80">
                <tr className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-widest font-bold">
                  <th className="px-4 py-3 w-12 text-center">Rank</th>
                  <th className="px-4 py-3 w-28">Ticker</th>
                  <th className="px-4 py-3">Selection Reason</th>
                  <th className="px-4 py-3 w-24 text-right">Today</th>
                  <th className="px-4 py-3 hidden md:table-cell">Key Metrics</th>
                  <th className="px-4 py-3 text-right" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-800/60">
                {activePicks.map(pick => (
                  <PickRow
                    key={pick.id}
                    pick={pick}
                    onDismiss={handleDismissPick}
                    onResearch={handleResearch}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Dismissed history */}
        {showHistory && inactivePicks.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-xs text-gray-600 dark:text-gray-400 uppercase tracking-wide font-semibold pl-1">Dismissed / Expired</p>
            {inactivePicks.map(pick => (
              <div
                key={pick.id}
                className="flex items-center gap-4 px-4 py-2.5 bg-gray-50 dark:bg-gray-900/30 border border-gray-200 dark:border-gray-800/50 rounded-xl opacity-50"
              >
                <span className="w-8 text-center text-xs text-gray-500 dark:text-gray-400">#{pick.rank}</span>
                <span className="w-24 text-sm font-bold text-gray-400 dark:text-gray-500 line-through">{pick.ticker}</span>
                <span className="flex-1 text-xs text-gray-500 dark:text-gray-600 truncate">{pick.reason}</span>
                <span className="text-[10px] text-gray-400 dark:text-gray-600">{pick.deactivated_reason}</span>
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
            <Bookmark className="text-emerald-500 dark:text-emerald-400" size={20} />
            <div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-white leading-tight">My Watchlist</h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">Manually tracked tickers — one click to full research</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              id="refresh-watchlist"
              onClick={load}
              className="p-2 rounded-lg text-gray-500 hover:text-gray-950 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <RefreshCw size={14} />
            </button>
            <button
              id="export-watchlist-btn"
              onClick={handleExport}
              title="Export Watchlist to CSV"
              className="flex items-center gap-1.5 px-3 py-2 border border-gray-300 dark:border-gray-700 hover:bg-gray-150 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 font-semibold text-xs rounded-none transition-colors"
            >
              <Download size={14} />
              Export
            </button>
            <button
              id="import-watchlist-btn"
              onClick={() => document.getElementById('import-csv-input')?.click()}
              title="Import Watchlist from CSV"
              className="flex items-center gap-1.5 px-3 py-2 border border-gray-300 dark:border-gray-700 hover:bg-gray-150 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 font-semibold text-xs rounded-none transition-colors"
            >
              <Upload size={14} />
              Import
            </button>
            <input
              id="import-csv-input"
              type="file"
              accept=".csv"
              onChange={handleImport}
              className="hidden"
            />
            <button
              id="add-ticker-btn"
              onClick={() => setShowAdd(v => !v)}
              className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs rounded-none transition-colors shadow"
            >
              <Plus size={14} />
              Add Ticker
            </button>
          </div>
        </div>

        {/* Add form */}
        {showAdd && (
          <div className="mb-4 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 space-y-4">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">Add to Watchlist</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input
                id="new-ticker-input"
                placeholder="Ticker (e.g. AAPL)"
                value={newTicker}
                onChange={e => setNewTicker(e.target.value.toUpperCase())}
                className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              />
              <input
                id="new-sector-input"
                placeholder="Sector (optional)"
                value={newSector}
                onChange={e => setNewSector(e.target.value)}
                className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              />
              <input
                id="new-notes-input"
                placeholder="Notes (optional)"
                value={newNotes}
                onChange={e => setNewNotes(e.target.value)}
                className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
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
                      ? (TAG_COLORS[tag] ?? 'bg-gray-750 dark:bg-gray-700 text-white dark:text-white border-gray-500')
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-500'
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>
            {addError && <p className="text-red-500 dark:text-red-400 text-sm">{addError}</p>}
            <div className="flex gap-2">
              <button
                id="confirm-add-btn"
                onClick={handleAdd}
                disabled={adding}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-sm rounded-lg transition-colors min-w-[100px]"
              >
                {adding ? (
                  <span className="flex items-center justify-center gap-2">
                    <RefreshCw size={14} className="animate-spin" />
                    Enriching...
                  </span>
                ) : 'Add Ticker'}
              </button>
              <button
                onClick={() => setShowAdd(false)}
                className="px-4 py-2 bg-gray-205 dark:bg-gray-800 hover:bg-gray-300 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 text-sm rounded-lg transition-colors"
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
              className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg pl-8 pr-3 py-2 text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
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
                    ? (TAG_COLORS[tag] ?? 'bg-gray-750 dark:bg-gray-700 text-white dark:text-white border-gray-500')
                    : 'bg-gray-100 dark:bg-gray-800/60 text-gray-650 dark:text-gray-400 border-gray-200 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-500'
                }`}
              >
                {tag}
              </button>
            ))}
            {tagFilter && (
              <button onClick={() => setTagFilter('')} className="text-xs text-gray-500 hover:text-gray-950 dark:hover:text-white ml-1">
                Clear
              </button>
            )}
          </div>
        </div>

        {/* List */}
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl overflow-hidden shadow-sm">
          {loading ? (
            <div className="text-center py-12 text-gray-400 dark:text-gray-650 text-sm animate-pulse">Loading…</div>
          ) : filteredItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3 border-b border-gray-200 dark:border-gray-800 last:border-0">
              <Bookmark size={28} className="text-gray-400 dark:text-gray-600" />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {items.length === 0
                  ? 'Your watchlist is empty. Add a ticker to get started.'
                  : 'No tickers match the current filter.'}
              </p>
            </div>
          ) : (
            <table className="w-full text-left">
              <thead className="border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/80">
                <tr className="text-[10px] text-gray-500 dark:text-gray-450 uppercase tracking-widest font-bold">
                  <th className="px-4 py-3">Ticker</th>
                  <th className="px-4 py-3">Notes</th>
                  <th className="px-4 py-3 hidden md:table-cell">Tags</th>
                  <th className="px-4 py-3 hidden lg:table-cell">Added</th>
                  <th className="px-4 py-3 text-right" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-800/60">
                {filteredItems.map(item => (
                  <WatchlistRow
                    key={item.ticker}
                    item={item}
                    onRemove={handleRemove}
                    onResearch={handleResearch}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  )
}
