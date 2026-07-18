import { Suspense } from 'react'
import Link from 'next/link'
import LiveGainers from '@/components/LiveGainers'
import CommandSummaryStrip from '@/components/CommandSummaryStrip'
import RepeatRunnerAlert from '@/components/RepeatRunnerAlert'
import FollowThrough from '@/components/FollowThrough'
import FloatBucketSummary from '@/components/FloatBucketSummary'
import SectorRotation from '@/components/SectorRotation'
import EconomicCalendar from '@/components/EconomicCalendar'
import HelpGuide from '@/components/HelpGuide'
import DashboardHeader from '@/components/DashboardHeader'
import { Panel, PanelLabel } from '@/components/Panel'
import { getContinuationPicks, ContinuationPick } from '@/lib/api'
import {
  TrendingUp, RotateCcw,
  BarChart2, ArrowRight, CalendarDays,
  Layers, TrendingDown, Zap,
} from 'lucide-react'

export const dynamic = 'force-dynamic'

// ── Dashboard Header ──────────────────────────────────────────────────────────

// ── Continuation picks (promoted from watchlist page) ─────────────────────────

async function ContinuationPicksPanel() {
  let picks: ContinuationPick[] = []
  try { picks = await getContinuationPicks() } catch {}

  const active = picks.filter(p => p.is_active).slice(0, 5)

  return (
    <Panel>
      <PanelLabel icon={Zap} label="AI Continuation Picks" href="/watchlist" />
      {active.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2 border border-[#262626] bg-[#050505]">
          <Zap size={22} className="text-gray-700" />
          <p className="text-gray-500 text-xs uppercase tracking-wider font-mono">No active picks found</p>
          <Link
            href="/watchlist"
            className="text-[11px] font-mono text-[#00ff00] hover:underline"
          >
            Configure picks in Watchlist
          </Link>
        </div>
      ) : (
        <div className="space-y-0.5">
          <div className="flex text-[10px] font-mono text-gray-600 uppercase tracking-wider px-2 pb-1 border-b border-[#1a1a1a] mb-1">
            <span className="w-6 shrink-0">#</span>
            <span className="flex-1">Ticker</span>
            <span className="w-16 text-right">Sel. Gap</span>
            <span className="w-24 text-right">Today</span>
          </div>
          {active.map((p, i) => (
            <Link
              key={p.id}
              href={`/research?ticker=${p.ticker}`}
              className="group flex items-center gap-2 px-2 py-1.5 font-mono hover:bg-[#0a0a0a] border-b border-[#1a1a1a] transition-colors rounded-none"
            >
              <span className="text-[11px] text-gray-500 w-6 shrink-0">#{i + 1}</span>
              <span className="text-sm font-bold text-white font-mono flex-1 group-hover:text-[#00ff00] transition-colors">{p.ticker}</span>
              {p.gap_pct != null && (
                <span className="text-xs font-mono text-gray-400 w-16 text-right">
                  +{p.gap_pct.toFixed(1)}%
                </span>
              )}
              <div className="w-24 text-right flex flex-col items-end shrink-0">
                {p.today_change_pct != null ? (
                  <>
                    <span className={`text-xs font-mono font-bold leading-none ${p.today_change_pct >= 0 ? 'text-[#00ff00]' : 'text-[#ff003c]'}`}>
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

export default function DashboardPage() {
  return (
    <div className="space-y-2 max-w-[1920px] mx-auto">

      {/* ── Dashboard Header ── */}
      <DashboardHeader />

      {/* ── Command Summary Strip (Market Regime Card) ── */}
      <CommandSummaryStrip />


      {/* ── Row 1: Live screener (full width) ── */}
      <Panel>
        <div className="flex items-center justify-between mb-3 border-b border-[#1a1a1a] pb-2">
          <span className="text-[11px] font-mono font-bold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
            <TrendingUp size={12} className="text-gray-500" />
            Live Gainer Screener
          </span>
          <div className="flex items-center gap-3">
            <Link href="/daily-charts" className="text-[11px] font-mono text-[#00ff00] hover:underline flex items-center gap-1">
              Charts <ArrowRight size={10} />
            </Link>
            <Link href="/history" className="text-[11px] font-mono text-gray-500 hover:text-white transition-colors flex items-center gap-1">
              History <ArrowRight size={10} />
            </Link>
          </div>
        </div>
        <LiveGainers />
      </Panel>

      {/* ── Row 2: Repeat runners + Follow-through (stacked on mobile, side-by-side on lg) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
        <Panel>
          <PanelLabel icon={RotateCcw} label="Repeat Runners" href="/history" />
          <Suspense fallback={<div className="space-y-2 animate-pulse">{[1,2].map(i=><div key={i} className="h-10 bg-[#111] rounded-none" />)}</div>}>
            <RepeatRunnerAlert />
          </Suspense>
        </Panel>

        <Panel>
          <PanelLabel icon={TrendingDown} label="Yesterday's Follow-Through" />
          <Suspense fallback={<div className="space-y-2 animate-pulse">{[1,2,3].map(i=><div key={i} className="h-8 bg-[#111] rounded-none" />)}</div>}>
            <FollowThrough />
          </Suspense>
        </Panel>
      </div>

      {/* ── Row 3: Float buckets + Sector rotation + AI picks (stacked on mobile, 3-cols on xl) ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
        <Panel>
          <PanelLabel icon={Layers} label="Float in Play" />
          <Suspense fallback={<div className="space-y-2 animate-pulse">{[1,2,3].map(i=><div key={i} className="h-8 bg-[#111] rounded-none" />)}</div>}>
            <FloatBucketSummary />
          </Suspense>
        </Panel>

        <Panel>
          <PanelLabel icon={BarChart2} label="Sector Rotation" />
          <Suspense fallback={<div className="space-y-2 animate-pulse">{[1,2,3,4].map(i=><div key={i} className="h-7 bg-[#111] rounded-none" />)}</div>}>
            <SectorRotation />
          </Suspense>
        </Panel>

        <Suspense fallback={<Panel><div className="animate-pulse h-32 bg-[#111] rounded-none" /></Panel>}>
          <ContinuationPicksPanel />
        </Suspense>
      </div>


      {/* ── Economic calendar (full width, compact) ── */}
      <Panel>
        <PanelLabel icon={CalendarDays} label="This Week's Calendar" />
        <Suspense fallback={<div className="h-8 bg-[#111] rounded-none animate-pulse" />}>
          <EconomicCalendar />
        </Suspense>
      </Panel>

      {/* ── Help Guide ── */}
      <HelpGuide />

    </div>
  )
}
