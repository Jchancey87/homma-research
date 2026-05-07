'use client'
import { useState, useEffect, useRef } from 'react'
import { Loader2, AlertCircle, RefreshCw, Clock, Download, type LucideIcon } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { getJobStatus } from '@/lib/api'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface FeatureState {
  jobId:   string | null
  loading: boolean
  report:  string | null
  error:   string | null
  status:  string | null
}

export const EMPTY_FEATURE: FeatureState = {
  jobId: null, loading: false, report: null, error: null, status: null,
}

interface FeaturePanelProps {
  title:       string
  description: string
  Icon:        LucideIcon
  accentColor: 'orange' | 'emerald' | 'blue' | 'violet'
  state:       FeatureState
  onTrigger:   () => void
  ticker:      string | null
  // Cache metadata
  cachedAt?:   string | null   // ISO timestamp of cache hit
  version?:    number | null
  expiresAt?:  string | null   // ISO timestamp for stale warning
  exportUrl?:  string | null   // download URL
}

// ── Accent colour maps ─────────────────────────────────────────────────────────

const COLORS = {
  orange: {
    icon:   'text-orange-400',
    border: 'border-orange-500/20',
    bg:     'bg-orange-500/5',
    spin:   'text-orange-400',
    status: 'text-orange-300',
    btn:    'bg-orange-600 hover:bg-orange-500',
    tag:    'text-orange-400',
  },
  emerald: {
    icon:   'text-emerald-400',
    border: 'border-emerald-500/20',
    bg:     'bg-emerald-500/5',
    spin:   'text-emerald-400',
    status: 'text-emerald-300',
    btn:    'bg-emerald-600 hover:bg-emerald-500',
    tag:    'text-emerald-400',
  },
  blue: {
    icon:   'text-blue-400',
    border: 'border-blue-500/20',
    bg:     'bg-blue-500/5',
    spin:   'text-blue-400',
    status: 'text-blue-300',
    btn:    'bg-blue-600 hover:bg-blue-500',
    tag:    'text-blue-400',
  },
  violet: {
    icon:   'text-violet-400',
    border: 'border-violet-500/20',
    bg:     'bg-violet-500/5',
    spin:   'text-violet-400',
    status: 'text-violet-300',
    btn:    'bg-violet-600 hover:bg-violet-500',
    tag:    'text-violet-400',
  },
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function FeaturePanel({
  title, description, Icon, accentColor, state, onTrigger, ticker,
  cachedAt, version, expiresAt, exportUrl,
}: FeaturePanelProps) {
  const c = COLORS[accentColor]

  // Stale warning: if expiresAt exists and we're >50% through TTL from cachedAt
  const isStale = (() => {
    if (!expiresAt || !cachedAt) return false
    const created = new Date(cachedAt).getTime()
    const expires = new Date(expiresAt).getTime()
    const now     = Date.now()
    const pct     = (now - created) / (expires - created)
    return pct > 0.5
  })()

  const cacheAge = (() => {
    if (!cachedAt) return null
    const ms  = Date.now() - new Date(cachedAt).getTime()
    const hrs = Math.floor(ms / 3_600_000)
    const min = Math.floor((ms % 3_600_000) / 60_000)
    return hrs > 0 ? `${hrs}h ago` : `${min}m ago`
  })()

  // Poll for job completion
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!state.jobId || !state.loading) {
      if (intervalRef.current) clearInterval(intervalRef.current)
      return
    }
    intervalRef.current = setInterval(async () => {
      try {
        const job = await getJobStatus(state.jobId!)
        if (job.status === 'done' || job.status === 'error') {
          if (intervalRef.current) clearInterval(intervalRef.current)
        }
      } catch { /* parent handles via its own polling */ }
    }, 2000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [state.jobId, state.loading])

  return (
    <div className={`rounded-2xl border ${state.loading ? `${c.border} ${c.bg}` : 'border-gray-800 bg-gray-900/60'} overflow-hidden transition-all duration-500`}>
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800/60">
        <div className="flex items-center gap-3">
          <Icon className={c.icon} size={20} />
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-white text-sm tracking-wide">{title}</h3>
              {/* Cache version badge */}
              {version != null && (
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">
                  v{version}
                </span>
              )}
            </div>
            {!state.report && !state.loading && (
              <p className="text-xs text-gray-500 mt-0.5">{description}</p>
            )}
            {/* Cache age */}
            {state.report && cacheAge && (
              <div className="flex items-center gap-1 mt-0.5">
                <Clock size={10} className={isStale ? 'text-amber-400' : 'text-gray-600'} />
                <span className={`text-[10px] ${isStale ? 'text-amber-400' : 'text-gray-600'}`}>
                  From cache · {cacheAge}{isStale ? ' · may be stale' : ''}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {/* Download button — only shown when report is ready and exportUrl provided */}
          {state.report && exportUrl && (
            <a
              href={exportUrl}
              download
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 transition-all"
              title="Download report as Markdown"
            >
              <Download size={12} />
            </a>
          )}
          {/* Run / Re-run button */}
          {ticker && (
            <button
              onClick={onTrigger}
              disabled={state.loading}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed ${state.report ? 'bg-gray-700 hover:bg-gray-600' : c.btn}`}
              title={state.report ? `Force re-run ${title}` : `Run ${title}`}
            >
              {state.loading
                ? <Loader2 size={13} className="animate-spin" />
                : state.report
                  ? <><RefreshCw size={12} /> RE-RUN</>
                  : 'RUN'
              }
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-6">
        {/* Loading */}
        {state.loading && (
          <div className="flex flex-col items-center justify-center py-8 gap-4 animate-pulse">
            <Loader2 className={`${c.spin} animate-spin`} size={28} />
            <p className={`text-sm font-medium ${c.status}`}>{state.status || 'Analyzing…'}</p>
          </div>
        )}

        {/* Error */}
        {!state.loading && state.error && (
          <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/20 rounded-xl p-4">
            <AlertCircle className="text-red-400 shrink-0 mt-0.5" size={18} />
            <div>
              <p className="text-sm font-bold text-red-400">Analysis Failed</p>
              <p className="text-xs text-gray-400 mt-0.5">{state.error}</p>
            </div>
          </div>
        )}

        {/* Report */}
        {!state.loading && state.report && (
          <div className={`prose prose-invert prose-sm max-w-none
            prose-headings:text-white prose-h2:text-base prose-h3:text-sm
            prose-strong:${c.tag} prose-table:text-xs
            prose-th:text-gray-400 prose-td:text-gray-300
            prose-code:${c.tag} prose-pre:bg-black/40 prose-pre:text-xs`}>
            <ReactMarkdown>{state.report}</ReactMarkdown>
          </div>
        )}

        {/* Idle — no ticker entered yet */}
        {!state.loading && !state.report && !state.error && !ticker && (
          <p className="text-xs text-gray-600 text-center py-6">
            Enter a ticker above to run this analysis.
          </p>
        )}

        {/* Idle — ticker entered, not yet run */}
        {!state.loading && !state.report && !state.error && ticker && (
          <p className="text-xs text-gray-600 text-center py-6">
            Click <span className={`font-bold ${c.tag}`}>RUN</span> or hit <span className="font-bold text-white">ANALYZE</span> to generate this report.
          </p>
        )}
      </div>
    </div>
  )
}
