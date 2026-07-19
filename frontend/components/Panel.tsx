import Link from 'next/link'
import { ArrowRight } from 'lucide-react'

/**
 * Panel — shared dark card primitive used across the dashboard.
 *
 * A `Panel` is the gray-bordered, near-black box that frames each section of
 * the home dashboard (live screener, repeat runners, watchlist, etc.). The
 * 1:1 extraction from `app/page.tsx` preserves all original Tailwind classes
 * so the visual output is byte-identical.
 */
export function Panel({
  children, className = '',
}: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-[#0B0E13] border border-border-subtle rounded-none p-2 ${className}`}>
      {children}
    </div>
  )
}

interface PanelLabelProps {
  icon:  React.ElementType
  label: string
  href?: string
}

export function PanelLabel({ icon: Icon, label, href }: PanelLabelProps) {
  return (
    <div className="flex items-center justify-between mb-3">
      <span className="text-[11px] font-mono font-bold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
        <Icon size={12} className="text-gray-500" />
        {label}
      </span>
      {href && (
        <Link
          href={href}
          className="text-[11px] font-mono text-gray-500 hover:text-white transition-colors flex items-center gap-1"
        >
          View all <ArrowRight size={10} />
        </Link>
      )}
    </div>
  )
}
