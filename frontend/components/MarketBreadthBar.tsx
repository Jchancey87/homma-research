'use client'
import { useEffect, useState } from 'react'
import { getMarketBreadth, MarketBreadthData } from '@/lib/api'
import { TrendingUp, TrendingDown, Minus, RefreshCw } from 'lucide-react'

function chgColor(v: number | null) {
  if (v == null) return 'text-gray-500'
  return v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-gray-400'
}

function chgSign(v: number | null) {
  if (v == null) return ''
  return v > 0 ? '+' : ''
}

const BIAS_CONFIG = {
  risk_on:  { label: 'Risk ON',  bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20' },
  neutral:  { label: 'Neutral',  bg: 'bg-yellow-500/10',  text: 'text-yellow-400',  border: 'border-yellow-500/20' },
  risk_off: { label: 'Risk OFF', bg: 'bg-red-500/10',     text: 'text-red-400',     border: 'border-red-500/20' },
  unknown:  { label: 'No Data',  bg: 'bg-gray-800',       text: 'text-gray-500',    border: 'border-gray-700' },
}

const INDEX_ORDER = ['SPY', 'QQQ', 'IWM']

export default function MarketBreadthBar() {
  const [data, setData]       = useState<MarketBreadthData | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastFetch, setLastFetch] = useState<Date | null>(null)

  const load = async () => {
    try {
      const d = await getMarketBreadth()
      setData(d)
      setLastFetch(new Date())
    } catch {}
    finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    // Auto-refresh every 15 minutes
    const iv = setInterval(load, 15 * 60 * 1000)
    return () => clearInterval(iv)
  }, [])

  const bias = BIAS_CONFIG[data?.bias ?? 'unknown']

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2.5 bg-gray-950 border border-gray-800/80 rounded-xl text-sm">
      {loading ? (
        <div className="flex gap-6 animate-pulse">
          {[1,2,3].map(i => <div key={i} className="h-4 w-24 bg-gray-800 rounded" />)}
        </div>
      ) : (
        <>
          {/* Index prices */}
          <div className="flex items-center gap-6">
            {INDEX_ORDER.map(ticker => {
              const idx = data?.indices?.[ticker]
              if (!idx) return null
              return (
                <div key={ticker} className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-gray-500 tracking-wider">{ticker}</span>
                  <span className="text-white font-mono text-sm font-semibold">
                    {idx.price != null ? `$${idx.price.toFixed(2)}` : '—'}
                  </span>
                  <span className={`font-mono text-xs font-medium ${chgColor(idx.chg_pct)}`}>
                    {idx.chg_pct != null ? `${chgSign(idx.chg_pct)}${idx.chg_pct.toFixed(2)}%` : '—'}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Bias badge */}
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border ${bias.bg} ${bias.text} ${bias.border}`}>
              {data?.bias === 'risk_on'  && <TrendingUp  size={11} />}
              {data?.bias === 'risk_off' && <TrendingDown size={11} />}
              {data?.bias === 'neutral'  && <Minus        size={11} />}
              {bias.label}
            </span>
            {lastFetch && (
              <span className="text-[10px] text-gray-700 hidden lg:block">
                Updated {lastFetch.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            <button
              onClick={load}
              className="text-gray-700 hover:text-gray-400 transition-colors"
              title="Refresh market data"
            >
              <RefreshCw size={12} />
            </button>
          </div>
        </>
      )}
    </div>
  )
}
