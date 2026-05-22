'use client'
import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Plus, TrendingUp, Filter, RefreshCw } from 'lucide-react'
import { getCharts, ChartCapture, chartImageUrl } from '@/lib/api'
import { VALID_TAGS } from '@/lib/geminiPrompt'
import ChartUpload from '@/components/ChartUpload'

export default function ChartsPage() {
  const [charts, setCharts]       = useState<ChartCapture[]>([])
  const [loading, setLoading]     = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [filterTag, setFilterTag] = useState<string>('')
  const [filterTicker, setFilterTicker] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [minCleanliness, setMinCleanliness] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (filterTicker)   params.ticker          = filterTicker.toUpperCase()
      if (filterTag)      params.tag             = filterTag
      if (dateFrom)       params.date_from       = dateFrom
      if (dateTo)         params.date_to         = dateTo
      if (minCleanliness) params.min_cleanliness = Number(minCleanliness)
      setCharts(await getCharts(params))
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <TrendingUp className="text-emerald-500 dark:text-emerald-450" size={24} />
            Chart Playbook
          </h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">{charts.length} setups captured</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="p-2 rounded-lg text-gray-500 hover:text-gray-950 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            <RefreshCw size={16} />
          </button>
          <button onClick={() => setShowUpload(v => !v)}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm rounded-lg transition-colors shadow">
            <Plus size={15} /> {showUpload ? 'Hide Upload' : 'Upload Chart'}
          </button>
        </div>
      </div>

      {showUpload && (
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-5 shadow-sm space-y-4">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">Upload New Chart</h2>
          <ChartUpload onSuccess={() => { setShowUpload(false); load() }} />
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap items-center bg-gray-50 dark:bg-gray-900/50 border border-gray-250 dark:border-gray-800 rounded-xl p-4">
        <div className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
          <Filter size={14} />
          <span className="text-xs font-semibold uppercase tracking-wider">Filters</span>
        </div>
        <input value={filterTicker} onChange={e => setFilterTicker(e.target.value.toUpperCase())}
          placeholder="Ticker…"
          className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 w-24" />
        <select value={filterTag} onChange={e => setFilterTag(e.target.value)}
          className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-905 dark:text-white focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500">
          <option value="" className="text-gray-500 dark:text-gray-400">All pattern tags</option>
          {VALID_TAGS.map(t => <option key={t} value={t} className="text-gray-900 dark:text-white">{t}</option>)}
        </select>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-gray-500 dark:text-gray-400 text-xs font-medium">Date:</span>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-905 dark:text-white focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500" />
          <span className="text-gray-400 dark:text-gray-600 text-xs">to</span>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-905 dark:text-white focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500" />
        </div>
        <input type="number" min={1} max={10} value={minCleanliness} onChange={e => setMinCleanliness(e.target.value)}
          placeholder="Min ⭐"
          className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-905 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 w-20" />
        
        <div className="flex items-center gap-2 ml-auto">
          {(filterTicker || filterTag || dateFrom || dateTo || minCleanliness) && (
            <button onClick={() => { setFilterTicker(''); setFilterTag(''); setDateFrom(''); setDateTo(''); setMinCleanliness('') }}
              className="text-xs text-gray-500 hover:text-gray-950 dark:hover:text-white font-semibold">
              Clear
            </button>
          )}
          <button onClick={load}
            className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-lg transition-colors shadow">
            Apply
          </button>
        </div>
      </div>

      {/* Gallery */}
      {loading ? (
        <div className="text-center text-gray-500 dark:text-gray-400 text-sm py-12">Loading playbook…</div>
      ) : charts.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 bg-gray-50 dark:bg-gray-900/20 border border-dashed border-gray-200 dark:border-gray-800 rounded-2xl gap-3 text-center px-4 transition-all max-w-xl mx-auto mt-6 animate-fade-in">
          <TrendingUp size={36} className="text-emerald-500 dark:text-emerald-400 animate-pulse" />
          <div className="space-y-1">
            <h3 className="font-bold text-gray-900 dark:text-white text-base">No charts found</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 max-w-xs">
              {filterTicker || filterTag || dateFrom || dateTo || minCleanliness
                ? 'Try adjusting your filters to find specific chart patterns.'
                : 'Upload screenshots of your setups, flags, or reversals to start building your trading database.'}
            </p>
          </div>
          <button
            onClick={() => setShowUpload(true)}
            className="mt-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl transition-colors shadow-md shadow-emerald-500/10 flex items-center gap-1.5"
          >
            <Plus size={14} />
            Upload First Chart
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {charts.map(c => {
            const tags: string[] = (() => { try { return JSON.parse(c.tags) } catch { return [] } })()
            return (
              <Link key={c.id} href={`/charts/${c.id}`}
                className="group bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden hover:border-emerald-550 dark:hover:border-emerald-500/50 hover:shadow-md transition-all flex flex-col">
                <div className="aspect-video bg-gray-100 dark:bg-gray-850 overflow-hidden relative border-b border-gray-200 dark:border-gray-800">
                  <img src={chartImageUrl(c.image_path)} alt={`${c.ticker} ${c.capture_date}`}
                    className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-300"
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                </div>
                <div className="p-4 space-y-2 flex-grow flex flex-col justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-gray-900 dark:text-white text-base">{c.ticker}</span>
                      {c.cleanliness_score && (
                        <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">⭐ {c.cleanliness_score}/10</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-405 dark:text-gray-500 font-medium">
                      {c.capture_date} {c.timeframe && `· ${c.timeframe}`}
                    </div>
                  </div>
                  {(tags.length > 0 || c.gemini_annotation) && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-gray-100 dark:border-gray-800/40">
                      {tags.slice(0, 2).map(t => (
                        <span key={t} className="text-[10px] font-semibold bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 px-2 py-0.5 rounded-full border border-gray-200 dark:border-gray-750">{t}</span>
                      ))}
                      {tags.length > 2 && <span className="text-[10px] text-gray-400 dark:text-gray-500 font-bold">+{tags.length - 2}</span>}
                      {c.gemini_annotation && (
                        <span className="inline-flex items-center text-[10px] font-semibold bg-violet-50 dark:bg-violet-500/15 text-violet-700 dark:text-violet-300 px-2 py-0.5 rounded-full border border-violet-100 dark:border-violet-500/20 ml-auto">✦ Gemini</span>
                      )}
                    </div>
                  )}
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
