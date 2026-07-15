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
    setRisk({ ...EMPTY_FEATURE, loading: true, status: 'Scanning SEC filings & corporate actions\u2026' })
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
    setCatalyst({ ...EMPTY_FEATURE, loading: true, status: 'Parsing news & regulatory events\u2026' })
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
    setContext({ ...EMPTY_FEATURE, loading: true, status: 'Building multi-timeframe technical picture\u2026' })
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
    setPipe({ ...EMPTY_FEATURE, loading: true, status: 'Scanning SEC 8-K filings for PIPE signals\u2026' })
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

    setMain({ ...EMPTY_MAIN, loading: true, status: 'Gathering market data\u2026' })
    setRisk({ ...EMPTY_FEATURE, loading: true, status: 'Scanning SEC filings & corporate actions\u2026' })
    setCatalyst({ ...EMPTY_FEATURE, loading: true, status: 'Parsing news & regulatory events\u2026' })
    setContext({ ...EMPTY_FEATURE, loading: true, status: 'Building multi-timeframe technical picture\u2026' })
    setPipe({ ...EMPTY_FEATURE, loading: true, status: 'Scanning SEC 8-K filings for PIPE signals\u2026' })
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
        else if ('job_id' in r) setMain(s => ({ ...s, jobId: r.job_id, status: 'AI Analyst is investigating\u2026' }))
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
    <div className="space-y-2 p-0">

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-[#050505] border border-[#262626]">
        <div>
          <h1 className="font-mono text-sm font-bold text-white uppercase flex items-center gap-1.5">
            <Search size={14} className="text-[#00f0ff]" />
            Deep Ticker Research
          </h1>
          <p className="font-mono text-[10px] text-gray-500 mt-0.5">
            Comprehensive fundamental, technical, and risk analysis
          </p>
        </div>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch}>
        <div className="flex items-center gap-1.5 px-3 py-2 bg-[#0a0a0a] border border-[#262626]">
          {/* Ticker input */}
          <input
            id="research-ticker-input"
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="TICKER (e.g. NVDA, TSLA, GME)"
            className="flex-1 bg-black border border-[#262626] text-white font-mono text-sm px-3 py-2 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark] uppercase placeholder:text-gray-700"
            disabled={anyActive}
          />

          {/* Optional date picker */}
          <div className="relative">
            <CalendarDays size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-600 pointer-events-none" />
            <input
              id="research-date-input"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="bg-black border border-[#262626] text-gray-400 font-mono text-[11px] pl-7 pr-2 py-2 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark] w-36"
              disabled={anyActive}
              title="Optional: anchor analysis to a specific trading date"
            />
          </div>

          {/* Analyze button */}
          <button
            id="research-analyze-btn"
            type="submit"
            disabled={anyActive || !ticker}
            className="flex items-center justify-center gap-1.5 px-4 py-2 border border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00] font-mono text-xs font-bold rounded-none transition-colors hover:bg-emerald-950/40 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {anyActive
              ? <Loader2 className="animate-spin text-[#00ff00]" size={13} />
              : 'ANALYZE'}
          </button>
        </div>

        {date && (
          <p className="font-mono text-[10px] text-gray-600 px-3 pt-1">
            Catalyst analysis anchored to <span className="text-[#00f0ff] font-mono">{date}</span>
          </p>
        )}
      </form>

      {/* Tabs — only show after at least one report has been started */}
      {anyReport || anyActive ? (
        <>
          {/* Tab bar */}
          <div className="flex bg-black border-b border-[#262626]">
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
                  className={
                    isActive
                      ? 'flex items-center gap-1.5 px-4 py-2 text-[11px] font-mono font-bold text-[#00ff00] border-b-2 border-[#00ff00] bg-[#0a0a0a] -mb-px'
                      : 'flex items-center gap-1.5 px-4 py-2 text-[11px] font-mono text-gray-500 hover:text-gray-300 transition-colors'
                  }
                >
                  {isLoading
                    ? <Loader2 size={12} className="animate-spin text-[#00ff00]" />
                    : <Icon size={12} className={isActive ? 'text-[#00ff00]' : ''} />
                  }
                  <span className="hidden sm:inline">{label}</span>
                  {hasReport && !isLoading && (
                    <span className="w-1 h-1 bg-[#00ff00] rounded-none" />
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
                  <div className="bg-emerald-950/20 border border-[#00ff00]/20 p-8 text-center space-y-3 animate-pulse rounded-none">
                    <Loader2 className="mx-auto text-[#00ff00] animate-spin" size={28} />
                    <p className="font-mono text-sm text-[#00ff00]">{main.status}</p>
                    <p className="font-mono text-[11px] text-gray-500">Checking SEC filings, short interest, and technical levels\u2026</p>
                  </div>
                )}
                {main.error && !main.loading && (
                  <div className="bg-red-950/20 border border-[#ff003c]/20 p-4 flex items-start gap-3 rounded-none">
                    <AlertCircle className="text-[#ff003c] shrink-0" size={16} />
                    <div>
                      <p className="font-mono text-xs font-bold text-[#ff003c]">RESEARCH ERROR</p>
                      <p className="font-mono text-xs text-gray-400 mt-0.5">{main.error}</p>
                    </div>
                  </div>
                )}
                {main.report && !main.loading && (
                  <div className="bg-[#050505] border border-[#262626] rounded-none overflow-hidden">
                    <div className="flex items-center justify-between px-3 py-2 bg-[#0a0a0a] border-b border-[#262626]">
                      <div className="flex items-center gap-2 font-mono text-[11px] font-bold text-[#00ff00] uppercase tracking-wider">
                        <FileText size={12} />
                        ANALYSIS REPORT: {ticker}
                      </div>
                      <div className="font-mono text-[10px] text-gray-500 uppercase tracking-widest">
                        {main.model || 'AI Analyst'}
                      </div>
                    </div>
                    <div className="p-4 font-mono text-xs text-gray-300 leading-relaxed prose-invert">
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
              <div className="space-y-2 pt-2">
                <div className="flex items-center justify-between px-1">
                  <span className="font-mono text-[10px] text-gray-500 uppercase tracking-wider">
                    Past Reports for <span className="text-white font-mono">{ticker}</span>
                  </span>
                  <button
                    onClick={loadHistory}
                    className="font-mono text-[10px] text-gray-500 hover:text-white transition-colors border border-[#262626] px-2 py-0.5 rounded-none"
                  >
                    REFRESH
                  </button>
                </div>
                {historyLoading ? (
                  <div className="flex items-center justify-center py-12 gap-2 border border-[#262626] bg-[#050505]">
                    <Loader2 size={14} className="animate-spin text-[#00ff00]" />
                    <span className="font-mono text-xs text-gray-500 uppercase tracking-wider">Loading history\u2026</span>
                  </div>
                ) : historyItems.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 gap-2 border border-[#262626] bg-[#050505]">
                    <History size={24} className="text-gray-700" />
                    <p className="font-mono text-xs text-gray-500 uppercase tracking-wider">No cached reports for {ticker}</p>
                  </div>
                ) : (
                  historyItems.map(item => (
                    <div key={item.id} className="bg-[#0a0a0a] border border-[#262626] p-2 space-y-1 hover:border-[#444] transition-colors rounded-none">
                      <div className="flex items-start justify-between gap-4">
                        <div className="space-y-1 flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            {/* Report type badge */}
                            <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-[#111] text-gray-500 border border-[#262626] rounded-none uppercase">
                              {item.report_type.replace('_', ' ')}
                            </span>
                            {/* Version badge */}
                            <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-[#111] text-gray-500 border border-[#262626] rounded-none">
                              v{item.version}
                            </span>
                            {item.date && (
                              <span className="font-mono text-[10px] text-gray-500">{item.date}</span>
                            )}
                          </div>
                          <p className="font-mono text-[10px] text-gray-500">
                            {new Date(item.created_at).toLocaleString()} · {item.model_used || 'unknown model'}
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            onClick={async () => {
                              if (expandedReport?.id === item.id) { setExpandedReport(null); return }
                              const full = await getCachedReport(item.id)
                              setExpandedReport(full)
                            }}
                            className="font-mono text-[10px] text-[#00f0ff] border border-[#00f0ff]/30 px-1.5 py-0.5 hover:bg-[#00f0ff]/5 transition-colors rounded-none"
                          >
                            {expandedReport?.id === item.id ? 'COLLAPSE' : 'VIEW'}
                          </button>
                          <a
                            href={getResearchExportUrl(item.id)}
                            download
                            className="flex items-center gap-1 font-mono text-[10px] text-gray-400 border border-[#262626] px-1.5 py-0.5 hover:text-white hover:border-[#444] transition-colors rounded-none"
                            title="Download .md"
                          >
                            <Download size={10} />
                          </a>
                        </div>
                      </div>
                      {/* Expanded report viewer */}
                      {expandedReport?.id === item.id && expandedReport.output && (
                        <div className="mt-2 pt-2 border-t border-[#262626] font-mono text-xs text-gray-300 leading-relaxed prose-invert">
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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          {[
            {
              Icon: ShieldAlert,
              color: 'text-amber-400',
              title: 'Risk Detection',
              desc: 'Identifies reverse-splits, toxic financing, and high short interest traps.',
            },
            {
              Icon: TrendingUp,
              color: 'text-[#00ff00]',
              title: 'Catalyst Analysis',
              desc: 'Scans recent news and SEC headlines to verify the quality of the move.',
            },
            {
              Icon: BarChart3,
              color: 'text-[#00f0ff]',
              title: 'Deep Context',
              desc: 'Combines technical SMA levels with fundamental EPS and float data.',
            },
            {
              Icon: Landmark,
              color: 'text-gray-400',
              title: 'PIPE Detection',
              desc: 'Scans 8-K filings for private placement signals and classifies deals as favorable or toxic.',
            },
          ].map(({ Icon, color, title, desc }) => (
            <div key={title} className="bg-[#050505] border border-[#262626] p-3 space-y-2 rounded-none">
              <Icon className={color} size={16} />
              <h3 className="font-mono text-xs font-bold text-white uppercase tracking-wider">{title}</h3>
              <p className="font-mono text-[10px] text-gray-500">{desc}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
