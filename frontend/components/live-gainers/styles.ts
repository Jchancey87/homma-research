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
  if (rvol == null) return { label: '—', className: 'bg-raised text-text-muted border border-border-subtle' }
  if (rvol >= 1000) return { label: `${rvol.toFixed(1)}x (Extreme)`, className: 'bg-red-custom/15 text-red-custom border border-red-custom/30 font-bold' }
  if (rvol >= 200)  return { label: `${rvol.toFixed(1)}x (Mega)`,    className: 'bg-green-custom/20 text-green-custom border border-green-custom/45 font-bold' }
  if (rvol >= 50)   return { label: `${rvol.toFixed(1)}x (Strong)`,  className: 'bg-green-custom/15 text-green-custom border border-green-custom/30 font-semibold' }
  if (rvol >= 5)    return { label: `${rvol.toFixed(1)}x (Above Avg)`, className: 'bg-green-custom/10 text-green-custom border border-green-custom/20' }
  return { label: `${rvol.toFixed(1)}x`, className: 'bg-raised text-text-secondary border border-border-subtle' }
}

export function getRvolColor(rvol: number | null) {
  if (rvol == null) return 'text-text-muted'
  if (rvol >= 1000) return 'text-red-custom font-bold'
  if (rvol >= 200)  return 'text-green-custom font-bold'
  if (rvol >= 50)   return 'text-green-custom font-semibold'
  if (rvol >= 5)    return 'text-green-custom'
  return 'text-text-secondary'
}

// ── Float ────────────────────────────────────────────────────────────────────

export function getFloatBadgeStyle(floatShares: number | null) {
  if (floatShares == null) return { label: '—', className: 'text-text-muted' }
  const formatted = fmtVol(floatShares)
  if (floatShares < 1_000_000)   return { label: `${formatted} (Small)`,  className: 'text-red-custom bg-red-custom/10 border border-red-custom/25 px-1.5 py-0.5 font-mono text-[10px]' }
  if (floatShares < 10_000_000)  return { label: `${formatted} (Medium)`, className: 'text-amber-custom bg-amber-custom/10 border border-amber-custom/25 px-1.5 py-0.5 font-mono text-[10px]' }
  if (floatShares < 50_000_000)  return { label: `${formatted} (Normal)`, className: 'text-green-custom bg-green-custom/10 border border-green-custom/25 px-1.5 py-0.5 font-mono text-[10px]' }
  return { label: `${formatted} (Large)`, className: 'text-info-custom bg-info-custom/10 border border-info-custom/25 px-1.5 py-0.5 font-mono text-[10px]' }
}

// ── Spread ───────────────────────────────────────────────────────────────────

export function getSpreadBadgeStyle(spreadPct: number | null) {
  if (spreadPct == null) return { label: '—', className: 'text-text-muted font-mono' }
  const formatted = `${spreadPct.toFixed(2)}%`
  if (spreadPct < 1) {
    return { label: formatted, className: 'text-text-secondary font-mono' }
  }
  if (spreadPct < 3) {
    return { label: `${formatted} (Elevated)`, className: 'bg-amber-custom/10 text-amber-custom border border-amber-custom/20 px-1.5 py-0.5 text-[10px] font-mono' }
  }
  if (spreadPct < 5) {
    return { label: `${formatted} (High)`, className: 'bg-amber-custom/20 text-amber-custom border border-amber-custom/35 px-1.5 py-0.5 text-[10px] font-mono' }
  }
  return { label: `${formatted} (Extreme)`, className: 'bg-red-custom/15 text-red-custom border border-red-custom/30 px-1.5 py-0.5 text-[10px] font-bold font-mono' }
}

// ── ATR / HOD / VWAP / ZenV ─────────────────────────────────────────────────

export function getAtrHodColor(val: number | null | undefined) {
  if (val == null) return 'text-text-muted'
  if (val === 0) return 'text-green-custom font-bold underline decoration-green-custom/40'
  if (val < 0.2) return 'text-green-custom font-bold'
  if (val < 0.5) return 'text-green-custom/75 font-semibold'
  if (val < 1.0) return 'text-text-primary'
  if (val < 2.0) return 'text-text-secondary'
  return 'text-text-muted'
}

export function getAtrSpreadStyle(val: number | null | undefined) {
  if (val == null) return { text: '—', className: 'text-text-muted' }
  if (val <= 0.3) return { text: `${val.toFixed(2)} (Tight / Clean)`, className: 'text-green-custom font-bold' }
  if (val > 1.0)  return { text: `${val.toFixed(2)} (Dangerously Wide)`, className: 'text-red-custom font-bold' }
  return { text: `${val.toFixed(2)} (Moderate)`, className: 'text-text-primary' }
}

export function getAtrVwapStyle(val: number | null | undefined) {
  if (val == null) return { text: '—', className: 'text-text-muted' }
  if (val > 3.0)  return { text: `+${val.toFixed(2)} (Overextended / Long)`, className: 'text-red-custom font-bold animate-pulse' }
  if (val < -3.0) return { text: `${val.toFixed(2)} (Heavily Short-Extended)`, className: 'text-red-custom font-bold' }
  if (Math.abs(val) <= 1.0) return { text: `${val >= 0 ? '+' : ''}${val.toFixed(2)} (Mean Reversion Zone)`, className: 'text-green-custom' }
  return { text: `${val >= 0 ? '+' : ''}${val.toFixed(2)} (Extending)`, className: 'text-text-secondary' }
}

export function getZenVStyle(val: number | null | undefined) {
  if (val == null) return { text: '—', className: 'text-text-muted' }
  if (val > 0) return { text: `▲ ${val.toFixed(2)}`, className: 'text-green-custom font-bold' }
  if (val < 0) return { text: `▼ ${val.toFixed(2)}`, className: 'text-red-custom font-bold' }
  return { text: `▶ ${val.toFixed(2)}`, className: 'text-text-secondary' }
}

// ── Time-ago freshness badge ────────────────────────────────────────────────

export function getTimeAgoBadge(tradeTimeMs: number | null) {
  if (!tradeTimeMs) return null
  const seconds = Math.floor((Date.now() - tradeTimeMs) / 1000)
  if (seconds < 300)   return { label: '⚡ Fresh',  className: 'bg-info-custom/10 text-info-custom border border-info-custom/25' }
  if (seconds < 900)   return { label: '🟢 Recent', className: 'bg-green-custom/10 text-green-custom border border-green-custom/25' }
  if (seconds < 3600)  return { label: '🟡 Stale',  className: 'bg-amber-custom/10 text-amber-custom border border-amber-custom/25' }
  return { label: '🔵 Old', className: 'bg-raised text-text-muted border border-border-subtle' }
}
