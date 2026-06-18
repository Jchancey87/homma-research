'use client'

import { Info } from 'lucide-react'

// ── Session badge ────────────────────────────────────────────────────────────

const SESSION_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  pre_market:   { bg: 'bg-sky-500/15',     text: 'text-sky-300',     dot: 'bg-sky-400' },
  open:         { bg: 'bg-emerald-500/15', text: 'text-emerald-400', dot: 'bg-emerald-400' },
  after_hours:  { bg: 'bg-violet-500/15',  text: 'text-violet-300',  dot: 'bg-violet-400' },
  closed:       { bg: 'bg-gray-700/40',    text: 'text-gray-500',    dot: 'bg-gray-600' },
}

export function SessionBadge({ session, label }: { session: string; label: string }) {
  const s = SESSION_STYLES[session] ?? SESSION_STYLES.closed
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${session === 'open' ? 'animate-pulse' : ''}`} />
      {label}
    </span>
  )
}

// ── Price change cell ───────────────────────────────────────────────────────

export function GapCell({ gap }: { gap: number }) {
  const color = gap >= 50 ? 'text-amber-400' : gap >= 20 ? 'text-emerald-400' : 'text-emerald-300'
  return (
    <td className="py-2.5 pr-4 text-right font-mono">
      <span className={`font-bold ${color}`}>+{gap.toFixed(1)}%</span>
    </td>
  )
}

// ── Price cell ──────────────────────────────────────────────────────────────

export function PriceCell({ last, prev }: { last: number | null; prev: number | null }) {
  if (last == null) return <td className="py-2.5 pr-4 text-right font-mono text-gray-500">—</td>
  const up = prev == null || last >= prev
  return (
    <td className={`py-2.5 pr-4 text-right font-mono text-sm ${up ? 'text-white font-semibold' : 'text-red-400'}`}>
      ${last.toFixed(2)}
    </td>
  )
}

// ── Tooltip-style label ─────────────────────────────────────────────────────

export function MetricLabelWithTooltip({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <div className="flex items-center gap-1.5 text-gray-500 group/tooltip relative select-none">
      <span>{label}</span>
      <Info size={11} className="text-gray-650 hover:text-gray-400 cursor-help shrink-0" />
      <div className="pointer-events-none absolute bottom-full left-0 mb-2 hidden group-hover/tooltip:block bg-gray-950 border border-gray-800 text-white text-[10px] font-medium py-1.5 px-2.5 rounded-lg shadow-2xl w-60 leading-relaxed z-50 normal-case font-sans">
        {tooltip}
        <span className="absolute top-full left-3 border-4 border-transparent border-t-gray-950" />
      </div>
    </div>
  )
}

// ── Loading skeleton rows ───────────────────────────────────────────────────

export function SkeletonRows({ cols = 6 }: { cols?: number }) {
  return (
    <>
      {Array.from({ length: 10 }).map((_, i) => (
        <tr key={i} className="animate-pulse">
          {Array.from({ length: cols }).map((_, j) => (
            <td key={j} className="py-3 pr-4">
              <div className={`h-3 bg-gray-850 rounded ${j === 0 && cols === 6 ? 'w-8' : j === 1 ? 'w-16' : 'w-12'}`} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}
