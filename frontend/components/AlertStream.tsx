'use client'
import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { getAlertsDailySummary } from '@/lib/api'
import { ChevronRight, Loader2, AlertCircle } from 'lucide-react'

// Alert type metadata for color coding
const ALERT_TYPE_META: Record<string, { bg: string; text: string; border: string; label: string; emoji: string }> = {
  'NEAR_HOD_RADAR': { bg: 'bg-pink-950/30', text: 'text-pink-400', border: 'border-pink-500/40', label: 'HOD', emoji: '🎯' },
  'VOLUME_SPIKE': { bg: 'bg-purple-950/30', text: 'text-purple-400', border: 'border-purple-500/40', label: 'VOL', emoji: '📊' },
  'PREV_DAY_BREAKOUT': { bg: 'bg-blue-950/30', text: 'text-blue-400', border: 'border-blue-500/40', label: 'BRK', emoji: '🚀' },
  'VOLATILITY_HALT': { bg: 'bg-red-950/30', text: 'text-red-400', border: 'border-red-500/40', label: 'HALT', emoji: '🛑' },
  'VOLATILITY_RESUME': { bg: 'bg-green-950/30', text: 'text-green-400', border: 'border-green-500/40', label: 'RSUM', emoji: '▶️' },
  'VWAP_CROSSOVER': { bg: 'bg-amber-950/30', text: 'text-amber-400', border: 'border-amber-500/40', label: 'VWAP', emoji: '📈' },
  'VWAP_BOUNCE': { bg: 'bg-amber-950/30', text: 'text-amber-400', border: 'border-amber-500/40', label: 'VWAP', emoji: '↩️' },
  'RUNNING_UP': { bg: 'bg-emerald-950/30', text: 'text-emerald-400', border: 'border-emerald-500/40', label: 'RUN', emoji: '🏃' },
  'BULL_FLAG': { bg: 'bg-cyan-950/30', text: 'text-cyan-400', border: 'border-cyan-500/40', label: 'FLAG', emoji: '🏳️' },
  'MULTI_TF_CONFLUENCE': { bg: 'bg-violet-950/30', text: 'text-violet-400', border: 'border-violet-500/40', label: 'MTF', emoji: '🔀' },
  'HALT_RESUME_MOMENTUM': { bg: 'bg-yellow-950/30', text: 'text-yellow-400', border: 'border-yellow-500/40', label: 'HRM', emoji: '⚡' },
}

function getAlertMeta(type: string) {
  return ALERT_TYPE_META[type] ?? { bg: 'bg-gray-950/30', text: 'text-gray-400', border: 'border-gray-500/40', label: type.slice(0, 4), emoji: '🔔' }
}

interface AlertStreamItem {
  id: number
  symbol: string
  alert_type: string
  trigger_price: number
  rel_vol: number
  alert_time: string
  priority_tier: string
  catalyst: string | null
}

