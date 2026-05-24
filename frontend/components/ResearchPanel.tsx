'use client'
import { useState, useEffect, useCallback } from 'react'
import { Loader2, Zap, Clock, ChevronRight, RefreshCw, ChevronDown, Clipboard, Check } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { startResearch, startSentiment, getJob, listJobs, LLMJob } from '@/lib/api'
import InteractiveSessionChart from './InteractiveSessionChart'

interface Props {
  defaultDate?: string
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function statusBadge(status: LLMJob['status']) {
  const map = {
    pending: 'bg-yellow-500/20 text-yellow-300',
    running: 'bg-sky-500/20 text-sky-300',
    done:    'bg-emerald-500/20 text-emerald-300',
    error:   'bg-red-500/20 text-red-400',
  }
  return map[status] ?? 'bg-gray-700 text-gray-400'
}

function fmtDate(iso: string) {
  try { return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: '2-digit' }) }
  catch { return iso }
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function ResearchPanel({ defaultDate }: Props) {
  const [mode, setMode]         = useState<'research' | 'sentiment'>('research')
  const [ticker, setTicker]     = useState('')
  const [date, setDate]         = useState(defaultDate || new Date().toLocaleDateString('en-CA')) // YYYY-MM-DD
  const [query, setQuery]       = useState('')
  const [activeJob, setActiveJob] = useState<LLMJob | null>(null)
  const [history, setHistory]   = useState<LLMJob[]>([])
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [copied, setCopied]       = useState(false)

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const jobs = await listJobs(undefined, 30)
      setHistory(jobs)
    } catch { /* silent */ }
    finally { setHistoryLoading(false) }
  }, [])

  useEffect(() => { loadHistory() }, [loadHistory])

  const poll = async (jobId: string) => {
    for (let i = 0; i < 80; i++) {
      await new Promise(r => setTimeout(r, 3000))
      const j = await getJob(jobId)
      setActiveJob(j)
      if (j.status === 'done' || j.status === 'error') {
        loadHistory()
        return
      }
    }
  }

  const handleRun = async () => {
    if (mode === 'research' && !ticker.trim()) { setError('Enter a ticker symbol.'); return }
    if (mode === 'sentiment' && !query.trim()) { setError('Enter a research question.'); return }
    setLoading(true); setError(null); setActiveJob(null)
    try {
      const res = mode === 'research'
        ? await startResearch(ticker.toUpperCase(), date)
        : await startSentiment(query)

      // Cache-hit: render immediately, no job polling needed
      if ('cached' in res && res.cached) {
        setActiveJob({ id: 'cache', status: 'done', output: res.report, type: mode } as LLMJob)
        return
      }

      if ('job_id' in res) {
        setActiveJob({ id: res.job_id, status: 'pending', type: mode } as LLMJob)
        await poll(res.job_id)
      }
    } catch (e) {
      const err = e as { response?: { data?: { error?: string } } }
      setError(err?.response?.data?.error ?? 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const viewHistoric = (job: LLMJob) => {
    setActiveJob(job)
    setShowHistory(false)
  }

  const copyToClipboard = () => {
    if (activeJob?.output) {
      navigator.clipboard.writeText(activeJob.output)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  // Extract chart props and clean output for interactive chart
  let chartProps = null
  let displayOutput = activeJob?.output ?? ''
  
  if (activeJob?.type === 'research' && activeJob.status === 'done' && displayOutput) {
    // Match full URL: http://127.0.0.1:5000/storage/charts/research/TICKER_Session_DATE_jobid.png
    const match = displayOutput.match(/\/charts\/research\/([A-Za-z0-9.]+)_Session_(\d{4}-\d{2}-\d{2})_/)
    if (match) {
      chartProps = { ticker: match[1], date: match[2] }
      // Remove all chart images from the markdown
      displayOutput = displayOutput.replace(/!\[.*?\]\(.*?\/charts\/research\/.*?\)\n*/g, '')
      // remove the generic header and first HR
      displayOutput = displayOutput.replace(/### Technical Charts\n*/g, '')
      displayOutput = displayOutput.replace(/---\n*/, '') // remove first HR
    }
  }

  // ─── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-5xl mx-auto space-y-6">

      {/* ── Top Bar: Mode + History Dropdown ─────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-gray-900/50 p-4 rounded-xl border border-gray-800">
        <div className="flex gap-2">
          {(['research', 'sentiment'] as const).map(m => (
            <button key={m} onClick={() => { setMode(m); setActiveJob(null); setError(null) }}
              className={`px-4 py-2 rounded-lg text-xs font-semibold transition-all duration-200
                ${mode === m
                  ? 'bg-sky-500 text-white shadow-lg shadow-sky-500/20'
                  : 'text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700'}`}>
              {m === 'research' ? '🔬 Ticker Research' : '🔍 Strategy Query'}
            </button>
          ))}
        </div>

        <div className="relative">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="w-full md:w-auto flex items-center justify-between gap-3 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-xs font-medium text-gray-300 hover:bg-gray-700 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Clock size={14} className="text-sky-400" />
              <span>Report History</span>
            </div>
            <ChevronDown size={14} className={`transition-transform duration-200 ${showHistory ? 'rotate-180' : ''}`} />
          </button>

          {showHistory && (
            <div className="absolute right-0 mt-2 w-72 md:w-80 bg-gray-900 border border-gray-800 rounded-xl shadow-2xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm">
                <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Recent Reports</span>
                <button onClick={loadHistory} disabled={historyLoading} className="text-gray-500 hover:text-sky-400 transition-colors">
                  <RefreshCw size={12} className={historyLoading ? 'animate-spin' : ''} />
                </button>
              </div>
              <div className="max-h-80 overflow-y-auto divide-y divide-gray-800/50">
                {history.length === 0 ? (
                  <div className="px-4 py-8 text-center">
                    <p className="text-xs text-gray-600">No reports found</p>
                  </div>
                ) : history.map(job => (
                  <button key={job.id} onClick={() => viewHistoric(job)}
                    className={`w-full text-left px-4 py-3 hover:bg-sky-500/5 transition-colors flex items-center gap-3
                      ${activeJob?.id === job.id ? 'bg-sky-500/10 border-l-2 border-sky-500' : 'border-l-2 border-transparent'}`}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-bold uppercase ${statusBadge(job.status)}`}>
                          {job.status}
                        </span>
                        <span className="text-[10px] text-gray-500 font-medium">{job.type}</span>
                      </div>
                      <p className="text-xs text-gray-200 truncate font-mono font-medium">
                        {job.input_ref ?? job.id.slice(0, 8)}
                      </p>
                      <p className="text-[10px] text-gray-500 mt-1">{fmtDate(job.created_at)}</p>
                    </div>
                    <ChevronRight size={12} className="text-gray-700" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Main Content Area ────────────────────────────────────────── */}
      <div className="space-y-6">

        {/* Input Section */}
        <div className="bg-gray-900/30 p-6 rounded-2xl border border-gray-800/50 backdrop-blur-sm">
          {mode === 'research' ? (
            <div className="max-w-2xl">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
                <div>
                  <label className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 block">Ticker Symbol</label>
                  <input type="text" value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())}
                    placeholder="NVDA, TSLA, AAPL..."
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-500 transition-all font-mono" />
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 block">Session Date (Optional)</label>
                  <input type="date" value={date} onChange={e => setDate(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-500 transition-all font-mono [color-scheme:dark]" />
                </div>
              </div>
              <button onClick={handleRun} disabled={loading}
                className="w-full bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-bold px-6 py-3 rounded-xl transition-all hover:scale-[1.01] active:scale-[0.99] text-sm flex items-center justify-center gap-2 shadow-lg shadow-sky-600/20">
                {loading ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                Run Research
              </button>
              <p className="text-[11px] text-gray-500 mt-3 flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-sky-500"></span>
                Deep fundamental analysis and high-resolution intraday charting (Polygon.io).
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <label className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 block">Research Question</label>
              <textarea value={query} onChange={e => setQuery(e.target.value)} rows={3}
                placeholder="e.g. Compare my top 3 setups by average cleanliness score..."
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-500 transition-all resize-none" />
              <button onClick={handleRun} disabled={loading}
                className="w-full bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-bold py-3 rounded-xl transition-all hover:scale-[1.01] active:scale-[0.99] text-sm flex items-center justify-center gap-2 shadow-lg shadow-sky-600/20">
                {loading ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                {loading ? 'Processing Query...' : 'Analyze Journal via Groq'}
              </button>
            </div>
          )}
          {error && <p className="text-red-400 text-xs mt-3 bg-red-400/10 p-2 rounded-lg border border-red-400/20">{error}</p>}
        </div>

        {/* Output Section */}
        {activeJob && (
          <div className={`rounded-2xl border transition-all duration-500 shadow-2xl
            ${activeJob.status === 'done'   ? 'border-sky-500/30 bg-gray-900/80 shadow-sky-500/5' : ''}
            ${activeJob.status === 'error'  ? 'border-red-500/30 bg-gray-900/80' : ''}
            ${activeJob.status === 'running' || activeJob.status === 'pending'
              ? 'border-gray-800 bg-gray-900/40 animate-pulse' : ''}`}>

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800/50">
              <div className="flex items-center gap-3">
                <span className={`text-[10px] font-black px-2 py-0.5 rounded uppercase tracking-tighter ${statusBadge(activeJob.status)}`}>
                  {activeJob.status}
                </span>
                <div className="h-4 w-[1px] bg-gray-800"></div>
                <span className="text-xs text-gray-400 font-mono font-medium">{activeJob.input_ref || activeJob.type}</span>
              </div>
              <div className="flex items-center gap-3">
                {activeJob.status === 'done' && (
                  <button onClick={copyToClipboard} className="text-gray-500 hover:text-white p-1.5 hover:bg-gray-800 rounded-lg transition-all" title="Copy to clipboard">
                    {copied ? <Check size={16} className="text-emerald-400" /> : <Clipboard size={16} />}
                  </button>
                )}
                {activeJob.model_used && (
                  <span className="text-[10px] text-gray-600 font-mono bg-gray-950 px-2 py-1 rounded border border-gray-800">{activeJob.model_used}</span>
                )}
              </div>
            </div>

            {/* Body */}
            <div className="p-6 md:p-8">
              {(activeJob.status === 'pending' || activeJob.status === 'running') && (
                <div className="flex flex-col items-center justify-center py-20 gap-4 text-sky-400">
                  <Loader2 size={32} className="animate-spin opacity-50" />
                  <span className="text-sm font-medium tracking-wide animate-pulse">
                    {activeJob.status === 'pending' ? 'QUEUEING JOB...' : 'GROQ IS ANALYZING...'}
                  </span>
                </div>
              )}

              {activeJob.status === 'done' && activeJob.output && (
                <div className="space-y-10">
                  {chartProps && (
                    <div className="w-full">
                      <InteractiveSessionChart ticker={chartProps.ticker} date={chartProps.date} />
                    </div>
                  )}
                  <div className="prose prose-invert prose-sky max-w-none
                    prose-headings:font-bold prose-headings:tracking-tight prose-headings:text-white
                    prose-h1:text-3xl prose-h1:mb-8 prose-h1:pb-4 prose-h1:border-b prose-h1:border-sky-500/20
                    prose-h2:text-xl prose-h2:mt-10 prose-h2:mb-4 prose-h2:text-sky-300
                    prose-p:text-gray-300 prose-p:leading-relaxed prose-p:mb-6
                    prose-strong:text-white prose-strong:font-bold
                    prose-ul:my-6 prose-li:my-2 prose-li:text-gray-300
                    prose-table:border prose-table:border-gray-800 prose-table:rounded-xl prose-table:overflow-hidden
                    prose-thead:bg-gray-800/50 prose-th:px-4 prose-th:py-3 prose-th:text-sky-200 prose-th:text-[11px] prose-th:uppercase prose-th:tracking-widest
                    prose-td:px-4 prose-td:py-3 prose-td:text-xs prose-td:border-t prose-td:border-gray-800
                    prose-blockquote:border-l-4 prose-blockquote:border-sky-500 prose-blockquote:bg-sky-500/5 prose-blockquote:py-2 prose-blockquote:px-6 prose-blockquote:rounded-r-lg prose-blockquote:italic prose-blockquote:text-sky-100
                    prose-img:rounded-2xl prose-img:shadow-2xl">
                    <ReactMarkdown>{displayOutput}</ReactMarkdown>
                  </div>
                </div>
              )}

              {activeJob.status === 'error' && (
                <div className="flex flex-col items-center justify-center py-12 gap-4 text-red-400">
                  <div className="p-3 bg-red-400/10 rounded-full border border-red-400/20">
                    <RefreshCw size={24} />
                  </div>
                  <p className="text-sm font-medium">{activeJob.output ?? 'Critical error during generation'}</p>
                  <button onClick={handleRun} className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-4 py-2 rounded-lg transition-colors border border-gray-700">
                    Retry Request
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

    </div>
  )
}
