/**
 * Pure badge/indicator style functions for the live-gainers table.
 *
 * Source of truth for RVOL / float / spread / ATR / ZenV colour tiering
 * used in the table rows, expand panels, and detail modal. Kept
 * dependency-free (no JSX, no React imports) so each function is unit
 * testable in isolation.
 */

import { fmtVol } from '@/lib/format'

// ── RVOL ─────────────────────────────────────────────────────────────────────

export function getRvolBadgeStyle(rvol: number | null) {
  if (rvol == null) return { label: '—', className: 'bg-gray-500/10 text-gray-400 border border-gray-500/20' }
  if (rvol >= 1000) return { label: `${rvol.toFixed(1)}x (Extreme)`, className: 'bg-rose-500/20 text-rose-300 border border-rose-500/30' }
  if (rvol >= 200)  return { label: `${rvol.toFixed(1)}x (Mega)`,    className: 'bg-emerald-600/30 text-emerald-200 border border-emerald-600/40' }
  if (rvol >= 50)   return { label: `${rvol.toFixed(1)}x (Strong)`,  className: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold' }
  if (rvol >= 5)    return { label: `${rvol.toFixed(1)}x (Above Avg)`, className: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' }
  return { label: `${rvol.toFixed(1)}x`, className: 'bg-gray-500/10 text-gray-400 border border-gray-500/20' }
}

export function getRvolColor(rvol: number | null) {
  if (rvol == null) return 'text-gray-400'
  if (rvol >= 1000) return 'text-rose-300 font-bold'
  if (rvol >= 200)  return 'text-emerald-200 font-bold'
  if (rvol >= 50)   return 'text-emerald-300 font-semibold'
  if (rvol >= 5)    return 'text-emerald-400'
  return 'text-gray-400'
}

// ── Float ────────────────────────────────────────────────────────────────────

export function getFloatBadgeStyle(floatShares: number | null) {
  if (floatShares == null) return { label: '—', className: 'text-gray-400' }
  const formatted = fmtVol(floatShares)
  if (floatShares < 1_000_000)   return { label: `${formatted} (Small)`,  className: 'text-rose-300' }
  if (floatShares < 10_000_000)  return { label: `${formatted} (Medium)`, className: 'text-amber-300' }
  if (floatShares < 50_000_000)  return { label: `${formatted} (Normal)`, className: 'text-emerald-300' }
  return { label: `${formatted} (Large)`, className: 'text-blue-300' }
}

// ── Spread ───────────────────────────────────────────────────────────────────

export function getSpreadBadgeStyle(spreadPct: number | null) {
  if (spreadPct == null) return { label: '—', className: 'text-gray-400 font-mono' }
  const formatted = `${spreadPct.toFixed(2)}%`
  if (spreadPct < 1) {
    return { label: formatted, className: 'text-gray-400 font-mono' }
  }
  if (spreadPct < 3) {
    return { label: `${formatted} (Elevated)`, className: 'bg-amber-500/10 text-amber-400 border border-amber-500/20 px-1.5 py-0.5 rounded text-[10px] font-mono' }
  }
  if (spreadPct < 5) {
    return { label: `${formatted} (High)`, className: 'bg-orange-500/10 text-orange-400 border border-orange-500/20 px-1.5 py-0.5 rounded text-[10px] font-mono' }
  }
  return { label: `${formatted} (Extreme)`, className: 'bg-rose-500/20 text-rose-300 border border-rose-500/30 px-1.5 py-0.5 rounded text-[10px] font-bold font-mono' }
}

// ── ATR / HOD / VWAP / ZenV ─────────────────────────────────────────────────

export function getAtrHodColor(val: number | null | undefined) {
  if (val == null) return 'text-slate-500'
  if (val === 0) return 'text-emerald-400 font-bold underline decoration-emerald-400/40'
  if (val < 0.2) return 'text-emerald-300 font-bold'
  if (val < 0.5) return 'text-emerald-400/70 font-semibold'
  if (val < 1.0) return 'text-slate-300'
  if (val < 2.0) return 'text-slate-400'
  return 'text-slate-500'
}

export function getAtrSpreadStyle(val: number | null | undefined) {
  if (val == null) return { text: '—', className: 'text-slate-500' }
  if (val <= 0.3) return { text: `${val.toFixed(2)} (Tight / Clean)`, className: 'text-emerald-400 font-bold' }
  if (val > 1.0)  return { text: `${val.toFixed(2)} (Dangerously Wide)`, className: 'text-rose-500 font-bold' }
  return { text: `${val.toFixed(2)} (Moderate)`, className: 'text-slate-300' }
}

export function getAtrVwapStyle(val: number | null | undefined) {
  if (val == null) return { text: '—', className: 'text-slate-500' }
  if (val > 3.0)  return { text: `+${val.toFixed(2)} (Overextended / Long)`, className: 'text-fuchsia-400 font-bold animate-pulse' }
  if (val < -3.0) return { text: `${val.toFixed(2)} (Heavily Short-Extended)`, className: 'text-orange-500 font-bold' }
  if (Math.abs(val) <= 1.0) return { text: `${val >= 0 ? '+' : ''}${val.toFixed(2)} (Mean Reversion Zone)`, className: 'text-emerald-400' }
  return { text: `${val >= 0 ? '+' : ''}${val.toFixed(2)} (Extending)`, className: 'text-slate-305' }
}

export function getZenVStyle(val: number | null | undefined) {
  if (val == null) return { text: '—', className: 'text-slate-500' }
  if (val > 0) return { text: `▲ ${val.toFixed(2)}`, className: 'text-emerald-400 font-bold' }
  if (val < 0) return { text: `▼ ${val.toFixed(2)}`, className: 'text-rose-500 font-bold' }
  return { text: `▶ ${val.toFixed(2)}`, className: 'text-slate-400' }
}

// ── Time-ago freshness badge ────────────────────────────────────────────────

export function getTimeAgoBadge(tradeTimeMs: number | null) {
  if (!tradeTimeMs) return null
  const seconds = Math.floor((Date.now() - tradeTimeMs) / 1000)
  if (seconds < 300)   return { label: '⚡ Fresh',  className: 'bg-violet-500/20 text-violet-300 border border-violet-500/30' }
  if (seconds < 900)   return { label: '🟢 Recent', className: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' }
  if (seconds < 3600)  return { label: '🟡 Stale',  className: 'bg-amber-500/20 text-amber-300 border border-amber-500/30' }
  return { label: '🔵 Old', className: 'bg-sky-500/20 text-sky-300 border border-sky-500/30' }
}
