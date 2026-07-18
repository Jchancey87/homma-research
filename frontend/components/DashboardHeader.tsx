'use client'

import { useEffect, useState, startTransition } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowRight, RefreshCw, Clock } from 'lucide-react'
import { getLiveGainers } from '@/lib/api'

// Helper to format ISO fetched_at string to ET time string (HH:MM:SS)
function formatTimeET(isoString: string | null): string {
  if (!isoString) return '--:--:--'
  try {
    const date = new Date(isoString)
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZone: 'America/New_York',
    })
  } catch {
    return '--:--:--'
  }
}

// Helper to format current date for the header
function getHeaderDateDetails() {
  const now = new Date()
  const dayName = now.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'America/New_York' }).toUpperCase()
  const dateStr = now.toLocaleDateString('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
    timeZone: 'America/New_York',
  }).toUpperCase()
  return { dayName, dateStr }
}

export type MarketSessionState = 'open' | 'pre_market' | 'after_hours' | 'closed'

export interface DashboardHeaderProps {
  eyebrow?: string
  title?: string
  subtitle?: string
  initialSessionState?: MarketSessionState
  initialFetchedAt?: string | null
  timezone?: string
  scopeLabel?: string
  primaryAction?: {
    label: string
    href: string
  }
  onRefresh?: () => void
}

