'use client'

import { Info } from 'lucide-react'

// ── Session badge ────────────────────────────────────────────────────────────

const SESSION_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  pre_market:   { bg: 'bg-info-custom/10 border border-info-custom/25',     text: 'text-info-custom',     dot: 'bg-info-custom' },
  open:         { bg: 'bg-green-custom/10 border border-green-custom/25', text: 'text-green-custom', dot: 'bg-green-custom' },
  after_hours:  { bg: 'bg-info-custom/15 border border-info-custom/30',  text: 'text-info-custom',  dot: 'bg-info-custom' },
  closed:       { bg: 'bg-raised border border-border-subtle',    text: 'text-text-muted',    dot: 'bg-text-muted' },
}

export function SessionBadge({ session, label }: { session: string; label: string }) {
  const s = SESSION_STYLES[session] ?? SESSION_STYLES.closed
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold rounded-none ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${session === 'open' ? 'animate-pulse' : ''}`} />
      {label}
    </span>
  )
}

// ── Price change cell ───────────────────────────────────────────────────────

export function GapCell({ gap }: { gap: number }) {
  const color = gap >= 50 ? 'text-amber-custom' : gap >= 20 ? 'text-green-custom' : 'text-green-custom/80'
  return (
    <td className="py-2 pr-4 text-right font-mono tabular-nums">
      <span className={`font-bold text-sm ${color}`}>+{gap.toFixed(1)}%</span>
    </td>
  )
}

// ── Price cell ──────────────────────────────────────────────────────────────

export function PriceCell({ last, prev }: { last: number | null; prev: number | null }) {
  if (last == null) return <td className="py-2 pr-4 text-right font-mono text-text-muted tabular-nums">—</td>
  const up = prev == null || last >= prev
  return (
    <td className={`py-2 pr-4 text-right font-mono text-sm tabular-nums font-bold ${up ? 'text-text-primary' : 'text-red-custom'}`}>
      ${last.toFixed(2)}
    </td>
  )
}

// ── Tooltip-style label ─────────────────────────────────────────────────────

export function MetricLabelWithTooltip({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <div className="flex items-center gap-1.5 text-text-secondary group/tooltip relative select-none">
      <span>{label}</span>
      <Info size={11} className="text-text-muted hover:text-text-primary cursor-help shrink-0" />
      <div className="pointer-events-none absolute bottom-full left-0 mb-2 hidden group-hover/tooltip:block bg-panel border border-border-strong text-text-primary text-[10px] font-medium py-1.5 px-2.5 shadow-2xl w-60 leading-relaxed z-50 normal-case font-sans">
        {tooltip}
        <span className="absolute top-full left-3 border-4 border-transparent border-t-panel" />
      </div>
    </div>
  )
}

// ── Loading skeleton rows ───────────────────────────────────────────────────

export function SkeletonRows({ cols = 6 }: { cols?: number }) {
  return (
    <>
      {Array.from({ length: 10 }).map((_, i) => (
        <tr key={i} className="animate-pulse border-b border-border-subtle/50">
          {Array.from({ length: cols }).map((_, j) => (
              <td key={j} className="py-3 pr-4">
                <div className={`h-3 bg-hover rounded-none ${j === 0 && cols === 6 ? 'w-8' : j === 1 ? 'w-16' : 'w-12'}`} />
              </td>
          ))}
        </tr>
      ))}
    </>
  )
}
