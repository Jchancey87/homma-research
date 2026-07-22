'use client'

import React, { useEffect, useState, useRef, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useSharedWebSocket } from './live-gainers/useAlertStream'
import { getAlertsDailySummary } from '@/lib/api'
import { fmtVol } from '@/lib/format'
import {
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Filter,
  Loader2,
  Maximize2,
  Pause,
  Play,
  Volume2,
  VolumeX,
  Wifi,
  WifiOff,
} from 'lucide-react'

// Alert type metadata for color coding
const ALERT_TYPE_META: Record<
  string,
  { bg: string; text: string; border: string; label: string; emoji: string }
> = {
  NEAR_HOD_RADAR: {
    bg: 'bg-[#F23645]/15',
    text: 'text-[#F23645]',
    border: 'border-[#F23645]/40',
    label: 'HOD RADAR',
    emoji: '🎯',
  },
  VOLUME_SPIKE: {
    bg: 'bg-[#2979FF]/15',
    text: 'text-[#2979FF]',
    border: 'border-[#2979FF]/40',
    label: 'VOL SPIKE',
    emoji: '📊',
  },
  PREV_DAY_BREAKOUT: {
    bg: 'bg-[#089981]/15',
    text: 'text-[#089981]',
    border: 'border-[#089981]/40',
    label: 'PDH BREAKOUT',
    emoji: '🚀',
  },
  VOLATILITY_HALT: {
    bg: 'bg-[#F23645]/20',
    text: 'text-[#F23645]',
    border: 'border-[#F23645]/60',
    label: 'VOL HALT',
    emoji: '🛑',
  },
  VOLATILITY_RESUME: {
    bg: 'bg-[#089981]/20',
    text: 'text-[#089981]',
    border: 'border-[#089981]/60',
    label: 'VOL RESUME',
    emoji: '▶️',
  },
  VWAP_CROSSOVER: {
    bg: 'bg-[#F59E0B]/15',
    text: 'text-[#F59E0B]',
    border: 'border-[#F59E0B]/40',
    label: 'VWAP CROSS',
    emoji: '📈',
  },
  VWAP_BOUNCE: {
    bg: 'bg-[#F59E0B]/15',
    text: 'text-[#F59E0B]',
    border: 'border-[#F59E0B]/40',
    label: 'VWAP BOUNCE',
    emoji: '↩️',
  },
  RUNNING_UP: {
    bg: 'bg-[#089981]/15',
    text: 'text-[#089981]',
    border: 'border-[#089981]/40',
    label: 'RUNNING UP',
    emoji: '🏃',
  },
  BULL_FLAG: {
    bg: 'bg-[#2979FF]/15',
    text: 'text-[#2979FF]',
    border: 'border-[#2979FF]/40',
    label: 'BULL FLAG',
    emoji: '🏳️',
  },
  MULTI_TF_CONFLUENCE: {
    bg: 'bg-[#A855F7]/15',
    text: 'text-[#A855F7]',
    border: 'border-[#A855F7]/40',
    label: 'MTF CONFLUENCE',
    emoji: '🔀',
  },
  HALT_RESUME_MOMENTUM: {
    bg: 'bg-[#F59E0B]/20',
    text: 'text-[#F59E0B]',
    border: 'border-[#F59E0B]/60',
    label: 'HALT MOMENTUM',
    emoji: '⚡',
  },
}

function getAlertMeta(type: string) {
  return (
    ALERT_TYPE_META[type] ?? {
      bg: 'bg-[#181C28]',
      text: 'text-[#9B9EAE]',
      border: 'border-[#1E222D]',
      label: type.replace(/_/g, ' '),
      emoji: '🔔',
    }
  )
}

export interface AlertStreamItem {
  id: number
  symbol: string
  alert_type: string
  trigger_price: number
  rel_vol: number
  gap_pct?: number | null
  float_shares?: number | null
  float_category?: string | null
  vwap_dist_pct?: number | null
  hod_dist_pct?: number | null
  stop_price?: number | null
  stop_risk_pct?: number | null
  alert_time: string
  priority_tier: string
  priority_score?: number | null
  catalyst: string | null
}

