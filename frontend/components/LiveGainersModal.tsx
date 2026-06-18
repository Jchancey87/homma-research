'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { X, Bookmark, BookmarkCheck, Sparkles, ExternalLink } from 'lucide-react'
import { LiveGainerRow, WatchlistItem } from '@/lib/api'
import { fmtVol } from '@/lib/format'
import MiniSessionChart from '@/components/MiniSessionChart'
import { getFloatBadgeStyle, getRvolBadgeStyle, getSpreadBadgeStyle } from './live-gainers/styles'

interface LiveGainersModalProps {
  gainer:        LiveGainerRow
  watchlist:     WatchlistItem[]
  onClose:       () => void
  onToggleWatch: () => Promise<void>
  onSaveNotes:   (notes: string) => Promise<void>
  watchlistLoading: boolean
}

export function LiveGainersModal({
  gainer,
  watchlist,
  onClose,
  onToggleWatch,
  onSaveNotes,
  watchlistLoading,
}: LiveGainersModalProps) {
  const router = useRouter()
  const [notesText, setNotesText] = useState('')
  const [savingNotes, setSavingNotes] = useState(false)

  useEffect(() => {
    const item = watchlist.find(w => w.ticker === gainer.ticker)
    setNotesText(item?.notes ?? '')
  }, [gainer.ticker, watchlist])

  const inWatchlist = watchlist.some(w => w.ticker === gainer.ticker)

  const handleSaveNotes = async () => {
    setSavingNotes(true)
    try {
      await onSaveNotes(notesText)
    } finally {
      setSavingNotes(false)
    }
  }

  const today = new Date().toISOString().slice(0, 10)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl bg-[#0c0c12] border border-gray-850 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[95vh] animate-in fade-in zoom-in duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800/80">
          <div className="flex items-center gap-3">
            <span className="text-xl font-bold text-white font-mono">{gainer.ticker}</span>
            <div className="flex items-center gap-1">
              {gainer.is_follow_through && (
                <span className="px-1.5 py-0.5 rounded text-[9px] font-black bg-blue-500/20 text-blue-400 border border-blue-500/30">
                  FT
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1 hover:bg-gray-800 rounded-lg transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Interactive Chart */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1 select-none">
                <Sparkles size={12} className="text-emerald-400" />
                Interactive Session Chart
              </h4>
              <span className="text-[10px] text-gray-500 select-none">Drag to scroll · Scroll to zoom</span>
            </div>
            <div className="min-h-[250px]">
              <MiniSessionChart
                ticker={gainer.ticker}
                date={today}
                gapPct={gainer.gap_pct}
                float={gainer.float_shares}
                rvol={gainer.rvol_15m}
                onExpand={(ticker) => {
                  router.push(`/research?ticker=${ticker}&date=${today}`)
                  onClose()
                }}
              />
            </div>
          </div>

          {/* Watchlist & Notes Section */}
          <div className="p-4 rounded-xl bg-gray-900/35 border border-gray-850 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 select-none">
                <h4 className="text-sm font-semibold text-white">Watchlist Quick Access</h4>
                {watchlistLoading && <span className="text-xs text-gray-500 animate-pulse">Syncing...</span>}
              </div>

              <button
                onClick={onToggleWatch}
                disabled={watchlistLoading}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                  inWatchlist
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/30 hover:bg-amber-500/20'
                    : 'bg-gray-800 text-gray-300 border-gray-700 hover:bg-gray-750 hover:text-white'
                }`}
              >
                {inWatchlist ? (
                  <>
                    <BookmarkCheck size={13} className="text-amber-400" />
                    In Watchlist
                  </>
                ) : (
                  <>
                    <Bookmark size={13} />
                    Add to Watchlist
                  </>
                )}
              </button>
            </div>

            {inWatchlist && (
              <div className="space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
                <label className="text-xs font-medium text-gray-400 block select-none">Watchlist Notes</label>
                <textarea
                  value={notesText}
                  onChange={(e) => setNotesText(e.target.value)}
                  placeholder="Type watchlist notes for this runner..."
                  className="w-full h-24 bg-[#08080c] border border-gray-800/80 rounded-lg p-2.5 text-xs text-white focus:outline-none focus:border-emerald-500/50 resize-none font-sans"
                />
                <div className="flex justify-end select-none">
                  <button
                    onClick={handleSaveNotes}
                    disabled={savingNotes}
                    className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-600/50 text-white font-semibold text-xs rounded-md shadow transition-colors flex items-center gap-1"
                  >
                    {savingNotes ? 'Saving...' : 'Save Notes'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Full Details Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono text-xs">
            <DetailCard label="Price">
              <span className="text-sm font-bold text-white">${gainer.last_price?.toFixed(2) ?? '—'}</span>
            </DetailCard>
            <DetailCard label="Change %">
              <span className={`text-sm font-bold ${gainer.gap_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                +{gainer.gap_pct?.toFixed(1)}%
              </span>
            </DetailCard>
            <DetailCard label="Float Shares">
              <span className={`whitespace-nowrap text-[10px] font-bold ${getFloatBadgeStyle(gainer.float_shares).className}`}>
                {getFloatBadgeStyle(gainer.float_shares).label}
              </span>
            </DetailCard>
            <DetailCard label="RVOL (15m)">
              <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] ${getRvolBadgeStyle(gainer.rvol_15m).className}`}>
                {getRvolBadgeStyle(gainer.rvol_15m).label}
              </span>
            </DetailCard>
            <DetailCard label="Volume">
              <span className="text-sm font-bold text-white">{fmtVol(gainer.volume)}</span>
            </DetailCard>
            <DetailCard label="Spread %">
              <span className={getSpreadBadgeStyle(gainer.spread_pct).className}>
                {getSpreadBadgeStyle(gainer.spread_pct).label}
              </span>
            </DetailCard>
            <DetailCard label="Sector">
              <span className="text-xs text-white truncate block">{gainer.sector ?? '—'}</span>
            </DetailCard>
            <DetailCard label="Last Trade">
              <span className="text-xs text-white block">
                {gainer.trade_time
                  ? new Date(gainer.trade_time).toLocaleTimeString('en-US', {
                      timeZone: 'America/New_York',
                      hour12: false,
                    })
                  : '—'} EST
              </span>
            </DetailCard>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-gray-950 border-t border-gray-850/80 flex justify-between items-center select-none">
          <span className="text-[10px] text-gray-650">ID: {gainer.ticker}</span>
          <button
            onClick={() => {
              router.push(`/research?ticker=${gainer.ticker}&date=${today}`)
              onClose()
            }}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg shadow-md transition-colors"
          >
            <ExternalLink size={12} />
            Go to Research Page
          </button>
        </div>
      </div>
    </div>
  )
}

function DetailCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="p-3 bg-gray-900/15 border border-gray-850 rounded-xl space-y-1">
      <span className="text-gray-500 block text-[10px] uppercase tracking-wider font-sans font-semibold">{label}</span>
      {children}
    </div>
  )
}
