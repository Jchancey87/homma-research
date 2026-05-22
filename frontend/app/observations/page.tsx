'use client'
import { useEffect, useState, useCallback } from 'react'
import {
  getObservations, createObservation, deleteObservation,
  Observation
} from '@/lib/api'
import { FileText, Plus, Trash2, Filter, RefreshCw } from 'lucide-react'

type Sentiment = 'bullish' | 'bearish' | 'neutral'

const SENTIMENT_CONFIG: Record<Sentiment, { label: string; color: string; dot: string }> = {
  bullish:  { label: 'Bullish',  color: 'text-emerald-600 dark:text-emerald-400', dot: 'bg-emerald-500' },
  bearish:  { label: 'Bearish',  color: 'text-red-600 dark:text-red-400',     dot: 'bg-red-500'     },
  neutral:  { label: 'Neutral',  color: 'text-gray-500 dark:text-gray-400',    dot: 'bg-gray-400'    },
}

function parseTags(raw: string): string[] {
  try { return JSON.parse(raw) } catch { return [] }
}

function SentimentDot({ sentiment }: { sentiment: Sentiment }) {
  const { dot, color } = SENTIMENT_CONFIG[sentiment]
  return (
    <span className={`flex items-center gap-1.5 text-xs font-medium ${color}`}>
      <span className={`inline-block w-2.5 h-2.5 rounded-full ${dot}`} />
      {SENTIMENT_CONFIG[sentiment].label}
    </span>
  )
}

