'use client'

import { Info } from 'lucide-react'
import { fmtVol } from '@/lib/format'

// ── Session badge ────────────────────────────────────────────────────────────

const SESSION_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  pre_market:   { bg: 'bg-[#1e222a]', text: 'text-info-custom', dot: 'bg-info-custom' },
  open:         { bg: 'bg-[#1e222a]', text: 'text-green-custom', dot: 'bg-green-custom' },
  after_hours:  { bg: 'bg-[#1e222a]', text: 'text-info-custom', dot: 'bg-info-custom' },
  closed:       { bg: 'bg-[#1a1c23]', text: 'text-text-muted',  dot: 'bg-text-muted' },
}

export function SessionBadge({ session, label }: { session: string; label: string }) {
  const s = SESSION_STYLES[session] ?? SESSION_STYLES.closed
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono font-bold tracking-wider ${s.bg} ${s.text}`}>
      <span className={`w-1 h-1 rounded-full ${s.dot} ${session === 'open' ? 'animate-pulse' : ''}`} />
      {label}
    </span>
  )
}

// ── Price change cell ───────────────────────────────────────────────────────

export function GapCell({ gap }: { gap: number }) {
  const color = gap >= 0 ? 'text-green-custom' : 'text-red-custom'
  return (
    <td className="py-[3px] px-1.5 text-right font-mono tabular-nums select-none">
      <span className={`font-bold text-[12px] ${color}`}>
        {gap >= 0 ? '+' : ''}{gap.toFixed(1)}%
      </span>
    </td>
  )
}

// ── Price cell ──────────────────────────────────────────────────────────────

export function PriceCell({ last, prev }: { last: number | null; prev: number | null }) {
  if (last == null) return <td className="py-[3px] px-1.5 text-right font-mono text-text-muted text-[12px] tabular-nums select-none">—</td>
  const up = prev == null || last >= prev
  
  let rangeClass = up ? 'text-text-primary' : 'text-red-custom'
  let tooltip = ''
  let containerStyle = ''
  
  if (last >= 2.0 && last <= 10.0) {
    rangeClass = 'text-green-custom font-extrabold'
    containerStyle = 'bg-green-custom/5 px-1 py-0.25 rounded-none'
    tooltip = 'Ross Sweet Spot ($2.00 - $10.00)'
  } else if (last < 2.0) {
    rangeClass = 'text-red-custom font-extrabold animate-pulse'
    containerStyle = 'bg-red-custom/10 px-1 py-0.25 rounded-none'
    tooltip = 'Caution: Sub-$2 (Dilution & Compliance Risk)'
  }

  return (
    <td className="py-[3px] px-1.5 text-right font-mono text-[12px] tabular-nums select-none">
      <div className="inline-flex items-center justify-end w-full group/tooltip relative">
        <span className={`${rangeClass} ${containerStyle}`}>
          ${last.toFixed(2)}
        </span>
        {tooltip && (
          <div className="pointer-events-none absolute bottom-full right-0 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-subtle text-text-primary text-[10px] font-medium py-1 px-2 shadow-2xl w-48 leading-normal z-50 normal-case font-sans text-left">
            {tooltip}
            <span className="absolute top-full right-2 border-4 border-transparent border-t-panel" />
          </div>
        )}
      </div>
    </td>
  )
}

// ── Tooltip-style label ─────────────────────────────────────────────────────

export function MetricLabelWithTooltip({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <div className="flex items-center gap-1 text-text-secondary group/tooltip relative select-none">
      <span>{label}</span>
      <Info size={10} className="text-text-muted hover:text-text-primary cursor-help shrink-0" />
      <div className="pointer-events-none absolute bottom-full left-0 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-strong text-text-primary text-[10px] font-medium py-1 px-2 shadow-2xl w-56 leading-normal z-50 normal-case font-sans">
        {tooltip}
        <span className="absolute top-full left-2 border-4 border-transparent border-t-panel" />
      </div>
    </div>
  )
}

// ── Loading skeleton rows ───────────────────────────────────────────────────

export function SkeletonRows({ cols = 9 }: { cols?: number }) {
  return (
    <>
      {Array.from({ length: 12 }).map((_, i) => (
        <tr key={i} className="animate-pulse border-b border-border-subtle bg-panel/30 h-[24px]">
          {Array.from({ length: cols }).map((_, j) => (
              <td key={j} className="py-[3px] px-1.5">
                <div className={`h-3.5 bg-hover rounded-none ${j === 0 ? 'w-4' : j === 1 ? 'w-14' : 'w-10'}`} />
              </td>
          ))}
        </tr>
      ))}
    </>
  )
}

// ── Float Inline Cell (badge + tooltip without td wrapper) ─────────────────

export function FloatCellInline({ float }: { float: number | null }) {
  if (float == null) {
    const tooltip = 'WARNING: Float size currently unverified! Structural float size is unknown.'
    const colorClass = 'text-red-custom bg-red-custom/10 px-1 py-0.25 font-bold animate-pulse'
    return (
      <div className="inline-flex items-center justify-end group/tooltip relative select-none">
        <span className={`inline-flex items-center font-mono text-[10px] tabular-nums ${colorClass}`}>
          UNVERIFIED
        </span>
        <div className="pointer-events-none absolute bottom-full right-0 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-subtle text-text-primary text-[10px] font-medium py-1 px-2 shadow-2xl w-56 leading-normal z-50 normal-case font-sans text-left">
          {tooltip}
          <span className="absolute top-full right-2 border-4 border-transparent border-t-panel" />
        </div>
      </div>
    )
  }
  
  const formatted = fmtVol(float)
  let tooltip = ''
  let colorClass = ''
  
  if (float < 5_000_000) {
    tooltip = 'Micro-Float Sweet Spot (< 5M): Supply shock trigger'
    colorClass = 'text-purple-400 bg-purple-400/10 px-1 py-0.25 font-black'
  } else if (float < 10_000_000) {
    tooltip = 'Low Float (5M - 10M): Ross Target Range'
    colorClass = 'text-amber-custom bg-amber-custom/10 px-1 py-0.25 font-bold'
  } else if (float < 20_000_000) {
    tooltip = 'Medium Float (10M - 20M): Ross Target Cap'
    colorClass = 'text-green-custom bg-green-custom/10 px-1 py-0.25'
  } else if (float < 100_000_000) {
    tooltip = 'Large Float (20M - 100M): Lower squeeze sensation'
    colorClass = 'text-info-custom bg-info-custom/10 px-1 py-0.25'
  } else {
    tooltip = 'Extreme Float (> 100M): Capped squeeze potential'
    colorClass = 'text-text-muted bg-text-muted/5 px-1 py-0.25'
  }
  
  return (
    <div className="inline-flex items-center justify-end group/tooltip relative select-none">
      <span className={`inline-flex items-center font-mono text-[11px] font-bold tabular-nums ${colorClass}`}>
        {formatted}
      </span>
      <div className="pointer-events-none absolute bottom-full right-0 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-subtle text-text-primary text-[10px] font-medium py-1 px-2 shadow-2xl w-56 leading-normal z-50 normal-case font-sans text-left">
        {tooltip}
        <span className="absolute top-full right-2 border-4 border-transparent border-t-panel" />
      </div>
    </div>
  )
}

// ── Float cell with tooltip ──────────────────────────────────────────────────

export function FloatCell({ float }: { float: number | null }) {
  if (float == null) {
    const tooltip = 'WARNING: Float size currently unverified! Structural float size is unknown.'
    const colorClass = 'text-red-custom bg-red-custom/10 px-1 py-0.25 font-bold animate-pulse'
    return (
      <td className="py-[3px] px-1.5 text-right select-none font-mono">
        <div className="inline-flex items-center justify-end w-full group/tooltip relative">
          <span className={`inline-flex items-center font-mono text-[10px] tabular-nums ${colorClass}`}>
            UNVERIFIED
          </span>
          <div className="pointer-events-none absolute bottom-full right-0 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-subtle text-text-primary text-[10px] font-medium py-1 px-2 shadow-2xl w-56 leading-normal z-50 normal-case font-sans text-left">
            {tooltip}
            <span className="absolute top-full right-2 border-4 border-transparent border-t-panel" />
          </div>
        </div>
      </td>
    )
  }
  
  const formatted = fmtVol(float)
  let tooltip = ''
  let colorClass = ''
  
  if (float < 5_000_000) {
    tooltip = 'Micro-Float Sweet Spot (< 5M): Supply shock trigger'
    colorClass = 'text-purple-400 bg-purple-400/10 px-1 py-0.25 font-black'
  } else if (float < 10_000_000) {
    tooltip = 'Low Float (5M - 10M): Ross Target Range'
    colorClass = 'text-amber-custom bg-amber-custom/10 px-1 py-0.25 font-bold'
  } else if (float < 20_000_000) {
    tooltip = 'Medium Float (10M - 20M): Ross Target Cap'
    colorClass = 'text-green-custom bg-green-custom/10 px-1 py-0.25'
  } else if (float < 100_000_000) {
    tooltip = 'Large Float (20M - 100M): Lower squeeze sensation'
    colorClass = 'text-info-custom bg-info-custom/10 px-1 py-0.25'
  } else {
    tooltip = 'Extreme Float (> 100M): Capped squeeze potential'
    colorClass = 'text-text-muted bg-text-muted/5 px-1 py-0.25'
  }
  
  return (
    <td className="py-[3px] px-1.5 text-right select-none font-mono">
      <div className="inline-flex items-center justify-end w-full group/tooltip relative">
        <span className={`inline-flex items-center font-mono text-[11px] font-bold tabular-nums ${colorClass}`}>
          {formatted}
        </span>
        <div className="pointer-events-none absolute bottom-full right-0 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-subtle text-text-primary text-[10px] font-medium py-1 px-2 shadow-2xl w-56 leading-normal z-50 normal-case font-sans text-left">
          {tooltip}
          <span className="absolute top-full right-2 border-4 border-transparent border-t-panel" />
        </div>
      </div>
    </td>
  )
}
