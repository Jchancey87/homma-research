'use client'
import { useEffect, useState } from 'react'
import { getEconomicCalendar, EconomicEvent } from '@/lib/api'
import { CalendarDays, AlertTriangle, Info } from 'lucide-react'

function daysUntil(dateStr: string): number {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(dateStr)
  target.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / 86400000)
}

function formatEventDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

export default function EconomicCalendar() {
  const [events, setEvents] = useState<EconomicEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getEconomicCalendar()
      .then(d => setEvents((d.events || []).slice(0, 6)))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex gap-3 overflow-x-auto pb-1 animate-pulse">
      {[1,2,3].map(i => <div key={i} className="h-16 w-40 shrink-0 bg-gray-800/60 rounded-lg" />)}
    </div>
  )

  if (events.length === 0) return (
    <div className="flex items-center gap-2 text-gray-700 text-xs py-3 pl-1">
      <Info size={12} />
      No high-impact events this week
    </div>
  )

  return (
    <div className="space-y-1">
      {events.map((e, i) => {
        const days = daysUntil(e.date)
        const isHigh = e.impact === 'high'
        const accentColor = isHigh ? 'text-red-400' : 'text-yellow-400'
        const accentBg    = isHigh ? 'bg-red-500/10' : 'bg-yellow-500/10'

        return (
          <div
            key={i}
            className="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-gray-800/40 transition-colors"
          >
            {/* Impact indicator */}
            <div className={`p-1 rounded-md ${accentBg} shrink-0`}>
              <AlertTriangle size={11} className={accentColor} />
            </div>

            {/* Event name */}
            <span className="text-xs text-gray-200 flex-1 min-w-0 truncate">{e.event}</span>

            {/* Days until */}
            <div className="text-right shrink-0">
              <div className={`text-xs font-bold font-mono ${accentColor}`}>
                {days === 0 ? 'TODAY' : days === 1 ? 'Tomorrow' : `${days}d`}
              </div>
              <div className="text-[10px] text-gray-700">{formatEventDate(e.date)}</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