export default function AlertStream() {
  const router = useRouter()
  const [alerts, setAlerts] = useState<AlertStreamItem[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const [newAlertIds, setNewAlertIds] = useState<Set<number>>(new Set())
  const [tierFilter, setTierFilter] = useState<'ALL' | 'Tier 1' | 'Tier 2' | 'Tier 3'>('ALL')
  const [searchTerm, setSearchTerm] = useState('')
  const [isPaused, setIsPaused] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const { connected: wsConnected, subscribe } = useSharedWebSocket()

  const prevAlertIdsRef = useRef<Set<number>>(new Set())
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const alertIdCounterRef = useRef<number>(1000000)
  const timeoutsRef = useRef<NodeJS.Timeout[]>([])

  const safeTimeout = useCallback((fn: () => void, delay: number) => {
    const id = setTimeout(() => {
      timeoutsRef.current = timeoutsRef.current.filter((t) => t !== id)
      fn()
    }, delay)
    timeoutsRef.current.push(id)
    return id
  }, [])

  // Process incoming raw alert object
  const processAlert = useCallback(
    (alertData: Record<string, unknown>) => {
      if (isPaused) return

      const id = (alertData.id as number) || (alertData.alert_db_id as number) || alertIdCounterRef.current++

      const newAlert: AlertStreamItem = {
        id,
        symbol: (alertData.symbol as string) || (alertData.ticker as string) || 'UNKNOWN',
        alert_type: (alertData.alert_type as string) || (alertData.alertType as string) || 'UNKNOWN',
        trigger_price: Number(alertData.price ?? alertData.trigger_price ?? 0),
        rel_vol: Number(alertData.rvol ?? alertData.rel_vol ?? 0),
        gap_pct: alertData.gap_pct != null ? Number(alertData.gap_pct) : (alertData.gapPct != null ? Number(alertData.gapPct) : null),
        float_shares: alertData.float_shares != null ? Number(alertData.float_shares) : (alertData.floatShares != null ? Number(alertData.floatShares) : null),
        float_category: (alertData.float_category as string) || null,
        vwap_dist_pct: alertData.vwap_dist_pct != null ? Number(alertData.vwap_dist_pct) : null,
        hod_dist_pct: alertData.hod_dist_pct != null ? Number(alertData.hod_dist_pct) : null,
        stop_price: alertData.stop_price != null ? Number(alertData.stop_price) : null,
        stop_risk_pct: alertData.stop_risk_pct != null ? Number(alertData.stop_risk_pct) : null,
        alert_time: (alertData.time as string) || (alertData.alert_time as string) || new Date().toISOString(),
        priority_tier: (alertData.priority_tier as string) || (alertData.priorityTier as string) || 'Tier 3',
        priority_score: alertData.priority_score != null ? Number(alertData.priority_score) : null,
        catalyst: (alertData.catalyst as string) || null,
      }

      setAlerts((prev) => {
        if (
          prev.some(
            (a) =>
              a.symbol === newAlert.symbol &&
              a.alert_type === newAlert.alert_type &&
              Math.abs(new Date(a.alert_time).getTime() - new Date(newAlert.alert_time).getTime()) < 3000
          )
        ) {
          return prev
        }
        return [newAlert, ...prev].slice(0, 30)
      })

      setNewAlertIds((prev) => {
        const next = new Set(Array.from(prev))
        next.add(id)
        return next
      })

      safeTimeout(() => {
        setNewAlertIds((prev) => {
          const next = new Set(Array.from(prev))
          next.delete(id)
          return next
        })
      }, 2500)

      setLastUpdate(new Date())
    },
    [isPaused, safeTimeout]
  )

  // Fetch initial alerts via REST API
  const fetchInitialAlerts = useCallback(async () => {
    try {
      const now = new Date()
      const etDate = now.toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
      const summary = await getAlertsDailySummary(etDate)

      const allAlerts: AlertStreamItem[] = []
      for (const ticker of summary.tickers) {
        for (const alert of ticker.alerts) {
          allAlerts.push({
            id: alert.id,
            symbol: ticker.symbol,
            alert_type: alert.alert_type,
            trigger_price: alert.trigger_price,
            rel_vol: alert.rel_vol ?? ticker.rvol ?? 0,
            gap_pct: ticker.gap_pct ?? null,
            float_shares: ticker.float_shares ?? null,
            float_category: ticker.float_category ?? null,
            vwap_dist_pct: alert.vwap_dist_pct ?? null,
            hod_dist_pct: alert.hod_dist_pct ?? null,
            stop_price: alert.stop_price ?? null,
            stop_risk_pct: alert.stop_risk_pct ?? null,
            alert_time: alert.alert_time,
            priority_tier: alert.priority_tier ?? 'Tier 3',
            priority_score: alert.priority_score ?? null,
            catalyst: alert.catalyst ?? null,
          })
        }
      }

      allAlerts.sort((a, b) => new Date(b.alert_time).getTime() - new Date(a.alert_time).getTime())
      setAlerts(allAlerts.slice(0, 30))
      prevAlertIdsRef.current = new Set(allAlerts.map((a) => a.id))
      setLastUpdate(new Date())
    } catch (err) {
      console.error('Failed to fetch initial alerts:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Polling fallback
  const startPolling = useCallback(() => {
    if (pollIntervalRef.current) return

    pollIntervalRef.current = setInterval(async () => {
      if (isPaused) return
      try {
        const now = new Date()
        const etDate = now.toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
        const summary = await getAlertsDailySummary(etDate)

        const allAlerts: AlertStreamItem[] = []
        for (const ticker of summary.tickers) {
          for (const alert of ticker.alerts) {
            allAlerts.push({
              id: alert.id,
              symbol: ticker.symbol,
              alert_type: alert.alert_type,
              trigger_price: alert.trigger_price,
              rel_vol: alert.rel_vol ?? ticker.rvol ?? 0,
              gap_pct: ticker.gap_pct ?? null,
              float_shares: ticker.float_shares ?? null,
              float_category: ticker.float_category ?? null,
              vwap_dist_pct: alert.vwap_dist_pct ?? null,
              hod_dist_pct: alert.hod_dist_pct ?? null,
              stop_price: alert.stop_price ?? null,
              stop_risk_pct: alert.stop_risk_pct ?? null,
              alert_time: alert.alert_time,
              priority_tier: alert.priority_tier ?? 'Tier 3',
              priority_score: alert.priority_score ?? null,
              catalyst: alert.catalyst ?? null,
            })
          }
        }

        allAlerts.sort((a, b) => new Date(b.alert_time).getTime() - new Date(a.alert_time).getTime())
        const recentAlerts = allAlerts.slice(0, 30)

        const currentIds = new Set(recentAlerts.map((a) => a.id))
        const newIds = new Set<number>()

        Array.from(currentIds).forEach((id) => {
          if (!prevAlertIdsRef.current.has(id)) {
            newIds.add(id)
          }
        })

        prevAlertIdsRef.current = currentIds

        if (newIds.size > 0) {
          setNewAlertIds(newIds)
          safeTimeout(() => setNewAlertIds(new Set()), 2500)
        }

        setAlerts(recentAlerts)
        setLastUpdate(new Date())
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 5000)
  }, [isPaused, safeTimeout])

  // Shared WebSocket subscription
  useEffect(() => {
    const unsubscribe = subscribe((data) => {
      if (data.type !== 'pong' && data.type !== 'ping' && data.type !== 'price' && data.symbol) {
        processAlert(data)
      }
    })
    return () => {
      unsubscribe()
    }
  }, [subscribe, processAlert])

  useEffect(() => {
    if (!wsConnected) {
      startPolling()
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
    }
  }, [wsConnected, startPolling])

  useEffect(() => {
    fetchInitialAlerts()

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
      timeoutsRef.current.forEach(clearTimeout)
      timeoutsRef.current = []
    }
  }, [fetchInitialAlerts])

  const formatTime = (timeStr: string) => {
    const date = new Date(timeStr)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZone: 'America/New_York',
    })
  }

  const getTimeAgo = (timeStr: string) => {
    const now = new Date()
    const alertTime = new Date(timeStr)
    const diffSec = Math.floor((now.getTime() - alertTime.getTime()) / 1000)
    if (diffSec < 60) return `${Math.max(0, diffSec)}s ago`
    const diffMin = Math.floor(diffSec / 60)
    if (diffMin < 60) return `${diffMin}m ago`
    return formatTime(timeStr)
  }

  const filteredAlerts = alerts
    .filter((a) => (tierFilter === 'ALL' ? true : a.priority_tier === tierFilter))
    .filter((a) =>
      searchTerm === ''
        ? true
        : a.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
          a.alert_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
          (a.catalyst && a.catalyst.toLowerCase().includes(searchTerm.toLowerCase()))
    )

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 bg-[#0D0E12] border border-[#1E222D]">
        <Loader2 className="text-[#089981] animate-spin" size={20} />
        <span className="ml-2 font-mono text-xs text-[#9B9EAE]">Loading Real-Time Alert Stream...</span>
      </div>
    )
  }

  return (
    <div className="w-full bg-[#0D0E12] text-[#E0E3EB] border border-[#1E222D] shadow-2xl font-sans">
      {/* Bloomberg Terminal Top Controls Header */}
      <div className="flex flex-wrap items-center justify-between px-3 py-1.5 bg-[#131722] border-b border-[#1E222D] gap-2">
        {/* Left: Stream Status Beacon */}
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                wsConnected ? 'bg-[#089981]' : 'bg-[#F59E0B]'
              }`}
            ></span>
            <span
              className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                wsConnected ? 'bg-[#089981]' : 'bg-[#F59E0B]'
              }`}
            ></span>
          </span>
          <span className="font-ticker text-xs text-[#FFFFFF] tracking-wider font-bold">
            LIVE ALERT STREAM <span className="text-[#089981] font-mono text-[11px]">[WEBSOCKET]</span>
          </span>
          <span
            className={`flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-mono border ${
              wsConnected
                ? 'bg-[#089981]/15 text-[#089981] border-[#089981]/30 font-bold'
                : 'bg-[#F59E0B]/15 text-[#F59E0B] border-[#F59E0B]/30'
            }`}
          >
            {wsConnected ? <Wifi size={9} /> : <WifiOff size={9} />}
            {wsConnected ? 'LIVE' : 'POLLING'}
          </span>
        </div>

        {/* Center: Tier Filter Tabs */}
        <div className="flex items-center bg-[#0D0E12] border border-[#1E222D] text-[10px] font-mono">
          <button
            onClick={() => setTierFilter('ALL')}
            className={`px-2 py-0.5 uppercase font-bold transition-colors ${
              tierFilter === 'ALL' ? 'bg-[#1E2433] text-[#FFFFFF]' : 'text-[#9B9EAE] hover:text-[#FFFFFF]'
            }`}
          >
            ALL ({alerts.length})
          </button>
          <button
            onClick={() => setTierFilter('Tier 1')}
            className={`px-2 py-0.5 uppercase font-bold border-l border-[#1E222D] transition-colors ${
              tierFilter === 'Tier 1'
                ? 'bg-[#F23645]/20 text-[#F23645]'
                : 'text-[#9B9EAE] hover:text-[#F23645]'
            }`}
          >
            T1 ({alerts.filter((a) => a.priority_tier === 'Tier 1').length})
          </button>
          <button
            onClick={() => setTierFilter('Tier 2')}
            className={`px-2 py-0.5 uppercase font-bold border-l border-[#1E222D] transition-colors ${
              tierFilter === 'Tier 2'
                ? 'bg-[#F59E0B]/20 text-[#F59E0B]'
                : 'text-[#9B9EAE] hover:text-[#F59E0B]'
            }`}
          >
            T2 ({alerts.filter((a) => a.priority_tier === 'Tier 2').length})
          </button>
          <button
            onClick={() => setTierFilter('Tier 3')}
            className={`px-2 py-0.5 uppercase font-bold border-l border-[#1E222D] transition-colors ${
              tierFilter === 'Tier 3' ? 'bg-[#1E2433] text-[#FFFFFF]' : 'text-[#9B9EAE] hover:text-[#FFFFFF]'
            }`}
          >
            T3 ({alerts.filter((a) => a.priority_tier === 'Tier 3').length})
          </button>
        </div>

        {/* Right: Controls & Search */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <div className="flex items-center bg-[#0D0E12] border border-[#1E222D] px-2 py-0.5">
            <Filter className="w-3 h-3 text-[#505668] mr-1" />
            <input
              type="text"
              placeholder="SEARCH ALERTS..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-transparent text-[#E0E3EB] placeholder-[#505668] focus:outline-none w-24 uppercase text-[10px]"
            />
          </div>

          <button
            onClick={() => setIsPaused(!isPaused)}
            title={isPaused ? 'Resume live feed' : 'Pause live feed'}
            className={`flex items-center gap-1 px-2 py-0.5 border text-[10px] font-bold uppercase transition-colors ${
              isPaused
                ? 'bg-[#F59E0B]/20 text-[#F59E0B] border-[#F59E0B]/40'
                : 'bg-[#181C28] text-[#9B9EAE] border-[#1E222D] hover:text-[#FFFFFF]'
            }`}
          >
            {isPaused ? <Play size={10} /> : <Pause size={10} />}
            {isPaused ? 'PAUSED' : 'LIVE'}
          </button>

          <button
            onClick={() => setIsMuted(!isMuted)}
            title={isMuted ? 'Unmute audio chimes' : 'Mute audio chimes'}
            className={`p-1 border text-[10px] transition-colors ${
              isMuted
                ? 'bg-[#F23645]/20 text-[#F23645] border-[#F23645]/40'
                : 'bg-[#181C28] text-[#9B9EAE] border-[#1E222D] hover:text-[#FFFFFF]'
            }`}
          >
            {isMuted ? <VolumeX size={11} /> : <Volume2 size={11} />}
          </button>
        </div>
      </div>

      {/* Main Alert Feed Table */}
      <div className="max-h-[360px] overflow-y-auto overflow-x-auto scrollbar-thin">
        {filteredAlerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 gap-2 text-[#505668] font-mono">
            <AlertCircle size={22} className="text-[#F59E0B]" />
            <p className="text-xs uppercase tracking-wider font-bold">No Active Stream Alerts Match Filter</p>
            <p className="text-[10px] text-[#505668]">
              Alerts will appear in real time when momentum triggers fire
            </p>
          </div>
        ) : (
          <table className="w-full border-collapse text-xs font-mono select-none">
            <thead>
              <tr className="bg-[#131722] text-[#9B9EAE] border-b border-[#1E222D] text-[10px] font-sans uppercase tracking-wider">
                <th className="text-left px-2 py-1 w-16">Time</th>
                <th className="text-left px-2 py-1 w-10">Tier</th>
                <th className="text-left px-2 py-1 w-28">Alert Signal</th>
                <th className="text-left px-2 py-1 w-20">Ticker</th>
                <th className="text-right px-2 py-1 w-20">Price</th>
                <th className="text-right px-2 py-1 w-20">Gap (%)</th>
                <th className="text-right px-2 py-1 w-20">RVOL</th>
                <th className="text-right px-2 py-1 w-24">Float</th>
                <th className="text-left px-2 py-1">Catalyst / Level Context</th>
                <th className="text-center px-2 py-1 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {filteredAlerts.map((alert) => {
                const meta = getAlertMeta(alert.alert_type)
                const isNew = newAlertIds.has(alert.id)
                const isExpanded = expandedId === alert.id

                return (
                  <React.Fragment key={alert.id}>
                    <tr
                      onClick={() => setExpandedId(isExpanded ? null : alert.id)}
                      className={`border-b border-[#1E222D] hover:bg-[#1E2433] transition-colors duration-100 cursor-pointer ${
                        isNew
                          ? 'bg-[#089981]/20 border-l-2 border-l-[#089981]'
                          : isExpanded
                          ? 'bg-[#1E2433] border-l-2 border-l-[#2979FF]'
                          : 'even:bg-[#0D0E12]/50'
                      }`}
                    >
                      {/* Time */}
                      <td className="px-2 py-[4px] text-left text-[#9B9EAE] text-[10px] font-tabular">
                        {getTimeAgo(alert.alert_time)}
                      </td>

                      {/* Tier Badge */}
                      <td className="px-2 py-[4px] text-left">
                        <span
                          className={`badge-terminal text-[9px] px-1 py-0.25 border ${
                            alert.priority_tier === 'Tier 1'
                              ? 'bg-[#F23645]/20 text-[#F23645] border-[#F23645]/40 font-bold'
                              : alert.priority_tier === 'Tier 2'
                              ? 'bg-[#F59E0B]/20 text-[#F59E0B] border-[#F59E0B]/40 font-bold'
                              : 'bg-[#181C28] text-[#9B9EAE] border-[#1E222D]'
                          }`}
                        >
                          {alert.priority_tier?.replace('Tier ', 'T') ?? 'T3'}
                        </span>
                      </td>

                      {/* Signal Badge */}
                      <td className="px-2 py-[4px] text-left">
                        <span
                          className={`badge-terminal text-[10px] px-1.5 py-0.5 border ${meta.bg} ${meta.text} ${meta.border} font-bold truncate max-w-[110px]`}
                        >
                          <span className="mr-1">{meta.emoji}</span>
                          {meta.label}
                        </span>
                      </td>

                      {/* Ticker */}
                      <td className="px-2 py-[4px] text-left">
                        <span className="font-ticker text-[13px] text-[#FFFFFF] tracking-[0.03em] font-bold group-hover:text-[#089981]">
                          {alert.symbol}
                        </span>
                      </td>

                      {/* Price */}
                      <td
                        className="px-2 py-[4px] text-right font-tabular text-[12px] text-[#FFFFFF] font-medium"
                        style={{ fontVariantNumeric: 'tabular-nums lining-nums' }}
                      >
                        ${alert.trigger_price.toFixed(2)}
                      </td>

                      {/* Gap % */}
                      <td
                        className={`px-2 py-[4px] text-right font-tabular text-[12px] font-bold ${
                          (alert.gap_pct ?? 0) >= 0 ? 'text-[#089981]' : 'text-[#F23645]'
                        }`}
                        style={{ fontVariantNumeric: 'tabular-nums lining-nums' }}
                      >
                        {alert.gap_pct != null ? (
                          <div className="flex items-center justify-end gap-0.5">
                            {alert.gap_pct >= 0 ? (
                              <ArrowUpRight className="w-3 h-3 text-[#089981]" />
                            ) : (
                              <ArrowDownRight className="w-3 h-3 text-[#F23645]" />
                            )}
                            <span>
                              {alert.gap_pct >= 0 ? `+${alert.gap_pct.toFixed(1)}%` : `${alert.gap_pct.toFixed(1)}%`}
                            </span>
                          </div>
                        ) : (
                          '—'
                        )}
                      </td>

                      {/* RVOL */}
                      <td
                        className={`px-2 py-[4px] text-right font-tabular text-[12px] ${
                          alert.rel_vol >= 5.0
                            ? 'text-[#089981] font-bold'
                            : alert.rel_vol >= 2.0
                            ? 'text-[#F59E0B] font-semibold'
                            : 'text-[#9B9EAE]'
                        }`}
                        style={{ fontVariantNumeric: 'tabular-nums lining-nums' }}
                      >
                        {alert.rel_vol > 0 ? `${alert.rel_vol.toFixed(1)}x` : '—'}
                      </td>

                      {/* Float Shares */}
                      <td
                        className={`px-2 py-[4px] text-right font-tabular text-[11px] ${
                          (alert.float_shares ?? 999999999) < 10000000
                            ? 'text-[#F59E0B] font-semibold'
                            : 'text-[#9B9EAE]'
                        }`}
                        style={{ fontVariantNumeric: 'tabular-nums lining-nums' }}
                      >
                        {alert.float_shares ? fmtVol(alert.float_shares) : '—'}
                      </td>

                      {/* Catalyst & Level Context */}
                      <td className="px-2 py-[4px] text-left font-sans text-[11px] truncate max-w-[200px]">
                        <div className="flex items-center gap-1.5">
                          {alert.catalyst && alert.catalyst !== 'Technical / No News' ? (
                            <span className="text-[#089981] bg-[#089981]/15 px-1 py-0.25 font-mono text-[9px] font-bold shrink-0">
                              ⚡ CATALYST
                            </span>
                          ) : alert.hod_dist_pct != null && Math.abs(alert.hod_dist_pct) <= 0.5 ? (
                            <span className="text-[#089981] font-mono text-[10px] font-bold shrink-0">
                              🎯 Near HOD ({alert.hod_dist_pct.toFixed(1)}%)
                            </span>
                          ) : alert.vwap_dist_pct != null ? (
                            <span className="text-[#2979FF] font-mono text-[10px] shrink-0">
                              VWAP {alert.vwap_dist_pct >= 0 ? '+' : ''}
                              {alert.vwap_dist_pct.toFixed(1)}%
                            </span>
                          ) : null}

                          <span className="text-[#9B9EAE] text-[10px] font-mono truncate">
                            {alert.catalyst ?? 'Technical Momentum'}
                          </span>
                        </div>
                      </td>

                      {/* Expand Chevron */}
                      <td className="px-2 py-[4px] text-center text-[#505668]">
                        {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      </td>
                    </tr>

                    {/* Expand Inline Micro Drawer */}
                    {isExpanded && (
                      <tr className="bg-[#181C28] border-b border-[#1E222D]">
                        <td colSpan={10} className="p-3">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
                            {/* Col 1: Execution Levels */}
                            <div className="space-y-1">
                              <h4 className="text-[10px] font-bold text-[#9B9EAE] uppercase border-b border-[#1E222D] pb-0.5">
                                Execution & Stop Levels
                              </h4>
                              <div className="flex justify-between">
                                <span className="text-[#9B9EAE]">Trigger Price:</span>
                                <span className="text-[#FFFFFF] font-bold">${alert.trigger_price.toFixed(2)}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-[#9B9EAE]">Stop Loss:</span>
                                <span className="text-[#F23645] font-bold">
                                  {alert.stop_price ? `$${alert.stop_price.toFixed(2)}` : '—'}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-[#9B9EAE]">Risk %:</span>
                                <span className="text-[#F23645]">
                                  {alert.stop_risk_pct ? `${alert.stop_risk_pct.toFixed(1)}%` : '—'}
                                </span>
                              </div>
                            </div>

                            {/* Col 2: Indicator Distances */}
                            <div className="space-y-1">
                              <h4 className="text-[10px] font-bold text-[#9B9EAE] uppercase border-b border-[#1E222D] pb-0.5">
                                Key Technical Distances
                              </h4>
                              <div className="flex justify-between">
                                <span className="text-[#9B9EAE]">Distance to HOD:</span>
                                <span
                                  className={
                                    (alert.hod_dist_pct ?? 99) <= 0.2 ? 'text-[#089981] font-bold' : 'text-[#E0E3EB]'
                                  }
                                >
                                  {alert.hod_dist_pct != null ? `${alert.hod_dist_pct.toFixed(2)}%` : '—'}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-[#9B9EAE]">VWAP Distance:</span>
                                <span className="text-[#2979FF]">
                                  {alert.vwap_dist_pct != null
                                    ? `${alert.vwap_dist_pct >= 0 ? '+' : ''}${alert.vwap_dist_pct.toFixed(2)}%`
                                    : '—'}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-[#9B9EAE]">Priority Score:</span>
                                <span className="text-[#F59E0B] font-bold">{alert.priority_score ?? '—'} pts</span>
                              </div>
                            </div>

                            {/* Col 3: Quick Action Buttons */}
                            <div className="flex flex-col justify-between gap-2">
                              <div className="space-y-0.5">
                                <span className="text-[9px] text-[#9B9EAE] font-sans block">Headline / Catalyst:</span>
                                <p className="text-[11px] text-[#E0E3EB] font-sans italic truncate">
                                  {alert.catalyst ?? 'No catalyst news logged.'}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    router.push(`/research?ticker=${alert.symbol}`)
                                  }}
                                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-[11px] font-bold text-[#FFFFFF] bg-[#089981] hover:bg-[#089981]/80 transition-colors"
                                >
                                  <ExternalLink size={11} /> Research {alert.symbol}
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    router.push(`/charts/${alert.symbol}`)
                                  }}
                                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-[11px] font-bold text-[#E0E3EB] bg-[#131722] hover:bg-[#1E2433] border border-[#1E222D] transition-colors"
                                >
                                  <Maximize2 size={11} /> Open Chart
                                </button>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Terminal Footer Navigation Bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#131722] border-t border-[#1E222D] text-[10px] font-mono text-[#9B9EAE]">
        <div className="flex items-center gap-4">
          <span>
            STREAMING: <strong className="text-[#FFFFFF]">{filteredAlerts.length} ALERTS</strong>
          </span>
          <span>
            TIER 1 CRITICAL: <strong className="text-[#F23645]">{alerts.filter((a) => a.priority_tier === 'Tier 1').length}</strong>
          </span>
          {lastUpdate && (
            <span>
              UPDATED: <strong className="text-[#FFFFFF]">{lastUpdate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</strong>
            </span>
          )}
        </div>
        <button
          onClick={() => router.push('/alerts')}
          className="text-[#089981] hover:text-[#FFFFFF] transition-colors font-bold flex items-center gap-1 uppercase"
        >
          View Full Alert Journal & Scorecard →
        </button>
      </div>
    </div>
  )
}
