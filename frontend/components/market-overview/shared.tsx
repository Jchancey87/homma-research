'use client'

import React from 'react'
import { RefreshCw, ChevronDown } from 'lucide-react'

export function chgColor(v: number | null) {
  if (v == null) return 'text-text-muted'
  return v > 0 ? 'text-green-custom' : v < 0 ? 'text-red-custom' : 'text-text-secondary'
}

export function chgSign(v: number | null) {
  if (v == null) return ''
  return v > 0 ? '+' : ''
}

export function fmt(v: number | null, decimals = 2): string {
  if (v == null) return '—'
  return v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export function fmtInt(v: number | null): string {
  if (v == null) return '—'
  return v.toLocaleString()
}

export const REGIME_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  risk_on:  { bg: 'bg-green-custom/15', text: 'text-green-custom', border: 'border-green-custom/30' },
  neutral:  { bg: 'bg-amber-custom/15',  text: 'text-amber-custom',  border: 'border-amber-custom/30' },
  risk_off: { bg: 'bg-red-custom/15', text: 'text-red-custom', border: 'border-red-custom/30' },
}

export const RISK_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  normal:   { bg: 'bg-info-custom/15',    text: 'text-info-custom',   border: 'border-info-custom/30' },
  elevated: { bg: 'bg-amber-custom/15',   text: 'text-amber-custom',  border: 'border-amber-custom/30' },
  high:     { bg: 'bg-red-custom/20',  text: 'text-red-custom', border: 'border-red-custom/40 font-black' },
}

export function CardHeader({
  icon: Icon,
  title,
  expanded,
  onToggle,
  showRefresh = false,
  onRefresh,
  loading = false,
}: {
  icon: React.ElementType
  title: string
  expanded: boolean
  onToggle: () => void
  showRefresh?: boolean
  onRefresh?: () => void
  loading?: boolean
}) {
  return (
    <button
      onClick={onToggle}
      className="flex items-center justify-between w-full mb-2.5 group select-none"
    >
      <span className="text-[10px] font-mono font-bold text-gray-500 uppercase tracking-widest flex items-center gap-1.5">
        <Icon size={11} className="text-gray-500" />
        {title}
      </span>
      <div className="flex items-center gap-1.5">
        {showRefresh && onRefresh && (
          <span
            role="button"
            onClick={(e) => { e.stopPropagation(); onRefresh() }}
            className="text-gray-600 hover:text-gray-400 transition-colors p-0.5"
            title="Refresh data"
          >
            <RefreshCw size={10} className={loading ? 'animate-spin' : ''} />
          </span>
        )}
        <ChevronDown
          size={10}
          className={`text-gray-600 group-hover:text-gray-400 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
        />
      </div>
    </button>
  )
}
