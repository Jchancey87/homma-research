import { Suspense } from 'react'
import Link from 'next/link'
import LiveGainers from '@/components/LiveGainers'
import WatchlistQuickAccess from '@/components/WatchlistQuickAccess'
import RecentObservations from '@/components/RecentObservations'
import MarketBreadthBar from '@/components/MarketBreadthBar'
import RepeatRunnerAlert from '@/components/RepeatRunnerAlert'
import FollowThrough from '@/components/FollowThrough'
import FloatBucketSummary from '@/components/FloatBucketSummary'
import SectorRotation from '@/components/SectorRotation'
import EconomicCalendar from '@/components/EconomicCalendar'
import HelpGuide from '@/components/HelpGuide'
import { getContinuationPicks } from '@/lib/api'
import {
  TrendingUp, Bookmark, FileText, RotateCcw,
  BarChart2, ArrowRight, CalendarDays,
  Layers, TrendingDown, Zap,
} from 'lucide-react'

export const dynamic = 'force-dynamic'

// ── Shared primitives ─────────────────────────────────────────────────────────

function PanelLabel({
  icon: Icon, label, href,
}: { icon: React.ElementType; label: string; href?: string }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <span className="text-[11px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
        <Icon size={12} className="text-gray-400 dark:text-gray-650" />
        {label}
      </span>
      {href && (
        <Link
          href={href}
          className="flex items-center gap-1 text-[11px] text-gray-600 dark:text-gray-400 hover:text-gray-950 dark:hover:text-white transition-colors"
        >
          View all <ArrowRight size={10} />
        </Link>
      )}
    </div>
  )
}