export default function DashboardHeader({
  eyebrow = 'MARKET INTELLIGENCE',
  title = 'US Market Snapshot',
  subtitle = 'Cross-asset conditions, market health, and actionable scan context',
  initialSessionState = 'closed',
  initialFetchedAt = null,
  timezone = 'America/New_York',
  scopeLabel = 'US EQUITIES + MACRO',
  primaryAction = { label: 'Command Center →', href: '/history' },
  onRefresh,
}: DashboardHeaderProps) {
  const router = useRouter()
  const [timeDetails, setTimeDetails] = useState(() => getHeaderDateDetails())
  const [currentTimeET, setCurrentTimeET] = useState(() => {
    try {
      return new Date().toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZone: 'America/New_York',
      })
    } catch {
      return '--:--:--'
    }
  })
  const [sessionState, setSessionState] = useState<MarketSessionState>(initialSessionState)
  const [fetchedAt, setFetchedAt] = useState<string | null>(initialFetchedAt)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Handle local ticking for the current date/day and live time in Eastern Time
  useEffect(() => {
    const updateTime = () => {
      setTimeDetails(getHeaderDateDetails())
      setCurrentTimeET(new Date().toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZone: 'America/New_York',
      }))
    }
    updateTime()
    const interval = setInterval(updateTime, 1000)
    return () => clearInterval(interval)
  }, [])

  // Poll live gainers endpoint for market state and data freshness
  useEffect(() => {
    const fetchMarketState = async () => {
      try {
        const data = await getLiveGainers()
        if (data) {
          if (data.session) setSessionState(data.session)
          if (data.fetched_at) setFetchedAt(data.fetched_at)
        }
      } catch (err) {
        console.warn('DashboardHeader: failed to fetch live market state', err)
      }
    }

    fetchMarketState()
    // Poll every 10 seconds to keep market session indicator fresh
    const pollInterval = setInterval(fetchMarketState, 10000)
    return () => clearInterval(pollInterval)
  }, [])

  // Map session state to color classes and status text
  let statusText = 'MARKET CLOSED'
  let dotColorClass = 'bg-red-custom'
  let pulseAnimationClass = ''
  let statusTextColorClass = 'text-red-custom'
  let sessionDetails = 'Market Closed · Opens 9:30 AM ET'

  if (sessionState === 'open') {
    statusText = 'MARKET OPEN'
    dotColorClass = 'bg-green-custom'
    pulseAnimationClass = 'animate-pulse'
    statusTextColorClass = 'text-green-custom'
    sessionDetails = 'Regular Session · Closes 4:00 PM ET'
  } else if (sessionState === 'pre_market') {
    statusText = 'PRE-MARKET'
    dotColorClass = 'bg-amber-custom'
    pulseAnimationClass = 'animate-pulse'
    statusTextColorClass = 'text-amber-custom'
    sessionDetails = 'Pre-Market Session · Opens 9:30 AM ET'
  } else if (sessionState === 'after_hours') {
    statusText = 'AFTER-HOURS'
    dotColorClass = 'bg-amber-custom'
    pulseAnimationClass = 'animate-pulse'
    statusTextColorClass = 'text-amber-custom'
    sessionDetails = 'After-Hours Session · Closes 8:00 PM ET'
  }

  const handleRefreshClick = () => {
    setIsRefreshing(true)
    if (onRefresh) {
      onRefresh()
      // Fallback spinner timeout
      setTimeout(() => setIsRefreshing(false), 800)
    } else {
      // Standard Next.js server component refresh
      startTransition(() => {
        router.refresh()
        // Provide visual indicator for at least 800ms
        setTimeout(() => setIsRefreshing(false), 800)
      })
    }
  }

  const freshnessTime = fetchedAt ? formatTimeET(fetchedAt) : currentTimeET

  return (
    <header className="bg-panel border-b border-border-subtle px-4 py-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between w-full select-none">
      {/* LEFT: Identity and context */}
      <div className="flex flex-col min-w-0">
        <span className="text-[10px] font-mono font-bold tracking-widest text-text-muted uppercase mb-0.5">
          {eyebrow}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 border border-border-strong bg-raised text-text-secondary select-none">
            US
          </span>
          <h1 className="text-base font-bold text-text-primary uppercase tracking-tight font-mono truncate">
            {title}
          </h1>
        </div>
        <p className="text-[11px] text-text-secondary mt-1 max-w-xl font-mono leading-relaxed">
          {subtitle}
        </p>
      </div>

      {/* CENTER: Live session strip (fixed size on desktop to prevent horizontal shift) */}
      <div className="flex items-center bg-raised/50 border border-border-subtle/50 px-3 py-1.5 font-mono text-[11px] text-text-secondary self-start lg:self-center overflow-x-auto max-w-full whitespace-nowrap scrollbar-none lg:w-[480px] lg:justify-center lg:shrink-0">
        <span className="font-bold text-text-primary tracking-wider">{timeDetails.dayName}</span>
        <span className="mx-2 text-text-muted">·</span>
        <span className="tabular-nums">{timeDetails.dateStr}</span>
        <span className="mx-2 text-text-muted">·</span>
        
        {/* Status indicator */}
        <div className="flex items-center gap-1.5 mr-2">
          <span className="relative flex h-2 w-2">
            {pulseAnimationClass && (
              <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 motion-safe:${pulseAnimationClass} ${dotColorClass}`} />
            )}
            <span className={`relative inline-flex rounded-full h-2 w-2 ${dotColorClass}`} />
          </span>
          <span className={`font-bold tracking-wider ${statusTextColorClass}`}>{statusText}</span>
        </div>
        
        <span className="mx-2 text-text-muted">·</span>
        <span className="text-text-secondary truncate">{sessionDetails}</span>
        <span className="mx-2 text-text-muted">·</span>
        <div className="flex items-center gap-1">
          <Clock size={11} className="text-text-muted shrink-0" />
          <span className="tabular-nums text-text-primary">
            UPDATED {freshnessTime} ET
          </span>
        </div>
      </div>

      {/* RIGHT: Scope and actions */}
      <div className="flex items-center justify-between lg:justify-end gap-3 flex-wrap lg:flex-nowrap border-t border-border-subtle/30 pt-2 lg:border-t-0 lg:pt-0">
        {/* Scope and Timezone */}
        <div className="flex items-center gap-2 font-mono text-[10px] text-text-muted">
          <span className="px-1.5 py-0.5 border border-info-custom/20 bg-info-custom/5 text-info-custom uppercase font-semibold">
            {scopeLabel}
          </span>
          <span className="text-text-muted uppercase tabular-nums">
            {timezone}
          </span>
        </div>

        {/* Quiet visual divider */}
        <span className="hidden lg:inline text-border-subtle">|</span>

        {/* Interactive Controls */}
        <div className="flex items-center gap-2 ml-auto lg:ml-0">
          <button
            onClick={handleRefreshClick}
            disabled={isRefreshing}
            className={`p-1.5 border border-border-strong bg-raised text-text-secondary hover:bg-hover hover:text-text-primary transition-all duration-150 rounded-none disabled:opacity-50 flex items-center justify-center`}
            title="Force Refresh Data"
          >
            <RefreshCw size={12} className={`${isRefreshing ? 'animate-spin' : ''}`} />
          </button>

          {primaryAction && (
            <Link
              href={primaryAction.href}
              className="font-mono text-[11px] font-bold text-green-custom border border-green-custom/30 bg-emerald-950/10 px-3 py-1.5 flex items-center gap-1 hover:bg-green-custom hover:text-black hover:border-green-custom transition-all duration-150 rounded-none"
            >
              {primaryAction.label}
              <ArrowRight size={12} />
            </Link>
          )}
        </div>
      </div>
    </header>
  )
}
