/**
 * Shared momentum indicator styling.
 *
 * Source of truth for `mom_2m` color tiering across the dashboard
 * live-gainers table and the daily-charts mini-chart HUD.
 *
 * Tiers (TradingView-style):
 *   >=  4.0  → "exploding"  (emerald-400 fill, white text, pulse)
 *   <= -3.0  → "dumping"    (red-800 fill, white text)
 *    >  0    → bullish text (emerald-400)
 *    <  0    → bearish text (red-400)
 *   null     → muted slate
 */

export function getMomStyle(mom: number | null | undefined): string {
  if (mom == null) return 'text-slate-500'
  if (mom >= 4.0) return 'text-emerald-950 bg-emerald-400 font-extrabold shadow-sm shadow-emerald-400/50 animate-pulse px-1.5 py-0.5 rounded'
  if (mom <= -3.0) return 'text-red-100 bg-red-800 font-extrabold shadow-sm shadow-red-800/50 px-1.5 py-0.5 rounded'
  if (mom > 0) return 'text-emerald-400'
  if (mom < 0) return 'text-red-400'
  return 'text-slate-350'
}

/** Format a mom value with explicit sign and 2-decimal precision. */
export function fmtMom(mom: number | null | undefined): string {
  if (mom == null) return '—'
  return mom >= 0 ? `+${mom.toFixed(2)}%` : `${mom.toFixed(2)}%`
}