function Panel({
  children, className = '',
}: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800/80 rounded-2xl p-5 shadow-sm hover:shadow-md dark:hover:shadow-black/30 hover:border-gray-300 dark:hover:border-gray-700/80 transition-all duration-300 ${className}`}>
      {children}
    </div>
  )
}

// ── Morning date header ────────────────────────────────────────────────────────

function MorningHeader() {
  const now = new Date()
  const dayName = now.toLocaleDateString('en-US', { weekday: 'long' })
  const dateStr = now.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
  const hour = now.getHours()
  const greeting = hour < 9 ? 'Pre-market briefing' : hour < 16 ? 'Market open' : 'After-hours'

  return (
    <div className="flex items-baseline justify-between border-b border-gray-200 dark:border-gray-850 pb-3 flex-wrap gap-2">
      <div>
        <h1 className="text-2xl font-black text-gray-900 dark:text-white tracking-tight">{dayName}</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{dateStr} · {greeting}</p>
      </div>
      <Link
        href="/history"
        className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 transition-colors flex items-center gap-1 bg-emerald-50 dark:bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-250/20"
      >
        Command Center <ArrowRight size={11} />
      </Link>
    </div>
  )
}

// ── Continuation picks (promoted from watchlist page) ─────────────────────────

async function ContinuationPicksPanel() {
  let picks: any[] = []
  try { picks = await getContinuationPicks() } catch {}

  const active = picks.filter(p => p.is_active).slice(0, 5)

  return (
    <Panel>
      <PanelLabel icon={Zap} label="AI Continuation Picks" href="/watchlist" />
      {active.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-6 border border-dashed border-gray-200 dark:border-gray-800 rounded-xl gap-2 text-center bg-gray-50/50 dark:bg-gray-900/10">
          <Zap size={22} className="text-gray-400 dark:text-gray-650" />
          <p className="text-gray-500 dark:text-gray-400 text-xs font-medium">No active picks found</p>
          <Link
            href="/watchlist"
            className="text-[11.5px] font-bold text-emerald-600 dark:text-emerald-400 hover:underline"
          >
            Configure picks in Watchlist
          </Link>
        </div>
      ) : (
        <div className="space-y-0.5">
          <div className="flex text-[10px] text-gray-400 dark:text-gray-700 uppercase tracking-wide font-semibold px-2 pb-1 border-b border-gray-100 dark:border-gray-900 mb-1">
            <span className="w-6 shrink-0">#</span>
            <span className="flex-1">Ticker</span>
            <span className="w-16 text-right">Sel. Gap</span>
            <span className="w-24 text-right">Today</span>
          </div>
          {active.map((p, i) => (
            <Link
              key={p.id}
              href={`/research?ticker=${p.ticker}`}
              className="group flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors"
            >
              <span className="text-[11px] text-gray-400 dark:text-gray-700 w-6 shrink-0">#{i + 1}</span>
              <span className="text-sm font-bold text-gray-900 dark:text-white font-mono flex-1 group-hover:text-emerald-400 transition-colors">{p.ticker}</span>
              {p.gap_pct != null && (
                <span className="text-xs font-mono text-gray-550 dark:text-gray-400 w-16 text-right">
                  +{p.gap_pct.toFixed(1)}%
                </span>
              )}
              <div className="w-24 text-right flex flex-col items-end shrink-0">
                {p.today_change_pct != null ? (
                  <>
                    <span className={`text-xs font-mono font-bold leading-none ${p.today_change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {p.today_change_pct >= 0 ? '+' : ''}{p.today_change_pct.toFixed(1)}%
                    </span>
                    {p.today_last != null && (
                      <span className="text-[9px] text-gray-500 font-mono mt-0.5">
                        ${p.today_last.toFixed(2)}
                      </span>
                    )}
                  </>
                ) : (
                  <span className="text-xs font-mono text-gray-500">—</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </Panel>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function DashboardPage() {
  return (
    <div className="space-y-6 max-w-[1600px] mx-auto">

      {/* ── Morning header ── */}
      <MorningHeader />

      {/* ── Help Guide ── */}
      <HelpGuide />

      {/* ── Market breadth strip (full width) ── */}
      <Suspense fallback={<div className="h-10 bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800/80 rounded-2xl animate-pulse" />}>
        <MarketBreadthBar />
      </Suspense>

      {/* ── Economic calendar (full width, compact) ── */}
      <Panel>
        <PanelLabel icon={CalendarDays} label="This Week's Calendar" />
        <Suspense fallback={<div className="h-8 bg-gray-150 dark:bg-gray-800/40 rounded animate-pulse" />}>
          <EconomicCalendar />
        </Suspense>
      </Panel>

      {/* ── Row 1: Live screener (full width) ── */}
      <Panel>
        <div className="flex items-center justify-between mb-3 border-b border-gray-100 dark:border-gray-900/50 pb-2">
          <span className="text-[11px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
            <TrendingUp size={12} className="text-gray-400 dark:text-gray-650" />
            Live Gainer Screener
          </span>
          <div className="flex items-center gap-3">
            <Link href="/daily-charts" className="text-[11px] text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-1 font-semibold">
              Charts <ArrowRight size={10} />
            </Link>
            <Link href="/history" className="text-[11px] text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors flex items-center gap-1">
              History <ArrowRight size={10} />
            </Link>
          </div>
        </div>
        <LiveGainers />
      </Panel>

      {/* ── Row 2: Repeat runners + Follow-through (stacked on mobile, side-by-side on lg) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel>
          <PanelLabel icon={RotateCcw} label="Repeat Runners" href="/history" />
          <Suspense fallback={<div className="space-y-2 animate-pulse">{[1,2].map(i=><div key={i} className="h-10 bg-gray-150 dark:bg-gray-800/60 rounded-lg" />)}</div>}>
            <RepeatRunnerAlert />
          </Suspense>
        </Panel>

        <Panel>
          <PanelLabel icon={TrendingDown} label="Yesterday's Follow-Through" />
          <Suspense fallback={<div className="space-y-2 animate-pulse">{[1,2,3].map(i=><div key={i} className="h-8 bg-gray-150 dark:bg-gray-800/60 rounded" />)}</div>}>
            <FollowThrough />
          </Suspense>
        </Panel>
      </div>

      {/* ── Row 3: Float buckets + Sector rotation + AI picks (stacked on mobile, 3-cols on xl) ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        <Panel>
          <PanelLabel icon={Layers} label="Float in Play" />
          <Suspense fallback={<div className="space-y-2 animate-pulse">{[1,2,3].map(i=><div key={i} className="h-8 bg-gray-150 dark:bg-gray-800/60 rounded" />)}</div>}>
            <FloatBucketSummary />
          </Suspense>
        </Panel>

        <Panel>
          <PanelLabel icon={BarChart2} label="Sector Rotation" />
          <Suspense fallback={<div className="space-y-2 animate-pulse">{[1,2,3,4].map(i=><div key={i} className="h-7 bg-gray-150 dark:bg-gray-800/60 rounded" />)}</div>}>
            <SectorRotation />
          </Suspense>
        </Panel>

        <Suspense fallback={<Panel><div className="animate-pulse h-32 bg-gray-150 dark:bg-gray-800/40 rounded" /></Panel>}>
          <ContinuationPicksPanel />
        </Suspense>
      </div>

      {/* ── Row 4: Watchlist (live prices) + Observations (stacked on mobile, side-by-side on lg) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Panel>
          <PanelLabel icon={Bookmark} label="Watchlist" href="/watchlist" />
          <Suspense fallback={<div className="space-y-1.5 animate-pulse">{[1,2,3].map(i=><div key={i} className="h-9 bg-gray-150 dark:bg-gray-800/60 rounded-lg" />)}</div>}>
            <WatchlistQuickAccess />
          </Suspense>
        </Panel>

        <Panel>
          <PanelLabel icon={FileText} label="Recent Observations" href="/observations" />
          <Suspense fallback={<div className="h-32 bg-gray-150 dark:bg-gray-800/40 rounded animate-pulse" />}>
            <RecentObservations />
          </Suspense>
        </Panel>
      </div>

    </div>
  )
}