export default function AlertStream() {
  const router = useRouter()
  const [alerts, setAlerts] = useState<AlertStreamItem[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const [newAlertIds, setNewAlertIds] = useState<Set<number>>(new Set())
  const prevAlertIdsRef = useRef<Set<number>>(new Set())
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const fetchAlerts = async () => {
    try {
      // Get today's date in ET
      const now = new Date()
      const etDate = now.toLocaleDateString('en-CA', { timeZone: 'America/New_York' })
      
      const summary = await getAlertsDailySummary(etDate)
      
      // Flatten all alerts from all tickers and sort by time (newest first)
      const allAlerts: AlertStreamItem[] = []
      for (const ticker of summary.tickers) {
        for (const alert of ticker.alerts) {
          allAlerts.push({
            id: alert.id,
            symbol: ticker.symbol,
            alert_type: alert.alert_type,
            trigger_price: alert.trigger_price,
            rel_vol: alert.rel_vol,
            alert_time: alert.alert_time,
            priority_tier: alert.priority_tier,
            catalyst: alert.catalyst,
          })
        }
      }
      
      // Sort by alert_time descending (newest first)
      allAlerts.sort((a, b) => new Date(b.alert_time).getTime() - new Date(a.alert_time).getTime())
      
      // Take only the most recent 20 alerts
      const recentAlerts = allAlerts.slice(0, 20)
      
      // Detect new alerts (ones we haven't seen before)
      const currentIds = new Set(recentAlerts.map(a => a.id))
      const newIds = new Set<number>()
      
      if (prevAlertIdsRef.current.size > 0) {
        Array.from(currentIds).forEach(id => {
          if (!prevAlertIdsRef.current.has(id)) {
            newIds.add(id)
          }
        })
      }
      
      prevAlertIdsRef.current = currentIds
      
      if (newIds.size > 0) {
        setNewAlertIds(newIds)
        // Clear new alert highlighting after 3 seconds
        setTimeout(() => setNewAlertIds(new Set()), 3000)
      }
      
      setAlerts(recentAlerts)
      setLastUpdate(new Date())
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAlerts()
    
    // Poll every 5 seconds for new alerts
    intervalRef.current = setInterval(fetchAlerts, 5000)
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  const formatTime = (timeStr: string) => {
    const date = new Date(timeStr)
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZone: 'America/New_York'
    })
  }

  const getTimeAgo = (timeStr: string) => {
    const now = new Date()
    const alertTime = new Date(timeStr)
    const diffMs = now.getTime() - alertTime.getTime()
    const diffSec = Math.floor(diffMs / 1000)
    const diffMin = Math.floor(diffSec / 60)
    
    if (diffSec < 60) return `${diffSec}s ago`
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    return formatTime(timeStr)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="text-[#00ff00] animate-spin" size={20} />
      </div>
    )
  }

  if (alerts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 gap-2 text-gray-600">
        <AlertCircle size={20} />
        <p className="text-[10px] font-mono uppercase tracking-wider">No alerts today</p>
        <p className="text-[9px] font-mono text-gray-700">Alerts will appear here when the streamer fires</p>
      </div>
    )
  }

  return (
    <div className="space-y-0.5">
      {/* Header with live indicator */}
      <div className="flex items-center justify-between px-2 pb-2 border-b border-[#1a1a1a] mb-2">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00ff00] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00ff00]"></span>
          </span>
          <span className="text-[10px] font-mono text-gray-500 uppercase tracking-wider">Live Feed</span>
        </div>
        {lastUpdate && (
          <span className="text-[9px] font-mono text-gray-600">
            Updated {lastUpdate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
          </span>
        )}
      </div>

      {/* Alert list */}
      <div className="max-h-[280px] overflow-y-auto space-y-0.5">
        {alerts.map((alert) => {
          const meta = getAlertMeta(alert.alert_type)
          const isNew = newAlertIds.has(alert.id)
          const isNewlyHighlighted = isNew
          
          return (
            <div
              key={alert.id}
              onClick={() => router.push(`/alerts?date=${new Date(alert.alert_time).toLocaleDateString('en-CA', { timeZone: 'America/New_York' })}`)}
              className={`group flex items-center gap-2 px-2 py-1.5 cursor-pointer transition-all rounded-none ${
                isNewlyHighlighted
                  ? 'bg-[#00ff00]/10 border border-[#00ff00]/30 animate-pulse'
                  : 'hover:bg-[#0a0a0a] border border-transparent hover:border-[#262626]'
              }`}
            >
              {/* Alert type badge */}
              <span className={`px-1 py-0.5 text-[8px] font-mono font-bold border ${meta.bg} ${meta.text} ${meta.border} rounded-none shrink-0`}>
                {meta.label}
              </span>
              
              {/* Ticker */}
              <span className="text-xs font-mono font-bold text-white group-hover:text-[#00ff00] transition-colors shrink-0 w-14">
                {alert.symbol}
              </span>
              
              {/* Price */}
              <span className="text-[10px] font-mono text-gray-400 shrink-0 w-14 text-right">
                ${alert.trigger_price.toFixed(2)}
              </span>
              
              {/* RVOL */}
              <span className="text-[10px] font-mono text-amber-400 shrink-0 w-10 text-right">
                {alert.rel_vol.toFixed(1)}x
              </span>
              
              {/* Priority tier */}
              <span className={`px-1 py-0.5 text-[8px] font-mono font-bold rounded-none shrink-0 ${
                alert.priority_tier === 'Tier 1' ? 'text-[#ff003c] border border-[#ff003c]/30 bg-red-950/20'
                : alert.priority_tier === 'Tier 2' ? 'text-amber-400 border border-amber-500/30 bg-amber-950/20'
                : 'text-gray-600 border border-[#262626]'
              }`}>
                {alert.priority_tier?.replace('Tier ', 'T') ?? 'T3'}
              </span>
              
              {/* Catalyst indicator */}
              {alert.catalyst && alert.catalyst !== 'Technical / No News' && (
                <span className="px-1 py-0.5 text-[8px] font-mono text-cyan-400 border border-cyan-500/30 bg-cyan-950/20 rounded-none shrink-0" title={alert.catalyst}>
                  ⚡
                </span>
              )}
              
              {/* Time ago */}
              <span className="text-[9px] font-mono text-gray-600 ml-auto shrink-0">
                {getTimeAgo(alert.alert_time)}
              </span>
              
              {/* Arrow on hover */}
              <ChevronRight size={10} className="text-gray-600 group-hover:text-[#00ff00] transition-colors shrink-0 opacity-0 group-hover:opacity-100" />
            </div>
          )
        })}
      </div>

      {/* Footer with link to full journal */}
      <div className="pt-2 border-t border-[#1a1a1a] mt-2">
        <button
          onClick={() => router.push('/alerts')}
          className="w-full text-center text-[10px] font-mono text-[#00ff00] hover:text-white transition-colors py-1"
        >
          View Full Alert Journal →
        </button>
      </div>
    </div>
  )
}
