'use client'
import { useState, useEffect, useCallback } from 'react'
import {
  Search, Loader2, AlertCircle, FileText,
  TrendingUp, ShieldAlert, BarChart3, CalendarDays, Landmark, History, Download,
  type LucideIcon,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import {
  startResearch, startRiskDetection, startCatalystAnalysis, startDeepContext,
  startPipeAnalysis, getJobStatus,
  getResearchHistory, getCachedReport, getResearchExportUrl,
  type CachedReport,
} from '@/lib/api'
import FeaturePanel, {
  type FeatureState, EMPTY_FEATURE,
} from '@/components/research/FeaturePanel'

// ── Types ─────────────────────────────────────────────────────────────────────

type Tab = 'report' | 'risk' | 'catalyst' | 'context' | 'pipe' | 'history'

interface MainState {
  jobId:   string | null
  loading: boolean
  report:  string | null
  error:   string | null
  status:  string | null
  model:   string | null
}

// Per-feature cache metadata
interface CacheMeta {
  cachedAt:  string | null
  version:   number | null
  expiresAt: string | null
  cacheId:   number | null
}
const EMPTY_META: CacheMeta = { cachedAt: null, version: null, expiresAt: null, cacheId: null }




// ── Helpers ───────────────────────────────────────────────────────────────────

const EMPTY_MAIN: MainState = {
  jobId: null, loading: false, report: null, error: null, status: null, model: null,
}



// ── Feature polling hook ───────────────────────────────────────────────────────

function useFeatureJob(
  jobId: string | null,
  onDone:  (output: string, model: string | null)  => void,
  onError: (msg: string)     => void,
) {
  useEffect(() => {
    if (!jobId) return
    const iv = setInterval(async () => {
      try {
        const job = await getJobStatus(jobId)
        if (job.status === 'done')  { clearInterval(iv); onDone(job.output ?? '', job.model_used ?? null) }
        if (job.status === 'error') { clearInterval(iv); onError(job.output ?? 'Error') }
      } catch { /* keep polling */ }
    }, 2500)
    return () => clearInterval(iv)
  }, [jobId]) // eslint-disable-line react-hooks/exhaustive-deps
}

// ── Tab config ────────────────────────────────────────────────────────────────

const TABS: { id: Tab; label: string; icon: LucideIcon }[] = [
  { id: 'report',   label: 'Full Report', icon: FileText },
  { id: 'risk',     label: 'Risk',        icon: ShieldAlert },
  { id: 'catalyst', label: 'Catalyst',    icon: TrendingUp },
  { id: 'context',  label: 'Context',     icon: BarChart3 },
  { id: 'pipe',     label: 'PIPE',        icon: Landmark },
  { id: 'history',  label: 'History',     icon: History },
]

const TAB_ACCENT: Record<Tab, string> = {
  report:   'text-emerald-400 border-emerald-500',
  risk:     'text-orange-400 border-orange-500',
  catalyst: 'text-emerald-400 border-emerald-500',
  context:  'text-blue-400 border-blue-500',
  pipe:     'text-violet-400 border-violet-500',
  history:  'text-gray-400 border-gray-500',
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ResearchPage() {
  const [ticker, setTicker] = useState('')
  const [date, setDate]     = useState('')
  const [activeTab, setActiveTab] = useState<Tab>('report')

  // Main report state
  const [main, setMain] = useState<MainState>(EMPTY_MAIN)

  // Feature states
  const [risk,     setRisk]     = useState<FeatureState>(EMPTY_FEATURE)
  const [catalyst, setCatalyst] = useState<FeatureState>(EMPTY_FEATURE)
  const [context,  setContext]  = useState<FeatureState>(EMPTY_FEATURE)
  const [pipe,     setPipe]     = useState<FeatureState>(EMPTY_FEATURE)

  // Cache metadata per feature
  const [riskMeta,     setRiskMeta]     = useState<CacheMeta>(EMPTY_META)
  const [catalystMeta, setCatalystMeta] = useState<CacheMeta>(EMPTY_META)
  const [contextMeta,  setContextMeta]  = useState<CacheMeta>(EMPTY_META)

  // History tab
  const [historyItems, setHistoryItems]   = useState<CachedReport[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [expandedReport, setExpandedReport] = useState<CachedReport | null>(null)

  // ── Polling hooks ──────────────────────────────────────────────────────────

  useFeatureJob(
    main.jobId,
    (output, model) => setMain(s => ({ ...s, loading: false, report: output, model, jobId: null })),
    (msg)    => setMain(s => ({ ...s, loading: false, error: msg,    jobId: null })),
  )
  useFeatureJob(
    risk.jobId,
    (output) => setRisk(s => ({ ...s, loading: false, report: output, jobId: null })),
    (msg)    => setRisk(s => ({ ...s, loading: false, error: msg,    jobId: null })),
  )
  useFeatureJob(
    catalyst.jobId,
    (output) => setCatalyst(s => ({ ...s, loading: false, report: output, jobId: null })),
    (msg)    => setCatalyst(s => ({ ...s, loading: false, error: msg,    jobId: null })),
  )
  useFeatureJob(
    context.jobId,
    (output) => setContext(s => ({ ...s, loading: false, report: output, jobId: null })),
    (msg)    => setContext(s => ({ ...s, loading: false, error: msg,    jobId: null })),
  )
  useFeatureJob(
    pipe.jobId,
    (output) => setPipe(s => ({ ...s, loading: false, report: output, jobId: null })),
    (msg)    => setPipe(s => ({ ...s, loading: false, error: msg,    jobId: null })),
  )

  // ── Trigger individual features ────────────────────────────────────────────

  // Helper: apply a cache-hit or job response to a feature setter
  const applyFeatureRes = (
    res: Awaited<ReturnType<typeof startRiskDetection>>,
    setState: typeof setRisk,
    setMeta: typeof setRiskMeta,
    errMsg: string,
  ) => {
    if ('cached' in res && res.cached) {
      setState({ ...EMPTY_FEATURE, loading: false, report: res.report })
      setMeta({ cachedAt: res.created_at, version: res.version, expiresAt: null, cacheId: null })
    } else if ('job_id' in res) {
      setState(s => ({ ...s, jobId: res.job_id }))
    } else {
      setState({ ...EMPTY_FEATURE, error: errMsg })
    }
  }

  const runRisk = useCallback(async (force = false) => {
    if (!ticker) return
    setRisk({ ...EMPTY_FEATURE, loading: true, status: 'Scanning SEC filings & corporate actions…' })
    setRiskMeta(EMPTY_META)
    try {
      const res = await startRiskDetection(ticker, force)
      applyFeatureRes(res, setRisk, setRiskMeta, 'Failed to start risk analysis')
    } catch (e) {
      const err = e as { response?: { data?: { error?: string } } }
      setRisk({ ...EMPTY_FEATURE, error: err.response?.data?.error ?? 'Failed to start risk analysis' })
    }
  }, [ticker])

  const runCatalyst = useCallback(async (force = false) => {
    if (!ticker) return
    setCatalyst({ ...EMPTY_FEATURE, loading: true, status: 'Parsing news & regulatory events…' })
    setCatalystMeta(EMPTY_META)
    try {
      const res = await startCatalystAnalysis(ticker, date || undefined, force)
      applyFeatureRes(res, setCatalyst, setCatalystMeta, 'Failed to start catalyst analysis')
    } catch (e) {
      const err = e as { response?: { data?: { error?: string } } }
      setCatalyst({ ...EMPTY_FEATURE, error: err.response?.data?.error ?? 'Failed to start catalyst analysis' })
    }
  }, [ticker, date])

  const runContext = useCallback(async (force = false) => {
    if (!ticker) return
    setContext({ ...EMPTY_FEATURE, loading: true, status: 'Building multi-timeframe technical picture…' })
    setContextMeta(EMPTY_META)
    try {
      const res = await startDeepContext(ticker, force)
      applyFeatureRes(res, setContext, setContextMeta, 'Failed to start deep context')
    } catch (e) {
      const err = e as { response?: { data?: { error?: string } } }
      setContext({ ...EMPTY_FEATURE, error: err.response?.data?.error ?? 'Failed to start deep context' })
    }
  }, [ticker])

  const runPipe = useCallback(async () => {
    if (!ticker) return
    setPipe({ ...EMPTY_FEATURE, loading: true, status: 'Scanning SEC 8-K filings for PIPE signals…' })
    try {
      const res = await startPipeAnalysis(ticker, date || undefined)
      if ('job_id' in res) setPipe(s => ({ ...s, jobId: res.job_id }))
    } catch (e) {
      const err = e as { response?: { data?: { error?: string } } }
      setPipe({ ...EMPTY_FEATURE, error: err.response?.data?.error ?? 'Failed to start PIPE analysis' })
    }
  }, [ticker, date])

  // ── History tab loader ────────────────────────────────────────────────────
  const loadHistory = useCallback(async () => {
    if (!ticker) return
    setHistoryLoading(true)
    try {
      const items = await getResearchHistory(ticker)
      setHistoryItems(items)
    } catch { /* silent */ } finally {
      setHistoryLoading(false)
    }
  }, [ticker])

  useEffect(() => {
    if (activeTab === 'history' && ticker) loadHistory()
  }, [activeTab, ticker, loadHistory])

  // ── Main search — fires all 4 jobs in parallel ─────────────────────────────

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    const sym = ticker.trim().toUpperCase()
    if (!sym) return

    setMain({ ...EMPTY_MAIN, loading: true, status: 'Gathering market data…' })
    setRisk({ ...EMPTY_FEATURE, loading: true, status: 'Scanning SEC filings & corporate actions…' })
    setCatalyst({ ...EMPTY_FEATURE, loading: true, status: 'Parsing news & regulatory events…' })
    setContext({ ...EMPTY_FEATURE, loading: true, status: 'Building multi-timeframe technical picture…' })
    setPipe({ ...EMPTY_FEATURE, loading: true, status: 'Scanning SEC 8-K filings for PIPE signals…' })
    setRiskMeta(EMPTY_META); setCatalystMeta(EMPTY_META); setContextMeta(EMPTY_META)
    setActiveTab('report')

    try {
      const [mainRes, riskRes, catRes, ctxRes, pipeRes] = await Promise.allSettled([
        startResearch(sym, date || undefined),
        startRiskDetection(sym),
        startCatalystAnalysis(sym, date || undefined),
        startDeepContext(sym),
        startPipeAnalysis(sym, date || undefined),
      ])

      // Main report — no cache path yet (deep research)
      if (mainRes.status === 'fulfilled') {
        const r = mainRes.value
        if ('cached' in r && r.cached) setMain({ ...EMPTY_MAIN, loading: false, report: r.report })
        else if ('job_id' in r) setMain(s => ({ ...s, jobId: r.job_id, status: 'AI Analyst is investigating…' }))
      } else setMain({ ...EMPTY_MAIN, error: 'Failed to start main report' })

      if (riskRes.status === 'fulfilled')    applyFeatureRes(riskRes.value, setRisk, setRiskMeta, 'Failed to start risk detection')
      else setRisk({ ...EMPTY_FEATURE, error: 'Failed to start risk detection' })

      if (catRes.status === 'fulfilled')     applyFeatureRes(catRes.value, setCatalyst, setCatalystMeta, 'Failed to start catalyst analysis')
      else setCatalyst({ ...EMPTY_FEATURE, error: 'Failed to start catalyst analysis' })

      if (ctxRes.status === 'fulfilled')     applyFeatureRes(ctxRes.value, setContext, setContextMeta, 'Failed to start deep context')
      else setContext({ ...EMPTY_FEATURE, error: 'Failed to start deep context' })

      if (pipeRes.status === 'fulfilled' && 'job_id' in pipeRes.value)
        setPipe(s => ({ ...s, jobId: pipeRes.value.job_id }))
      else setPipe({ ...EMPTY_FEATURE, error: 'Failed to start PIPE analysis' })

    } catch {
      setMain({ ...EMPTY_MAIN, error: 'Unexpected error starting research' })
      setRisk({ ...EMPTY_FEATURE, error: 'Unexpected error' })
      setCatalyst({ ...EMPTY_FEATURE, error: 'Unexpected error' })
      setContext({ ...EMPTY_FEATURE, error: 'Unexpected error' })
      setPipe({ ...EMPTY_FEATURE, error: 'Unexpected error' })
    }
  }

  const anyActive = main.loading || risk.loading || catalyst.loading || context.loading || pipe.loading
  const anyReport = main.report || risk.report || catalyst.report || context.report || pipe.report

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-20">

      {/* Header */}
      <div className="text-center space-y-2 pt-2">
        <h1 className="text-3xl font-bold text-white tracking-tight">Deep Ticker Research</h1>
        <p className="text-gray-400">
          Enter a symbol for a comprehensive fundamental, technical, and risk analysis.
        </p>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="space-y-4">
        {/* Ticker - Now Full Width */}
        <div className="relative group">
          <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none text-gray-500 group-focus-within:text-emerald-500 transition-colors">
            <Search size={24} />
          </div>
          <input
            id="research-ticker-input"
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="TICKER (e.g. NVDA, TSLA, GME)"
            className="w-full bg-gray-900 border-2 border-gray-800 rounded-2xl py-5 pl-14 pr-4 text-2xl font-bold tracking-widest text-white focus:outline-none focus:border-emerald-500 transition-all shadow-xl placeholder:text-gray-700"
            disabled={anyActive}
          />
        </div>

        <div className="flex flex-col sm:flex-row gap-3 items-center justify-center">
          {/* Optional date picker */}
          <div className="relative group w-full sm:w-auto">
            <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-gray-600 group-focus-within:text-blue-400 transition-colors">
              <CalendarDays size={16} />
            </div>
            <input
              id="research-date-input"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="bg-gray-900 border-2 border-gray-800 rounded-2xl py-3 pl-10 pr-4 text-sm text-gray-400 focus:outline-none focus:border-blue-500 transition-all shadow-xl w-full sm:w-48"
              disabled={anyActive}
              title="Optional: anchor analysis to a specific trading date"
            />
          </div>

          {/* Analyze button */}
          <button
            id="research-analyze-btn"
            type="submit"
            disabled={anyActive || !ticker}
            className="w-full sm:w-auto px-12 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-800 disabled:text-gray-500 text-white font-bold rounded-2xl transition-all flex items-center justify-center gap-2 shadow-xl"
          >
            {anyActive
              ? <Loader2 className="animate-spin" size={18} />
              : 'ANALYZE'}
          </button>
        </div>

        {date && (
          <p className="text-xs text-gray-600 text-center">
            Catalyst analysis anchored to <span className="text-blue-400 font-mono">{date}</span>
          </p>
        )}
      </form>

      {/* Tabs — only show after at least one report has been started */}
      {anyReport || anyActive ? (
        <>
          {/* Tab bar */}
          <div className="flex gap-1 bg-gray-900/80 border border-gray-800 rounded-2xl p-1">
            {TABS.map(({ id, label, icon: Icon }) => {
              const isActive = activeTab === id
              const isLoading =
                id === 'report'   ? main.loading     :
                id === 'risk'     ? risk.loading      :
                id === 'catalyst' ? catalyst.loading  :
                id === 'context'  ? context.loading   :
                                    pipe.loading
              const hasReport =
                id === 'report'   ? !!main.report     :
                id === 'risk'     ? !!risk.report      :
                id === 'catalyst' ? !!catalyst.report  :
                id === 'context'  ? !!context.report   :
                                    !!pipe.report

              return (
                <button
                  key={id}
                  id={`research-tab-${id}`}
                  onClick={() => setActiveTab(id)}
                  className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-sm font-semibold transition-all ${
                    isActive
                      ? 'bg-gray-800 text-white'
                      : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {isLoading
                    ? <Loader2 size={14} className="animate-spin text-gray-400" />
                    : <Icon size={14} className={isActive ? TAB_ACCENT[id].split(' ')[0] : ''} />
                  }
                  <span className="hidden sm:inline">{label}</span>
                  {hasReport && !isLoading && (
                    <span className={`w-1.5 h-1.5 rounded-full ${TAB_ACCENT[id].split(' ')[0].replace('text-', 'bg-')}`} />
                  )}
                </button>
              )
            })}
          </div>

          {/* Tab panels */}
          <div>
            {/* Full Report tab */}
            {activeTab === 'report' && (
              <div>
                {main.loading && (
                  <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-2xl p-8 text-center space-y-4 animate-pulse">
                    <Loader2 className="mx-auto text-emerald-500 animate-spin" size={32} />
                    <p className="text-lg font-medium text-emerald-400">{main.status}</p>
                    <p className="text-sm text-gray-500">Checking SEC filings, short interest, and technical levels…</p>
                  </div>
                )}
                {main.error && !main.loading && (
                  <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-6 flex items-start gap-4">
                    <AlertCircle className="text-red-500 shrink-0" size={24} />
                    <div>
                      <p className="font-bold text-red-400">Research Error</p>
                      <p className="text-sm text-gray-400">{main.error}</p>
                    </div>
                  </div>
                )}
                {main.report && !main.loading && (
                  <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden shadow-2xl">
                    <div className="bg-gray-800/50 px-6 py-4 border-b border-gray-700 flex items-center justify-between">
                      <div className="flex items-center gap-2 text-emerald-400 font-bold tracking-tight">
                        <FileText size={18} />
                        ANALYSIS REPORT: {ticker}
                      </div>
                      <div className="text-xs text-gray-500 font-mono uppercase tracking-widest">
                        Generated by {main.model || 'AI Analyst'}
                      </div>
                    </div>
                    <div className="p-8 prose prose-invert prose-emerald max-w-none prose-headings:text-white prose-strong:text-emerald-400 prose-code:text-emerald-300 prose-pre:bg-black/50">
                      <ReactMarkdown>{main.report}</ReactMarkdown>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Risk Detection tab */}
            {activeTab === 'risk' && (
              <FeaturePanel
                title="Risk Detection"
                description="Identifies reverse-splits, toxic financing, shelf registrations, and short interest traps."
                Icon={ShieldAlert}
                accentColor="orange"
                state={risk}
                onTrigger={() => runRisk(true)}
                ticker={ticker || null}
                cachedAt={riskMeta.cachedAt}
                version={riskMeta.version}
                expiresAt={riskMeta.expiresAt}
                exportUrl={riskMeta.cacheId ? getResearchExportUrl(riskMeta.cacheId) : null}
              />
            )}

            {/* Catalyst Analysis tab */}
            {activeTab === 'catalyst' && (
              <FeaturePanel
                title="Catalyst Analysis"
                description="Scans recent SEC 8-K filings and news to verify the quality and durability of the move."
                Icon={TrendingUp}
                accentColor="emerald"
                state={catalyst}
                onTrigger={() => runCatalyst(true)}
                ticker={ticker || null}
                cachedAt={catalystMeta.cachedAt}
                version={catalystMeta.version}
                expiresAt={catalystMeta.expiresAt}
                exportUrl={catalystMeta.cacheId ? getResearchExportUrl(catalystMeta.cacheId) : null}
              />
            )}

            {/* Deep Context tab */}
            {activeTab === 'context' && (
              <FeaturePanel
                title="Deep Context"
                description="Combines SMA levels, RS vs SPY, options sentiment, and your journal history for a setup score."
                Icon={BarChart3}
                accentColor="blue"
                state={context}
                onTrigger={() => runContext(true)}
                ticker={ticker || null}
                cachedAt={contextMeta.cachedAt}
                version={contextMeta.version}
                expiresAt={contextMeta.expiresAt}
                exportUrl={contextMeta.cacheId ? getResearchExportUrl(contextMeta.cacheId) : null}
              />
            )}

            {/* PIPE Detection tab */}
            {activeTab === 'pipe' && (
              <FeaturePanel
                title="PIPE Detection"
                description="Scans SEC 8-K filings (Items 1.01 & 3.02) for private placement signals and classifies the deal as favorable or toxic."
                Icon={Landmark}
                accentColor="violet"
                state={pipe}
                onTrigger={runPipe}
                ticker={ticker || null}
              />
            )}

            {/* History tab */}
            {activeTab === 'history' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-300">Past Reports for <span className="text-white font-mono">{ticker}</span></h3>
                  <button onClick={loadHistory} className="text-xs text-gray-500 hover:text-white transition-colors">Refresh</button>
                </div>
                {historyLoading ? (
                  <div className="flex items-center justify-center py-12 text-gray-600 gap-2">
                    <Loader2 size={16} className="animate-spin" /> Loading history…
                  </div>
                ) : historyItems.length === 0 ? (
                  <p className="text-center py-12 text-gray-600 text-sm">No cached reports yet for {ticker}. Run an analysis first.</p>
                ) : (
                  historyItems.map(item => (
                    <div key={item.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-start justify-between gap-4 hover:border-gray-700 transition-colors">
                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold uppercase tracking-wide text-gray-400 bg-gray-800 px-2 py-0.5 rounded">{item.report_type.replace('_', ' ')}</span>
                          <span className="text-[10px] font-mono text-gray-600 bg-gray-800 px-1.5 py-0.5 rounded">v{item.version}</span>
                          {item.date && <span className="text-[10px] text-gray-600">{item.date}</span>}
                        </div>
                        <p className="text-xs text-gray-500">
                          {new Date(item.created_at).toLocaleString()} · {item.model_used || 'unknown model'}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={async () => {
                            if (expandedReport?.id === item.id) { setExpandedReport(null); return }
                            const full = await getCachedReport(item.id)
                            setExpandedReport(full)
                          }}
                          className="text-xs text-gray-400 hover:text-emerald-400 transition-colors px-2 py-1.5 rounded bg-gray-800 hover:bg-gray-700"
                        >
                          {expandedReport?.id === item.id ? 'Collapse' : 'View'}
                        </button>
                        <a
                          href={getResearchExportUrl(item.id)}
                          download
                          className="flex items-center gap-1 text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded bg-gray-800 hover:bg-gray-700 transition-colors"
                          title="Download .md"
                        >
                          <Download size={12} />
                        </a>
                      </div>
                      {/* Expanded report viewer */}
                      {expandedReport?.id === item.id && expandedReport.output && (
                        <div className="col-span-full w-full mt-3 pt-3 border-t border-gray-800 prose prose-invert prose-sm max-w-none prose-headings:text-white prose-strong:text-emerald-400">
                          <ReactMarkdown>{expandedReport.output}</ReactMarkdown>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </>
      ) : (
        /* Empty state — placeholder cards */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            {
              Icon: ShieldAlert,
              color: 'text-orange-400',
              title: 'Risk Detection',
              desc: 'Identifies reverse-splits, toxic financing, and high short interest traps.',
            },
            {
              Icon: TrendingUp,
              color: 'text-emerald-400',
              title: 'Catalyst Analysis',
              desc: 'Scans recent news and SEC headlines to verify the quality of the move.',
            },
            {
              Icon: BarChart3,
              color: 'text-blue-400',
              title: 'Deep Context',
              desc: 'Combines technical SMA levels with fundamental EPS and float data.',
            },
            {
              Icon: Landmark,
              color: 'text-violet-400',
              title: 'PIPE Detection',
              desc: 'Scans 8-K filings for private placement signals and classifies deals as favorable or toxic.',
            },
          ].map(({ Icon, color, title, desc }) => (
            <div key={title} className="bg-gray-900/50 border border-gray-800 p-6 rounded-2xl space-y-3">
              <Icon className={color} size={24} />
              <h3 className="font-bold text-white">{title}</h3>
              <p className="text-xs text-gray-400">{desc}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
