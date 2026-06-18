'use client'
import { useEffect, useState, useCallback } from 'react'
import {
  getObservations, createObservation, deleteObservation,
  Observation
} from '@/lib/api'
import { FileText, Plus, Trash2, Filter, RefreshCw } from 'lucide-react'

type Sentiment = 'bullish' | 'bearish' | 'neutral'

const SENTIMENT_CONFIG: Record<Sentiment, { label: string; color: string; dot: string }> = {
  bullish:  { label: 'Bullish',  color: 'text-[#00ff00]', dot: 'bg-[#00ff00]' },
  bearish:  { label: 'Bearish',  color: 'text-[#ff003c]', dot: 'bg-[#ff003c]'  },
  neutral:  { label: 'Neutral',  color: 'text-gray-400',  dot: 'bg-gray-600'   },
}

function parseTags(raw: string): string[] {
  try { return JSON.parse(raw) } catch { return [] }
}

function SentimentDot({ sentiment }: { sentiment: Sentiment }) {
  const { dot, color } = SENTIMENT_CONFIG[sentiment]
  return (
    <span className={`flex items-center gap-1.5 font-mono text-[11px] font-medium ${color}`}>
      <span className={`inline-block w-2 h-2 rounded-none ${dot}`} />
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
    <div className="bg-[#050505] border border-[#262626] p-3 space-y-2 hover:border-[#444] transition-colors group">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-white text-xs">{obs.ticker}</span>
          <span className="font-mono text-[10px] text-gray-500">{obs.date}</span>
          <SentimentDot sentiment={obs.sentiment} />
        </div>
        <button
          id={`delete-obs-${obs.id}`}
          onClick={() => onDelete(obs.id)}
          className="p-1 border border-transparent text-gray-600 hover:text-[#ff003c] hover:border-[#ff003c]/30 rounded-none opacity-0 group-hover:opacity-100 transition-all"
        >
          <Trash2 size={13} />
        </button>
      </div>

      {obs.title && (
        <p className="font-mono text-xs font-bold text-gray-300">{obs.title}</p>
      )}

      <p className="font-mono text-xs text-gray-400 leading-relaxed whitespace-pre-line">
        {expanded ? obs.body : preview}
        {isLong && !expanded && '…'}
      </p>

      {isLong && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="font-mono text-[11px] text-[#00ff00] hover:text-white"
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map(t => (
            <span key={t} className="font-mono text-[10px] px-1.5 py-0.5 border border-[#262626] bg-[#111] text-gray-400 rounded-none">
              {t}
            </span>
          ))}
        </div>
      )}

      <p className="font-mono text-[10px] text-gray-600">
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
    } catch (e) {
      const err = e as { response?: { data?: { error?: string } } }
      setSaveError(err?.response?.data?.error || 'Failed to save')
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
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-[#050505] border border-[#262626]">
        <div>
          <h1 className="font-mono text-sm font-bold text-white uppercase flex items-center gap-1.5">
            <FileText className="text-[#00f0ff]" size={14} />
            Observations
          </h1>
          <p className="font-mono text-[10px] text-gray-500 mt-0.5">Markdown notes per ticker with sentiment tagging</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            id="refresh-observations"
            onClick={load}
            className="border border-[#262626] bg-black text-gray-400 hover:text-white transition-colors rounded-none p-1.5"
          >
            <RefreshCw size={13} />
          </button>
          <button
            id="add-observation-btn"
            onClick={() => setShowForm(v => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00] font-mono text-[11px] rounded-none transition-colors"
          >
            <Plus size={13} />
            Add Observation
          </button>
        </div>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="bg-[#050505] border border-[#262626] p-3 space-y-2">
          <h2 className="font-mono text-[11px] font-bold text-gray-400 uppercase tracking-widest">New Observation</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              id="obs-ticker"
              placeholder="Ticker *"
              value={form.ticker}
              onChange={e => setForm(f => ({ ...f, ticker: e.target.value.toUpperCase() }))}
              className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none placeholder-gray-600 [color-scheme:dark]"
            />
            <input
              id="obs-date"
              type="date"
              value={form.date}
              onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
              className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark]"
            />
            <select
              id="obs-sentiment"
              value={form.sentiment}
              onChange={e => setForm(f => ({ ...f, sentiment: e.target.value as Sentiment }))}
              className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark]"
            >
              <option value="bullish">Bullish</option>
              <option value="bearish">Bearish</option>
              <option value="neutral">Neutral</option>
            </select>
          </div>
          <input
            id="obs-title"
            placeholder="Title (optional)"
            value={form.title}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            className="w-full bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none placeholder-gray-600 [color-scheme:dark]"
          />
          <textarea
            id="obs-body"
            placeholder="Write your observation… (markdown supported)"
            value={form.body}
            onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
            rows={5}
            className="w-full bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none placeholder-gray-600 resize-y [color-scheme:dark]"
          />
          <input
            id="obs-tags"
            placeholder="Tags (comma-separated, e.g. gap, low-float)"
            value={form.tags}
            onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
            className="w-full bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none placeholder-gray-600 [color-scheme:dark]"
          />
          {saveError && <p className="font-mono text-[11px] text-[#ff003c]">{saveError}</p>}
          <div className="flex gap-2">
            <button
              id="save-observation-btn"
              onClick={handleSave}
              disabled={saving}
              className="px-3 py-1.5 border border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00] font-mono text-[11px] rounded-none disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-3 py-1.5 border border-[#262626] bg-black text-gray-400 hover:text-white font-mono text-[11px] rounded-none transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-1.5 p-2 bg-[#0a0a0a] border border-[#262626]">
        <Filter size={12} className="text-gray-500" />
        <input
          id="filter-ticker"
          placeholder="Filter by ticker…"
          value={tickerFilter}
          onChange={e => setTickerFilter(e.target.value)}
          className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none placeholder-gray-600 [color-scheme:dark] w-36"
        />
        {(['bullish', 'bearish', 'neutral'] as Sentiment[]).map(s => (
          <button
            key={s}
            id={`filter-${s}`}
            onClick={() => setSentimentFilter(prev => prev === s ? '' : s)}
            className={`flex items-center gap-1.5 px-2 py-1 font-mono text-[11px] border rounded-none transition-colors ${
              sentimentFilter === s
                ? 'border-[#262626] bg-[#0a0a0a] text-white'
                : 'border-[#262626] bg-black text-gray-400 hover:text-white'
            }`}
          >
            <span className={`w-2 h-2 rounded-none ${SENTIMENT_CONFIG[s].dot}`} />
            {SENTIMENT_CONFIG[s].label}
          </button>
        ))}
        {(tickerFilter || sentimentFilter) && (
          <button
            onClick={() => { setTickerFilter(''); setSentimentFilter('') }}
            className="font-mono text-[11px] text-gray-500 hover:text-white transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Feed */}
      {loading ? (
        <div className="animate-pulse bg-[#111] h-8" />
      ) : observations.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2 border border-[#262626] bg-[#050505]">
          <FileText size={28} className="text-gray-700" />
          <p className="text-gray-500 text-xs uppercase tracking-wider font-mono">
            {tickerFilter || sentimentFilter ? 'No observations match filters' : 'No observations yet'}
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00] font-mono text-[11px] rounded-none transition-colors mt-2"
          >
            <Plus size={13} />
            Write First Observation
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
          {observations.map(obs => (
            <ObservationCard key={obs.id} obs={obs} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}
