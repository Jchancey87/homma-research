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
  Volume2,
  VolumeX,
  Bell,
  BellOff,
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
const PRICE_MIN = 2.0
const PRICE_MAX = 25.0

export default function LiveGainers() {
  const router = useRouter()
  const [snap,        setSnap]        = useState<LiveGainerSnapshot | null>(null)
  const [loading,     setLoading]     = useState(true)
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
  const [watchlist, setWatchlist]     = useState<WatchlistItem[]>([])
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
    fetchData()
    fetchWatchlist()
    timerRef.current = setInterval(() => fetchData(), 15 * 1000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [fetchData, fetchWatchlist])

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
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          {snap && (
            <SessionBadge session={session} label={snap.session_label} />
          )}
          {ageStr && (
            <span className="flex items-center gap-1 text-[11px] text-gray-600">
              <Clock size={10} />
              {ageStr}
            </span>
          )}
          {isActive && !error && (
            <span className="flex items-center gap-1 text-[11px] text-gray-700">
              <Wifi size={10} className="text-emerald-600" />
              auto-refresh 1m
            </span>
          )}
          {error && (
            <span className="flex items-center gap-1 text-[11px] text-red-500">
              <WifiOff size={10} />
              {error}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 select-none">
          {/* Audio Chime Toggle */}
          <button
            onClick={() => setAudioChimesEnabled(!audioChimesEnabled)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              audioChimesEnabled
                ? 'bg-emerald-600/15 border-emerald-500/35 text-emerald-400 hover:bg-emerald-600/25'
                : 'bg-gray-900/40 border-gray-800/60 text-gray-450 hover:text-gray-300 hover:bg-gray-900/60'
            }`}
            title="Toggle Audio Chimes on Breakouts"
          >
            {audioChimesEnabled ? <Volume2 size={12} /> : <VolumeX size={12} />}
            <span>Audio</span>
          </button>

          {/* Toast Stack Toggle */}
          <button
            onClick={() => setToastStackEnabled(!toastStackEnabled)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              toastStackEnabled
                ? 'bg-emerald-600/15 border-emerald-500/35 text-emerald-400 hover:bg-emerald-600/25'
                : 'bg-gray-900/40 border-gray-800/60 text-gray-450 hover:text-gray-300 hover:bg-gray-900/60'
            }`}
            title="Toggle Toast Stack Notifications"
          >
            {toastStackEnabled ? <Bell size={12} /> : <BellOff size={12} />}
            <span>Toasts</span>
          </button>

          <button
            onClick={() => {
              const newValue = !priceFilterEnabled
              setPriceFilterEnabled(newValue)
              localStorage.setItem(PRICE_FILTER_KEY, String(newValue))
              window.dispatchEvent(new Event(PRICE_FILTER_EVENT))
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              priceFilterEnabled
                ? 'bg-emerald-600/15 border-emerald-500/35 text-emerald-400 hover:bg-emerald-600/25'
                : 'bg-gray-900/40 border-gray-800/60 text-gray-450 hover:text-gray-300 hover:bg-gray-900/60'
            }`}
          >
            <span>$2-$25 Filter</span>
            {priceFilterEnabled ? (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            ) : (
              <span className="w-1.5 h-1.5 rounded-full bg-gray-600" />
            )}
          </button>

          <button
            id="live-gainers-refresh"
            onClick={() => fetchData(true)}
            disabled={refreshing}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-emerald-400 transition-colors disabled:opacity-40"
          >
            <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* EOD persist notice */}
      {session === 'after_hours' && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-xs text-violet-300">
          <TrendingUp size={12} className="shrink-0" />
          These gainers will be automatically saved to your database at 8:00 PM ET.
        </div>
      )}

      {/* Side-by-Side Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GainerTable
          gainers={loading ? [] : filteredGainers}
          fullList={loading ? [] : filteredGainers}
          title="All Live Gainers"
          showRank={true}
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
          showRank={false}
          emptyMessage="No Near HOD breakout setups coiling right now (AtrHoD < 1.0)."
          onOpenModal={setModalGainer}
          handleResearch={handleResearch}
          loading={loading}
          defaultSortKey="atr_hod"
          defaultSortDir="asc"
          flashingTickers={flashingTickers}
        />
      </div>

      {/* Footer — last DB ingest */}
      <div className="pt-2 border-t border-gray-800/60">
        <LastIngestRow />
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

function LastIngestRow() {
  const [summary, setSummary] = useState<{ date: string | null; total: number } | null>(null)

  useEffect(() => {
    getGainersSummary()
      .then(s => setSummary({ date: s.date, total: s.total }))
      .catch(() => {})
  }, [])

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
