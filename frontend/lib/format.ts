/**
 * Shared formatting and date utilities.
 *
 * Source of truth for number/date formatters used across the dashboard
 * (LiveGainers, MiniSessionChart, alerts page, history, gainers, etc).
 *
 * Conventions:
 *  - `fmt1(n)`:           1-decimal fixed-point, optional suffix, '—' for null.
 *  - `fmtFloat(n)`:       takes raw share count, returns "1.2M" / "3.4B".
 *  - `fmtVol(n)`:         volume formatter (K/M with locale fallback).
 *  - `addDays(s, n)`:     ISO date string + day offset, returns ISO date.
 *  - `todayET()`:         current date in America/New_York as ISO (YYYY-MM-DD).
 */

export function fmt1(n: number | null | undefined, suffix = ''): string {
  if (n == null) return '—'
  return `${n.toFixed(1)}${suffix}`
}

export function fmtFloat(n: number | null | undefined): string {
  if (n == null) return '—'
  const m = n / 1_000_000
  return m >= 1000 ? `${(m / 1000).toFixed(1)}B` : `${m.toFixed(1)}M`
}

export function fmtVol(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toLocaleString()
}

export function addDays(dateStr: string, n: number): string {
  const d = new Date(dateStr + 'T12:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().split('T')[0]
}

export function todayET(): string {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
}
