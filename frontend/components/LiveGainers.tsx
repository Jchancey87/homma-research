'use client'

import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import {
  getLiveGainers,
  LiveGainerSnapshot,
  LiveGainerRow,
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  updateWatchlistItem,
  WatchlistItem,
  getGainersSummary,
} from '@/lib/api'
import { useRouter } from 'next/navigation'
import {
  RefreshCw,
  TrendingUp,
  Clock,
  Wifi,
  WifiOff,
  Database,
  Zap,
} from 'lucide-react'
import { GainerTable } from './live-gainers/GainerTable'
import { SessionBadge } from './live-gainers/badges'
import { useAlertStream } from './live-gainers/useAlertStream'
import { LiveGainersModal } from './LiveGainersModal'
import { ToastStack } from './ToastStack'

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtAge(isoUtc: string | null): string {
  if (!isoUtc) return ''
  const seconds = Math.floor((Date.now() - new Date(isoUtc).getTime()) / 1000)
  if (seconds < 60)   return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

const PRICE_FILTER_KEY = 'price-filter-enabled'
const PRICE_FILTER_EVENT = 'price-filter-changed'
const PRICE_MIN = 1.0
const PRICE_MAX = 30.0

interface LiveGainersProps {
  initialSnap?: LiveGainerSnapshot | null
  initialWatchlist?: WatchlistItem[]
  initialSummary?: { date: string | null; total: number } | null
}

export default function LiveGainers({ initialSnap = null, initialWatchlist = [], initialSummary = null }: LiveGainersProps) {
  const router = useRouter()
  const [snap,        setSnap]        = useState<LiveGainerSnapshot | null>(initialSnap)
  const [loading,     setLoading]     = useState(!initialSnap)
  const [error,       setError]       = useState<string | null>(null)
  const [refreshing,  setRefreshing]  = useState(false)
  const [ageStr,      setAgeStr]      = useState('')
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Real-time Breakout Alerts & Notifications (Phase 3)
  const {
    flashingTickers,
    toasts,
    dismissToast,
    audioChimesEnabled,
    setAudioChimesEnabled,
    toastStackEnabled,
    setToastStackEnabled,
  } = useAlertStream()

  // UX states
  const [modalGainer, setModalGainer] = useState<LiveGainerRow | null>(null)
  const [watchlist, setWatchlist]     = useState<WatchlistItem[]>(initialWatchlist)
  const [watchlistLoading, setWatchlistLoading] = useState(false)
  const [priceFilterEnabled, setPriceFilterEnabled] = useState(true)

  useEffect(() => {
    const val = localStorage.getItem(PRICE_FILTER_KEY)
    if (val !== null) setPriceFilterEnabled(val === 'true')
    const handleSync = () => {
      const syncedVal = localStorage.getItem(PRICE_FILTER_KEY)
      if (syncedVal !== null) setPriceFilterEnabled(syncedVal === 'true')
    }
    window.addEventListener(PRICE_FILTER_EVENT, handleSync)
    return () => window.removeEventListener(PRICE_FILTER_EVENT, handleSync)
  }, [])

  const fetchData = useCallback(async (force = false) => {
    try {
      if (force) setRefreshing(true)
      const data = await getLiveGainers(force)
      setSnap(data)
      setError(null)
    } catch (e: unknown) {
      setError((e as Error)?.message ?? 'Failed to load live data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  const fetchWatchlist = useCallback(async () => {
    try {
      const items = await getWatchlist()
      setWatchlist(items)
    } catch (e) {
      console.error('Failed to load watchlist', e)
    }
  }, [])

  // Initial load + polling
  useEffect(() => {
    if (!initialSnap) {
      fetchData()
    }
    if (!initialWatchlist || initialWatchlist.length === 0) {
      fetchWatchlist()
    }

    const startPolling = () => {
      if (timerRef.current) clearInterval(timerRef.current)
      timerRef.current = setInterval(() => {
        if (document.visibilityState === 'visible') {
          fetchData()
        }
      }, 3000)
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchData()
        startPolling()
      } else {
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
      }
    }

    if (document.visibilityState === 'visible') {
      startPolling()
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [fetchData, fetchWatchlist, initialSnap, initialWatchlist])

  // Live "X ago" counter (updates every 5s)
  useEffect(() => {
    const tick = () => setAgeStr(snap?.fetched_at ? fmtAge(snap.fetched_at) : '')
    tick()
    const id = setInterval(tick, 5_000)
    return () => clearInterval(id)
  }, [snap?.fetched_at])

  // Sync watchlist notes when modal ticker changes is now handled inside
  // LiveGainersModal (it owns the notes textarea state).

  // Prevent background body scroll when detailed view modal is open
  useEffect(() => {
    if (modalGainer) {
      document.body.classList.add('overflow-hidden')
    } else {
      document.body.classList.remove('overflow-hidden')
    }
    return () => {
      document.body.classList.remove('overflow-hidden')
    }
  }, [modalGainer])

  const handleResearch = (g: LiveGainerRow) => {
    const today = new Date().toISOString().slice(0, 10)
    router.push(`/research?ticker=${g.ticker}&date=${today}`)
  }

  const handleToggleWatchlist = async () => {
    if (!modalGainer) return
    setWatchlistLoading(true)
    try {
      const item = watchlist.find(w => w.ticker === modalGainer.ticker)
      if (item) {
        await removeFromWatchlist(modalGainer.ticker)
      } else {
        await addToWatchlist({
          ticker: modalGainer.ticker,
          sector: modalGainer.sector || undefined
        })
      }
      await fetchWatchlist()
    } catch {
      alert('Failed to update watchlist')
    } finally {
      setWatchlistLoading(false)
    }
  }

  const handleSaveNotes = async (notes: string) => {
    if (!modalGainer) return
    try {
      await updateWatchlistItem(modalGainer.ticker, { notes })
      await fetchWatchlist()
    } catch {
      alert('Failed to save notes')
    }
  }

  const session    = snap?.session ?? 'closed'
  const isActive   = session !== 'closed'

  const filteredGainers = useMemo(() => {
    const list = snap?.gainers ?? []
    if (!priceFilterEnabled) return list
    return list.filter(g => {
      const p = g.last_price
      return p != null && p >= PRICE_MIN && p <= PRICE_MAX
    })
  }, [snap, priceFilterEnabled])

  return (
    <div className="space-y-2.5">
      {/* Bloomberg-style Functional Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between border border-[#2b3547]/50 bg-[#0E1116] text-[11px] font-mono select-none w-full min-h-[30px]">
        {/* Left Side: Terminal Status Metrics */}
        <div className="flex items-center gap-3 px-2.5 py-1 flex-wrap">
          {snap && (
            <SessionBadge session={session} label={snap.session_label} />
          )}
          {ageStr && (
            <span className="flex items-center gap-1 text-text-muted">
              <Clock size={10} />
              {ageStr}
            </span>
          )}
          {isActive && !error && (
            <span className="flex items-center gap-1 text-green-custom font-bold">
              <Wifi size={10} />
              LIVE 3S
            </span>
          )}
          {snap?.fast_mode_active && (
            <span className="flex items-center gap-1 font-bold text-amber-custom">
              <Zap size={10} className="animate-pulse fill-amber-custom" />
              FAST ({snap.streaming_symbols_count} SYM)
            </span>
          )}
          {snap?.redis_connected ? (
            <span className="flex items-center gap-1 text-green-custom font-bold">
              <Database size={10} />
              REDIS: OK
            </span>
          ) : (
            <span className="flex items-center gap-1 text-red-custom font-bold animate-pulse">
              <Database size={10} />
              REDIS: DISCONNECT
            </span>
          )}
          {error && (
            <span className="flex items-center gap-1 text-red-custom font-bold">
              <WifiOff size={10} />
              {error}
            </span>
          )}
        </div>

        {/* Right Side: Function Keys Control Strip */}
        <div className="flex items-stretch border-t sm:border-t-0 sm:border-l border-[#2b3547]/50 h-full">
          {/* Audio Chime F1 */}
          <button
            onClick={() => setAudioChimesEnabled(!audioChimesEnabled)}
            className={`px-3 py-1.5 sm:py-0 flex items-center gap-1 hover:bg-[#1C2330] border-r border-[#2b3547]/50 transition-colors ${
              audioChimesEnabled ? 'text-green-custom font-bold bg-green-custom/5' : 'text-text-muted hover:text-text-primary'
            }`}
            title="Toggle Audio Chimes on Breakouts [F1]"
          >
            <span>[F1] AUDIO: {audioChimesEnabled ? 'ON' : 'OFF'}</span>
          </button>

          {/* Toasts Toggle F2 */}
          <button
            onClick={() => setToastStackEnabled(!toastStackEnabled)}
            className={`px-3 py-1.5 sm:py-0 flex items-center gap-1 hover:bg-[#1C2330] border-r border-[#2b3547]/50 transition-colors ${
              toastStackEnabled ? 'text-green-custom font-bold bg-green-custom/5' : 'text-text-muted hover:text-text-primary'
            }`}
            title="Toggle Toast Notifications [F2]"
          >
            <span>[F2] TOASTS: {toastStackEnabled ? 'ON' : 'OFF'}</span>
          </button>

          {/* Price Filter F3 */}
          <button
            onClick={() => {
              const newValue = !priceFilterEnabled
              setPriceFilterEnabled(newValue)
              localStorage.setItem(PRICE_FILTER_KEY, String(newValue))
              window.dispatchEvent(new Event(PRICE_FILTER_EVENT))
            }}
            className={`px-3 py-1.5 sm:py-0 flex items-center gap-1 hover:bg-[#1C2330] border-r border-[#2b3547]/50 transition-colors ${
              priceFilterEnabled ? 'text-info-custom font-bold bg-info-custom/5' : 'text-text-muted hover:text-text-primary'
            }`}
            title="Toggle $1-$30 Price Filter [F3]"
          >
            <span>[F3] FILTER $1-$30: {priceFilterEnabled ? 'ON' : 'OFF'}</span>
          </button>

          {/* Refresh F5 */}
          <button
            id="live-gainers-refresh"
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="px-3 py-1.5 sm:py-0 flex items-center gap-1 text-text-muted hover:text-green-custom hover:bg-[#1C2330] transition-colors disabled:opacity-40"
            title="Manual Database Poll [F5]"
          >
            <RefreshCw size={10} className={refreshing ? 'animate-spin' : ''} />
            <span>[F5] REFRESH</span>
          </button>
        </div>
      </div>

      {/* EOD persist notice */}
      {session === 'after_hours' && (
        <div className="flex items-center gap-2 px-3 py-1 bg-violet-500/5 border border-violet-500/10 text-xs text-violet-300">
          <TrendingUp size={11} className="shrink-0" />
          These gainers will be automatically saved to your database at 8:00 PM ET.
        </div>
      )}

      {/* 3-Column Terminal Panel Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-2.5">
        <GainerTable
          gainers={loading ? [] : filteredGainers}
          fullList={loading ? [] : filteredGainers}
          title="All Live Gainers"
          emptyMessage={
            session === 'closed'
              ? 'Market is closed. Check back during pre-market (4 AM ET) or regular hours.'
              : 'No gainers meeting criteria right now.'
          }
          onOpenModal={setModalGainer}
          handleResearch={handleResearch}
          loading={loading}
          flashingTickers={flashingTickers}
        />
        <GainerTable
          gainers={loading ? [] : filteredGainers.filter(g => g.atr_hod != null && g.atr_hod < 1.0)}
          fullList={loading ? [] : filteredGainers}
          title="Near HOD Radar"
          emptyMessage="No Near HOD breakout setups coiling right now (AtrHoD < 1.0)."
          onOpenModal={setModalGainer}
          handleResearch={handleResearch}
          loading={loading}
          defaultSortKey="atr_hod"
          defaultSortDir="asc"
          flashingTickers={flashingTickers}
        />
        <GainerTable
          gainers={loading ? [] : filteredGainers.filter(g => g.rvol_15m != null && g.rvol_15m >= 2.0)}
          fullList={loading ? [] : filteredGainers}
          title="High RVOL Radar"
          emptyMessage="No high relative volume setups active right now (RVOL >= 2.0)."
          onOpenModal={setModalGainer}
          handleResearch={handleResearch}
          loading={loading}
          defaultSortKey="rvol"
          defaultSortDir="desc"
          flashingTickers={flashingTickers}
        />
      </div>

      {/* Footer — last DB ingest */}
      <div className="pt-2 border-t border-gray-800/60">
        <LastIngestRow initialSummary={initialSummary} />
      </div>

      {/* Details modal overlay */}
      {modalGainer && (
        <LiveGainersModal
          gainer={modalGainer}
          watchlist={watchlist}
          onClose={() => setModalGainer(null)}
          onToggleWatch={handleToggleWatchlist}
          onSaveNotes={handleSaveNotes}
          watchlistLoading={watchlistLoading}
        />
      )}

      {/* Toast notifications stack */}
      <ToastStack
        toasts={toasts}
        onDismiss={dismissToast}
      />
    </div>
  )
}

// ── Last DB ingest sub-row ─────────────────────────────────────────────────────

function LastIngestRow({ initialSummary = null }: { initialSummary?: { date: string | null; total: number } | null }) {
  const [summary, setSummary] = useState<{ date: string | null; total: number } | null>(initialSummary)

  useEffect(() => {
    if (!initialSummary) {
      getGainersSummary()
        .then(s => setSummary({ date: s.date, total: s.total }))
        .catch(() => {})
    }
  }, [initialSummary])

  if (!summary?.date) return null

  const dateLabel = new Date(summary.date + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
  })

  return (
    <div className="flex items-center justify-between text-[11px] text-gray-600">
      <span>
        Last ingested: <span className="text-gray-500">{dateLabel}</span>
        <span className="ml-2 text-gray-700">({summary.total} tickers)</span>
      </span>
      <a href="/history" className="hover:text-emerald-400 transition-colors">
        Command Center →
      </a>
    </div>
  )
}
