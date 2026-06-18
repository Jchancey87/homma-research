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
      const params: Parameters<typeof getCharts>[0] = {}
      if (filterTicker)   params.ticker          = filterTicker.toUpperCase()
      if (filterTag)      params.tag             = filterTag
      if (dateFrom)       params.date_from       = dateFrom
      if (dateTo)         params.date_to         = dateTo
      if (minCleanliness) params.min_cleanliness = Number(minCleanliness)
      setCharts(await getCharts(params))
    } finally { setLoading(false) }
  }

  useEffect(() => {
    const loadInitial = async () => {
      setLoading(true)
      try {
        setCharts(await getCharts({}))
      } finally {
        setLoading(false)
      }
    }
    loadInitial()
  }, [])

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-[#050505] border border-[#262626]">
        <div>
          <h1 className="font-mono text-sm font-bold text-white uppercase flex items-center gap-1.5">
            <TrendingUp className="text-[#00ff00]" size={14} />
            Chart Playbook
          </h1>
          <p className="font-mono text-[10px] text-gray-500 mt-0.5">{charts.length} setups captured</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="p-1.5 border border-[#262626] bg-black text-gray-400 hover:text-white transition-colors rounded-none"
          >
            <RefreshCw size={13} />
          </button>
          <button onClick={() => setShowUpload(v => !v)}
            className="flex items-center gap-1 px-2.5 py-1 border border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00] text-[11px] font-mono hover:bg-emerald-950/30 transition-colors rounded-none">
            <Plus size={12} /> {showUpload ? 'Hide Upload' : 'Upload Chart'}
          </button>
        </div>
      </div>

      {/* Upload panel */}
      {showUpload && (
        <div className="border border-[#262626] bg-[#050505] p-3">
          <ChartUpload onSuccess={() => { setShowUpload(false); load() }} />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-1.5 p-2 bg-[#0a0a0a] border border-[#262626]">
        <div className="flex items-center gap-1 text-gray-500">
          <Filter size={11} />
          <span className="font-mono text-[11px] uppercase tracking-wider">Filters</span>
        </div>
        <input value={filterTicker} onChange={e => setFilterTicker(e.target.value.toUpperCase())}
          placeholder="Ticker…"
          className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none w-20 placeholder-gray-600" />
        <select value={filterTag} onChange={e => setFilterTag(e.target.value)}
          className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark]">
          <option value="">All pattern tags</option>
          {VALID_TAGS.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-mono text-[10px] text-gray-500 uppercase tracking-wider">Date:</span>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark]" />
          <span className="font-mono text-[10px] text-gray-600">to</span>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark]" />
        </div>
        <input type="number" min={1} max={10} value={minCleanliness} onChange={e => setMinCleanliness(e.target.value)}
          placeholder="Min ★"
          className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none w-16 placeholder-gray-600" />

        <div className="flex items-center gap-1.5 ml-auto">
          {(filterTicker || filterTag || dateFrom || dateTo || minCleanliness) && (
            <button onClick={() => { setFilterTicker(''); setFilterTag(''); setDateFrom(''); setDateTo(''); setMinCleanliness('') }}
              className="px-2.5 py-1 border border-[#262626] bg-black text-gray-400 hover:text-white font-mono text-[11px] transition-colors rounded-none">
              Clear
            </button>
          )}
          <button onClick={load}
            className="px-2.5 py-1 border border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00] font-mono text-[11px] hover:bg-emerald-950/30 transition-colors rounded-none">
            Apply
          </button>
        </div>
      </div>

      {/* Gallery */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-1">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="animate-pulse bg-[#111] aspect-video" />
          ))}
        </div>
      ) : charts.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2 border border-[#262626] bg-[#050505]">
          <TrendingUp size={28} className="text-gray-700" />
          <span className="text-gray-500 text-xs uppercase tracking-wider font-mono">
            {filterTicker || filterTag || dateFrom || dateTo || minCleanliness
              ? 'No charts match filters'
              : 'No charts captured yet'}
          </span>
          <button
            onClick={() => setShowUpload(true)}
            className="mt-2 flex items-center gap-1 px-2.5 py-1 border border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00] text-[11px] font-mono hover:bg-emerald-950/30 transition-colors rounded-none"
          >
            <Plus size={12} />
            Upload First Chart
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-1">
          {charts.map(c => {
            const tags: string[] = (() => { try { return JSON.parse(c.tags) } catch { return [] } })()
            return (
              <Link key={c.id} href={`/charts/${c.id}`}
                className="bg-[#050505] border border-[#262626] hover:border-[#444] transition-colors group cursor-pointer">
                <div className="aspect-video overflow-hidden bg-black">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={chartImageUrl(c.image_path)} alt={`${c.ticker} ${c.capture_date}`}
                    className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-300"
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                </div>
                <div className="p-2 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-white text-xs">{c.ticker}</span>
                    {c.cleanliness_score && (
                      <span className="font-mono text-[10px] text-amber-400">⭐ {c.cleanliness_score}/10</span>
                    )}
                  </div>
                  <div className="font-mono text-[10px] text-gray-500">
                    {c.capture_date} {c.timeframe && `· ${c.timeframe}`}
                  </div>
                  {(tags.length > 0 || c.gemini_annotation) && (
                    <div className="flex flex-wrap items-center gap-1 pt-1 border-t border-[#1a1a1a]">
                      {tags.slice(0, 2).map(t => (
                        <span key={t} className="font-mono text-[10px] px-1.5 py-0.5 border border-[#262626] bg-[#111] text-gray-500 rounded-none">{t}</span>
                      ))}
                      {tags.length > 2 && <span className="font-mono text-[10px] text-gray-600">+{tags.length - 2}</span>}
                      {c.gemini_annotation && (
                        <span className="font-mono text-[10px] text-[#00f0ff] hover:text-white transition-colors ml-auto">✦ AI</span>
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
