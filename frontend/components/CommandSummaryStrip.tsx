'use client'

import { useEffect, useState, useCallback } from 'react'
import { getCommandSummary, CommandSummaryData } from '@/lib/api'
import MarketRegimeCard from './market-overview/MarketRegimeCard'
import SmallCapBreadthCard from './market-overview/SmallCapBreadthCard'
import LiquidityFloatCard from './market-overview/LiquidityFloatCard'
import RiskAnomaliesCard from './market-overview/RiskAnomaliesCard'
import { CardId } from './market-overview/types'

// ── Skeleton ────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-[#0D1218] border border-border-subtle p-3 shadow-sm">
      <div className="flex items-center gap-1.5 mb-3">
        <div className="h-3 w-3 bg-[#131B24] animate-pulse" />
        <div className="h-3 w-24 bg-[#131B24] animate-pulse" />
      </div>
      <div className="h-7 w-20 bg-[#131B24] animate-pulse mb-2" />
      <div className="h-4 w-16 bg-[#131B24] animate-pulse mb-3" />
      <div className="space-y-1.5">
        <div className="h-3 w-full bg-[#131B24] animate-pulse" />
        <div className="h-3 w-3/4 bg-[#131B24] animate-pulse" />
        <div className="h-3 w-2/3 bg-[#131B24] animate-pulse" />
      </div>
    </div>
  )
}

// ── Component ───────────────────────────────────────────────────────────────

export default function CommandSummaryStrip() {
  const [data, setData] = useState<CommandSummaryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [priceFilter, setPriceFilter] = useState(true)
  const [expanded, setExpanded] = useState<CardId | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const toggle = (id: CardId) => setExpanded(prev => prev === id ? null : id)

  const loadData = useCallback(async (filter: boolean) => {
    try {
      const res = await getCommandSummary(filter)
      setData(res)
      setLastUpdated(new Date())
    } catch (err) {
      console.error('Failed to load command summary', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Sync price filter from localStorage
  useEffect(() => {
    const val = localStorage.getItem('price-filter-enabled')
    const currentFilter = val !== null ? val === 'true' : true
    setPriceFilter(currentFilter)
    loadData(currentFilter)

    const handleSync = () => {
      const syncedVal = localStorage.getItem('price-filter-enabled')
      const newFilter = syncedVal !== null ? syncedVal === 'true' : true
      setPriceFilter(newFilter)
      setLoading(true)
      loadData(newFilter)
    }

    window.addEventListener('price-filter-changed', handleSync)
    return () => window.removeEventListener('price-filter-changed', handleSync)
  }, [loadData])

  // Poll every 60s
  useEffect(() => {
    const timer = setInterval(() => loadData(priceFilter), 60_000)
    return () => clearInterval(timer)
  }, [priceFilter, loadData])

  const refresh = () => {
    setLoading(true)
    loadData(priceFilter)
  }

  if (loading && !data) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 bg-transparent">
        {[1, 2, 3, 4].map(i => <SkeletonCard key={i} />)}
      </div>
    )
  }

  if (!data) return null

  return (
    <div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 bg-transparent">
        <MarketRegimeCard
          data={data.regime}
          macro={data.macro}
          expanded={expanded === 'regime'}
          onToggle={() => toggle('regime')}
        />

        <SmallCapBreadthCard
          data={data.breadth}
          expanded={expanded === 'breadth'}
          onToggle={() => toggle('breadth')}
        />

        <LiquidityFloatCard
          data={data.liquidity}
          expanded={expanded === 'liquidity'}
          onToggle={() => toggle('liquidity')}
        />

        <RiskAnomaliesCard
          data={data.risk}
          lastUpdated={lastUpdated}
          onRefresh={refresh}
          loading={loading}
          expanded={expanded === 'risk'}
          onToggle={() => toggle('risk')}
        />
      </div>

      {lastUpdated && (
        <div className="flex justify-end px-1 pt-1">
          <span className="text-[9px] font-mono text-gray-600">
            {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · {data.cache_ttl_s}s cache
          </span>
        </div>
      )}
    </div>
  )
}