function ObservationCard({
  obs,
  onDelete,
}: {
  obs: Observation
  onDelete: (id: number) => void
}) {
  const tags = parseTags(obs.tags)
  const [expanded, setExpanded] = useState(false)
  const preview = obs.body.slice(0, 180)
  const isLong = obs.body.length > 180

  return (
    <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 space-y-3 hover:shadow-md hover:border-gray-300 dark:hover:border-gray-700 transition-all group">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-bold text-gray-900 dark:text-white text-sm">{obs.ticker}</span>
          <span className="text-xs text-gray-400 dark:text-gray-500">{obs.date}</span>
          <SentimentDot sentiment={obs.sentiment} />
        </div>
        <button
          id={`delete-obs-${obs.id}`}
          onClick={() => onDelete(obs.id)}
          className="p-1.5 rounded-lg text-gray-400 hover:text-red-500 dark:hover:text-red-450 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
        >
          <Trash2 size={13} />
        </button>
      </div>

      {obs.title && (
        <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">{obs.title}</p>
      )}

      <p className="text-sm text-gray-650 dark:text-gray-400 leading-relaxed whitespace-pre-line">
        {expanded ? obs.body : preview}
        {isLong && !expanded && '…'}
      </p>

      {isLong && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-xs text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 font-semibold"
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map(t => (
            <span key={t} className="px-2.5 py-0.5 rounded-full text-[11px] bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-750">
              {t}
            </span>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-400 dark:text-gray-600">
        {new Date(obs.created_at).toLocaleString()}
      </p>
    </div>
  )
}

export default function ObservationsPage() {
  const [observations, setObservations] = useState<Observation[]>([])
  const [loading, setLoading] = useState(true)

  // Filters
  const [tickerFilter, setTickerFilter] = useState('')
  const [sentimentFilter, setSentimentFilter] = useState<string>('')

  // New observation form
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    ticker: '',
    date: new Date().toISOString().split('T')[0],
    title: '',
    body: '',
    sentiment: 'neutral' as Sentiment,
    tags: '',
  })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (tickerFilter) params.ticker = tickerFilter.toUpperCase()
      if (sentimentFilter) params.sentiment = sentimentFilter
      setObservations(await getObservations(params))
    } finally {
      setLoading(false)
    }
  }, [tickerFilter, sentimentFilter])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    if (!form.ticker.trim()) return setSaveError('Ticker is required')
    if (!form.date.trim())   return setSaveError('Date is required')
    if (!form.body.trim())   return setSaveError('Body is required')
    setSaving(true); setSaveError('')
    try {
      const tags = form.tags.split(',').map(t => t.trim()).filter(Boolean)
      await createObservation({
        ticker: form.ticker.trim().toUpperCase(),
        date: form.date,
        title: form.title || undefined,
        body: form.body,
        sentiment: form.sentiment,
        tags,
      })
      setForm({ ticker: '', date: new Date().toISOString().split('T')[0], title: '', body: '', sentiment: 'neutral', tags: '' })
      setShowForm(false)
      await load()
    } catch (e: any) {
      setSaveError(e?.response?.data?.error || 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this observation?')) return
    await deleteObservation(id)
    setObservations(prev => prev.filter(o => o.id !== id))
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <FileText className="text-emerald-500 dark:text-emerald-400" size={22} />
            Observations
          </h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">Markdown notes per ticker with sentiment tagging</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            id="refresh-observations"
            onClick={load}
            className="p-2 rounded-lg text-gray-500 hover:text-gray-950 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <RefreshCw size={16} />
          </button>
          <button
            id="add-observation-btn"
            onClick={() => setShowForm(v => !v)}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm rounded-lg transition-colors shadow"
          >
            <Plus size={15} />
            Add Observation
          </button>
        </div>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">New Observation</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              id="obs-ticker"
              placeholder="Ticker *"
              value={form.ticker}
              onChange={e => setForm(f => ({ ...f, ticker: e.target.value.toUpperCase() }))}
              className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
            />
            <input
              id="obs-date"
              type="date"
              value={form.date}
              onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
              className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
            />
            <select
              id="obs-sentiment"
              value={form.sentiment}
              onChange={e => setForm(f => ({ ...f, sentiment: e.target.value as Sentiment }))}
              className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
            >
              <option value="bullish">🟢 Bullish</option>
              <option value="bearish">🔴 Bearish</option>
              <option value="neutral">⚪ Neutral</option>
            </select>
          </div>
          <input
            id="obs-title"
            placeholder="Title (optional)"
            value={form.title}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
          />
          <textarea
            id="obs-body"
            placeholder="Write your observation… (markdown supported)"
            value={form.body}
            onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
            rows={5}
            className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 resize-y font-mono"
          />
          <input
            id="obs-tags"
            placeholder="Tags (comma-separated, e.g. gap, low-float)"
            value={form.tags}
            onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
            className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
          />
          {saveError && <p className="text-red-500 dark:text-red-400 text-sm">{saveError}</p>}
          <div className="flex gap-2">
            <button
              id="save-observation-btn"
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-sm rounded-lg transition-colors"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-4 py-2 bg-gray-200 dark:bg-gray-800 hover:bg-gray-300 dark:hover:bg-gray-700 text-gray-750 dark:text-gray-300 text-sm rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <Filter size={14} className="text-gray-500" />
        <input
          id="filter-ticker"
          placeholder="Filter by ticker…"
          value={tickerFilter}
          onChange={e => setTickerFilter(e.target.value)}
          className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-1.5 text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 w-40"
        />
        {(['bullish', 'bearish', 'neutral'] as Sentiment[]).map(s => (
          <button
            key={s}
            id={`filter-${s}`}
            onClick={() => setSentimentFilter(prev => prev === s ? '' : s)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              sentimentFilter === s
                ? 'bg-gray-250 dark:bg-gray-700 text-gray-905 dark:text-white border-gray-300 dark:border-gray-500'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-500'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${SENTIMENT_CONFIG[s].dot}`} />
            {SENTIMENT_CONFIG[s].label}
          </button>
        ))}
        {(tickerFilter || sentimentFilter) && (
          <button
            onClick={() => { setTickerFilter(''); setSentimentFilter('') }}
            className="text-xs text-gray-500 hover:text-gray-950 dark:hover:text-white ml-1 font-semibold"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Feed */}
      {loading ? (
        <div className="text-gray-500 text-sm py-12 text-center">Loading…</div>
      ) : observations.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 bg-gray-50 dark:bg-gray-900/20 border border-dashed border-gray-200 dark:border-gray-800 rounded-2xl gap-3 text-center px-4 transition-all max-w-xl mx-auto mt-6">
          <FileText size={36} className="text-emerald-500 dark:text-emerald-400 animate-pulse" />
          <div className="space-y-1">
            <h3 className="font-bold text-gray-900 dark:text-white text-base">No observations found</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 max-w-xs">
              {tickerFilter || sentimentFilter
                ? 'Try adjusting your filters to find specific logs, or write a new one.'
                : 'Keep track of your trade patterns, catalyst analysis, or checklist notes by writing observations.'}
            </p>
          </div>
          <button
            onClick={() => setShowForm(true)}
            className="mt-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl transition-colors shadow-md shadow-emerald-500/10 flex items-center gap-1.5"
          >
            <Plus size={14} />
            Write First Observation
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {observations.map(obs => (
            <ObservationCard key={obs.id} obs={obs} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}
