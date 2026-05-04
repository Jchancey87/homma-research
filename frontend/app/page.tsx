import { Suspense } from 'react'
import HeatMap from '@/components/HeatMap'
import TodayGainers from '@/components/TodayGainers'
import WatchlistQuickAccess from '@/components/WatchlistQuickAccess'
import RecentObservations from '@/components/RecentObservations'
import SystemStatus from '@/components/SystemStatus'
import { getHeatmap, getArchetypes } from '@/lib/api'
import { TrendingUp, Bookmark, FileText, Activity } from 'lucide-react'

export const dynamic = 'force-dynamic'

function SectionHeader({ icon: Icon, label, href }: {
  icon: React.ElementType
  label: string
  href?: string
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide flex items-center gap-2">
        <Icon size={14} className="text-emerald-400" />
        {label}
      </h2>
      {href && (
        <a href={href} className="text-xs text-gray-600 hover:text-emerald-400 transition-colors">
          View all →
        </a>
      )}
    </div>
  )
}

export default async function DashboardPage() {
  let heatmapSpec = null
  let archetypes: any[] = []

  try { heatmapSpec = await getHeatmap() }    catch { /* no data yet */ }
  try { archetypes  = await getArchetypes() } catch { /* no data yet */ }

  return (
    <div className="space-y-6">

      {/* Page title */}
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-0.5">Your market research briefing</p>
      </div>

      {/* ── Row 1: Today's Movers (full width) ── */}
      <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide flex items-center gap-2">
            <TrendingUp size={14} className="text-emerald-400" />
            Today&apos;s Top Movers
          </h2>
          <div className="flex items-center gap-3">
            <a href="/daily-charts" className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors font-medium">
              View charts →
            </a>
            <a href="/gainers" className="text-xs text-gray-600 hover:text-gray-400 transition-colors">
              Table view
            </a>
          </div>
        </div>
        <Suspense fallback={<p className="text-gray-600 text-sm py-4">Loading gainers…</p>}>
          <TodayGainers />
        </Suspense>
      </section>

      {/* ── Row 2: Watchlist quick-access + Recent observations ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
          <SectionHeader icon={Bookmark} label="Watchlist" href="/watchlist" />
          <WatchlistQuickAccess />
        </section>

        <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
          <SectionHeader icon={FileText} label="Recent Observations" href="/observations" />
          <RecentObservations />
        </section>
      </div>

      {/* ── Row 3: Archetype stats + Heatmap ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-4">Archetype Stats</h2>
          {archetypes.length === 0 ? (
            <p className="text-gray-600 text-sm">No chart captures yet. Upload your first chart to see patterns.</p>
          ) : (
            <div className="space-y-2">
              {archetypes.map((a: any) => (
                <div key={a.tag} className="flex items-center justify-between bg-gray-800/60 rounded-lg px-3 py-2">
                  <span className="text-sm font-medium text-gray-200">{a.tag}</span>
                  <div className="flex gap-4 text-xs text-gray-400">
                    <span>n={a.count}</span>
                    {a.avg_gap_pct    != null && <span className="text-emerald-400">+{a.avg_gap_pct}%</span>}
                    {a.avg_float_m    != null && <span>{a.avg_float_m}M float</span>}
                    {a.avg_cleanliness != null && <span>⭐ {a.avg_cleanliness}/10</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide mb-4">Float × RVOL Heatmap</h2>
          <HeatMap spec={heatmapSpec} />
        </section>
      </div>

      {/* ── Row 4: System Status (collapsible feel via smaller treatment) ── */}
      <details className="bg-gray-900 border border-gray-800 rounded-2xl group" open={false}>
        <summary className="flex items-center gap-2 px-6 py-4 cursor-pointer list-none text-sm font-semibold text-gray-400 hover:text-gray-200 transition-colors select-none">
          <Activity size={14} className="text-gray-500 group-open:text-emerald-400 transition-colors" />
          System Status
          <span className="ml-auto text-xs text-gray-600 group-open:hidden">click to expand</span>
        </summary>
        <div className="px-6 pb-6 border-t border-gray-800 pt-4">
          <SystemStatus />
        </div>
      </details>

    </div>
  )
}
