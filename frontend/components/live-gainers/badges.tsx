'use client'

import { Info } from 'lucide-react'
import { fmtVol } from '@/lib/format'

// ── Session badge ────────────────────────────────────────────────────────────

const SESSION_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  pre_market:   { bg: 'bg-[#1e222a] border border-[#2b323e]', text: 'text-info-custom', dot: 'bg-info-custom' },
  open:         { bg: 'bg-[#1e222a] border border-[#2b323e]', text: 'text-green-custom', dot: 'bg-green-custom' },
  after_hours:  { bg: 'bg-[#1e222a] border border-[#2b323e]', text: 'text-info-custom', dot: 'bg-info-custom' },
  closed:       { bg: 'bg-[#1a1c23] border border-[#232731]', text: 'text-text-muted',  dot: 'bg-text-muted' },
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
  return (
    <td className={`py-[3px] px-1.5 text-right font-mono text-[12px] tabular-nums font-bold select-none ${up ? 'text-text-primary' : 'text-red-custom'}`}>
      ${last.toFixed(2)}
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
        <tr key={i} className="animate-pulse border-b border-border-subtle/20 bg-panel/30 h-[24px]">
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
  if (float == null) return <span className="font-mono text-text-muted text-[11px] tabular-nums select-none">—</span>
  
  const formatted = fmtVol(float)
  let tooltip = ''
  let colorClass = ''
  
  if (float < 1_000_000) {
    tooltip = 'Small Float (< 1M): High squeeze risk'
    colorClass = 'text-red-custom bg-red-custom/10 px-1 py-0.25'
  } else if (float < 10_000_000) {
    tooltip = 'Medium Float (1M - 10M): Moderate squeeze risk'
    colorClass = 'text-amber-custom bg-amber-custom/10 px-1 py-0.25'
  } else if (float < 50_000_000) {
    tooltip = 'Normal Float (10M - 50M): Standard float'
    colorClass = 'text-green-custom bg-green-custom/10 px-1 py-0.25'
  } else {
    tooltip = 'Large Float (> 50M): Low squeeze risk'
    colorClass = 'text-info-custom bg-info-custom/10 px-1 py-0.25'
  }
  
  return (
    <div className="inline-flex items-center justify-end group/tooltip relative select-none">
      <span className={`inline-flex items-center font-mono text-[11px] font-bold tabular-nums ${colorClass}`}>
        {formatted}
      </span>
      <div className="pointer-events-none absolute bottom-full right-0 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-strong text-text-primary text-[10px] font-medium py-1 px-2 shadow-2xl w-56 leading-normal z-50 normal-case font-sans text-left">
        {tooltip}
        <span className="absolute top-full right-2 border-4 border-transparent border-t-panel" />
      </div>
    </div>
  )
}

// ── Float cell with tooltip ──────────────────────────────────────────────────

export function FloatCell({ float }: { float: number | null }) {
  if (float == null) return <td className="py-[3px] px-1.5 text-right font-mono text-text-muted text-[11px] tabular-nums select-none">—</td>
  
  const formatted = fmtVol(float)
  let tooltip = ''
  let colorClass = ''
  
  if (float < 1_000_000) {
    tooltip = 'Small Float (< 1M): High squeeze risk'
    colorClass = 'text-red-custom bg-red-custom/10 px-1 py-0.25'
  } else if (float < 10_000_000) {
    tooltip = 'Medium Float (1M - 10M): Moderate squeeze risk'
    colorClass = 'text-amber-custom bg-amber-custom/10 px-1 py-0.25'
  } else if (float < 50_000_000) {
    tooltip = 'Normal Float (10M - 50M): Standard float'
    colorClass = 'text-green-custom bg-green-custom/10 px-1 py-0.25'
  } else {
    tooltip = 'Large Float (> 50M): Low squeeze risk'
    colorClass = 'text-info-custom bg-info-custom/10 px-1 py-0.25'
  }
  
  return (
    <td className="py-[3px] px-1.5 text-right select-none font-mono">
      <div className="inline-flex items-center justify-end w-full group/tooltip relative">
        <span className={`inline-flex items-center font-mono text-[11px] font-bold tabular-nums ${colorClass}`}>
          {formatted}
        </span>
        <div className="pointer-events-none absolute bottom-full right-0 mb-1.5 hidden group-hover/tooltip:block bg-panel border border-border-strong text-text-primary text-[10px] font-medium py-1 px-2 shadow-2xl w-56 leading-normal z-50 normal-case font-sans text-left">
          {tooltip}
          <span className="absolute top-full right-2 border-4 border-transparent border-t-panel" />
        </div>
      </div>
    </td>
  )
}
