'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  getRSSSources, createRSSSource, updateRSSSource, deleteRSSSource,
  getRSSPool, triggerRSSIngest, curateRSSItem, rejectRSSItem,
  RSSSource, RSSFeedPoolItem
} from '@/lib/api'
import { FileText, Plus, Trash2, Check, X, Rss, RefreshCw, Send, ExternalLink } from 'lucide-react'

export default function RSSCurationPage() {
  const [sources, setSources] = useState<RSSSource[]>([])
  const [poolItems, setPoolItems] = useState<RSSFeedPoolItem[]>([])
  const [loadingSources, setLoadingSources] = useState(true)
  const [loadingPool, setLoadingPool] = useState(true)
  const [ingesting, setIngesting] = useState(false)
  
  // New source form state
  const [newSourceName, setNewSourceName] = useState('')
  const [newSourceUrl, setNewSourceUrl] = useState('')
  const [newSourceCat, setNewSourceCat] = useState<'biotech' | 'tech' | 'general'>('biotech')
  
  // Modal / Curate item state
  const [curatingItem, setCuratingItem] = useState<RSSFeedPoolItem | null>(null)
  const [curatedTitle, setCuratedTitle] = useState('')
  const [curatedDesc, setCuratedDesc] = useState('')
  const [curatedTickers, setCuratedTickers] = useState('')
  const [curatedNotes, setCuratedNotes] = useState('')
  const [publishing, setPublishing] = useState(false)

  // Fetch Sources
  const fetchSources = useCallback(async () => {
    setLoadingSources(true)
    try {
      const data = await getRSSSources()
      setSources(data)
    } catch (err) {
      console.error('Failed to load RSS sources:', err)
    } finally {
      setLoadingSources(false)
    }
  }, [])

  // Fetch Pool
  const fetchPool = useCallback(async () => {
    setLoadingPool(true)
    try {
      const data = await getRSSPool('pending')
      setPoolItems(data)
    } catch (err) {
      console.error('Failed to load pending feed pool:', err)
    } finally {
      setLoadingPool(false)
    }
  }, [])

  useEffect(() => {
    fetchSources()
    fetchPool()
  }, [fetchSources, fetchPool])

  // Ingest Trigger
  const handleIngest = useCallback(async () => {
    setIngesting(true)
    try {
      const res = await triggerRSSIngest()
      alert(`Ingestion finished!\nProcessed: ${res.stats.processed}\nInserted: ${res.stats.inserted}\nAuto-Approved: ${res.stats.auto_approved}`)
      fetchPool()
    } catch (err) {
      console.error('Failed triggering ingest:', err)
      alert('Failed to run ingestion task.')
    } finally {
      setIngesting(false)
    }
  }, [fetchPool])

  // Add Source
  const handleAddSource = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newSourceName || !newSourceUrl) return
    try {
      await createRSSSource({
        name: newSourceName,
        feed_url: newSourceUrl,
        category: newSourceCat
      })
      setNewSourceName('')
      setNewSourceUrl('')
      fetchSources()
    } catch (err) {
      console.error('Failed to add source:', err)
      alert('Failed to add RSS source.')
    }
  }

  // Toggle Source Active
  const handleToggleSource = async (src: RSSSource) => {
    try {
      await updateRSSSource(src.id, { is_active: !src.is_active })
      fetchSources()
    } catch (err) {
      console.error('Failed to toggle source:', err)
    }
  }

  // Delete Source
  const handleDeleteSource = async (id: number) => {
    if (!confirm('Are you sure you want to remove this source?')) return
    try {
      await deleteRSSSource(id)
      fetchSources()
    } catch (err) {
      console.error('Failed to delete source:', err)
    }
  }

  // Open Curation Dialog
  const startCurating = (item: RSSFeedPoolItem) => {
    setCuratingItem(item)
    setCuratedTitle(item.title)
    setCuratedDesc(item.description || '')
    setCuratedTickers(item.detected_tickers.join(', '))
    setCuratedNotes('')
  }

  // Submit Curate Item
  const handlePublishCuration = async () => {
    if (!curatingItem) return
    setPublishing(true)
    try {
      const tickersArray = curatedTickers
        .split(',')
        .map(t => t.trim().toUpperCase())
        .filter(t => t.length > 0)

      await curateRSSItem(curatingItem.id, {
        title: curatedTitle,
        description: curatedDesc,
        associated_tickers: tickersArray,
        curated_notes: curatedNotes
      })

      setCuratingItem(null)
      fetchPool()
    } catch (err) {
      console.error('Failed publishing curation:', err)
      alert('Failed to curate and publish item.')
    } finally {
      setPublishing(false)
    }
  }

  // Reject Item
  const handleRejectItem = async (id: number) => {
    try {
      await rejectRSSItem(id)
      setPoolItems(items => items.filter(x => x.id !== id))
    } catch (err) {
      console.error('Failed to reject item:', err)
    }
  }

  return (
    <main className="max-w-screen-2xl mx-auto p-4 space-y-4 text-gray-300">
      
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#262626] pb-3">
        <div>
          <h1 className="font-mono text-lg font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <Rss className="text-[#00ff00]" size={18} />
            RSS Feed Curation Manager
          </h1>
          <p className="font-mono text-[10px] text-gray-500 mt-0.5">
            Ingest financial feeds, curate catalysts, and syndicate breaking updates.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <a
            href="http://127.0.0.1:5000/api/rss/feed"
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-[#262626] text-gray-400 hover:text-white bg-black hover:border-gray-600 transition-colors flex items-center gap-1.5"
          >
            <ExternalLink size={12} />
            View RSS XML Feed
          </a>
          <button
            onClick={handleIngest}
            disabled={ingesting}
            className="font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 hover:bg-emerald-950/20 disabled:opacity-50 transition-colors flex items-center gap-1.5"
          >
            <RefreshCw size={12} className={ingesting ? 'animate-spin' : ''} />
            {ingesting ? 'Ingesting...' : 'Trigger Feed Ingest'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        
        {/* Left Side: Sources Settings */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-black border border-[#262626] p-4 space-y-3">
            <h2 className="font-mono text-xs font-bold text-white uppercase tracking-wider border-b border-[#262626] pb-1.5">
              RSS Feed Sources
            </h2>
            
            {/* Add Source Form */}
            <form onSubmit={handleAddSource} className="space-y-2 border-b border-[#262626] pb-3">
              <div className="space-y-1">
                <label className="font-mono text-[9px] text-gray-500 uppercase">Source Name</label>
                <input
                  type="text"
                  placeholder="e.g. BioPharma Dive"
                  value={newSourceName}
                  onChange={e => setNewSourceName(e.target.value)}
                  className="w-full bg-[#050505] border border-[#262626] text-xs text-white p-1.5 focus:border-[#444] focus:outline-none rounded-none font-mono"
                  required
                />
              </div>
              <div className="space-y-1">
                <label className="font-mono text-[9px] text-gray-500 uppercase">RSS Feed URL</label>
                <input
                  type="url"
                  placeholder="https://example.com/rss"
                  value={newSourceUrl}
                  onChange={e => setNewSourceUrl(e.target.value)}
                  className="w-full bg-[#050505] border border-[#262626] text-xs text-white p-1.5 focus:border-[#444] focus:outline-none rounded-none font-mono"
                  required
                />
              </div>
              <div className="flex gap-2">
                <div className="flex-1 space-y-1">
                  <label className="font-mono text-[9px] text-gray-500 uppercase">Category</label>
                  <select
                    value={newSourceCat}
                    onChange={e => setNewSourceCat(e.target.value as any)}
                    className="w-full bg-[#050505] border border-[#262626] text-xs text-white p-1.5 focus:border-[#444] focus:outline-none rounded-none font-mono"
                  >
                    <option value="biotech">Biotech</option>
                    <option value="tech">Tech</option>
                    <option value="general">General</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <button
                    type="submit"
                    className="font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-[#262626] bg-[#0c0c0c] hover:bg-white hover:text-black transition-all flex items-center gap-1 w-full justify-center"
                  >
                    <Plus size={13} />
                    Add
                  </button>
                </div>
              </div>
            </form>

            {/* Sources List */}
            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
              {loadingSources ? (
                <p className="font-mono text-[10px] text-gray-500">Loading sources...</p>
              ) : sources.length === 0 ? (
                <p className="font-mono text-[10px] text-gray-500">No sources configured.</p>
              ) : (
                sources.map(src => (
                  <div key={src.id} className="p-2 border border-[#1a1a1a] bg-[#030303] hover:border-[#262626] transition-colors flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[11px] font-bold text-white truncate block">{src.name}</span>
                        <span className={`font-mono text-[8px] uppercase px-1 border border-[#262626] ${
                          src.category === 'biotech' ? 'text-[#00ff00]' : src.category === 'tech' ? 'text-amber-500' : 'text-gray-400'
                        }`}>
                          {src.category}
                        </span>
                      </div>
                      <span className="font-mono text-[9px] text-gray-500 truncate block mt-0.5">{src.feed_url}</span>
                      <span className="font-mono text-[8px] text-gray-600 block">
                        Polled: {src.last_polled_at ? new Date(src.last_polled_at).toLocaleTimeString() : 'Never'}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        onClick={() => handleToggleSource(src)}
                        className={`font-mono text-[8px] uppercase tracking-wider px-1.5 py-0.5 border ${
                          src.is_active 
                            ? 'border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10' 
                            : 'border-transparent text-gray-600'
                        }`}
                      >
                        {src.is_active ? 'Active' : 'Off'}
                      </button>
                      <button
                        onClick={() => handleDeleteSource(src.id)}
                        className="p-1 border border-transparent text-gray-600 hover:text-[#ff003c] hover:border-[#ff003c]/20"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Side: Pending Queue */}
        <div className="lg:col-span-8 space-y-4">
          <div className="bg-black border border-[#262626] p-4 space-y-3">
            <h2 className="font-mono text-xs font-bold text-white uppercase tracking-wider border-b border-[#262626] pb-1.5">
              Staging Feed Pool (Pending Articles)
            </h2>

            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {loadingPool ? (
                <p className="font-mono text-[10px] text-gray-500">Loading pending feed queue...</p>
              ) : poolItems.length === 0 ? (
                <p className="font-mono text-[10px] text-gray-500">Staging pool is empty. Click Trigger Feed Ingest to poll sources.</p>
              ) : (
                poolItems.map(item => (
                  <div key={item.id} className="p-3 border border-[#1a1a1a] bg-[#030303] hover:border-[#262626] transition-colors space-y-2 group">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-0.5">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="font-mono text-[9px] text-gray-500">
                            {new Date(item.published_at).toLocaleString()}
                          </span>
                          {item.detected_tickers.length > 0 && (
                            <div className="flex gap-1">
                              {item.detected_tickers.map(t => (
                                <span key={t} className="font-mono text-[9px] font-bold px-1 border border-[#00ff00]/40 text-[#00ff00] bg-emerald-950/20">
                                  ${t}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <h3 className="font-mono text-xs font-bold text-white leading-tight">
                          {item.title}
                        </h3>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => startCurating(item)}
                          className="font-mono text-[9px] uppercase tracking-wider px-2 py-1 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 hover:bg-emerald-950/25 flex items-center gap-1"
                        >
                          <Check size={10} />
                          Curate
                        </button>
                        <button
                          onClick={() => handleRejectItem(item.id)}
                          className="font-mono text-[9px] uppercase tracking-wider px-2 py-1 border border-[#ff003c]/20 text-[#ff003c] hover:bg-[#ff003c]/10 flex items-center gap-1"
                        >
                          <X size={10} />
                          Reject
                        </button>
                      </div>
                    </div>
                    {item.description && (
                      <p className="font-mono text-[10px] text-gray-400 leading-relaxed max-line-clamp-2">
                        {item.description.replace(/<[^>]*>/g, '')}
                      </p>
                    )}
                    <a
                      href={item.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-[9px] text-gray-500 hover:text-white flex items-center gap-1 mt-1 w-max"
                    >
                      <ExternalLink size={10} />
                      Original Link
                    </a>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

      </div>

      {/* Curation Modal Dialog */}
      {curatingItem && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#050505] border border-[#262626] max-w-2xl w-full p-4 space-y-4 shadow-xl shadow-black/80">
            <div className="flex items-center justify-between border-b border-[#262626] pb-2">
              <h3 className="font-mono text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="text-[#00ff00]" size={14} />
                Curate Article / Publish to RSS
              </h3>
              <button
                onClick={() => setCuratingItem(null)}
                className="text-gray-500 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <div className="space-y-1">
                <label className="text-[9px] text-gray-500 uppercase">Title</label>
                <input
                  type="text"
                  value={curatedTitle}
                  onChange={e => setCuratedTitle(e.target.value)}
                  className="w-full bg-[#090909] border border-[#262626] text-white p-2 focus:border-[#00ff00]/40 focus:outline-none rounded-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[9px] text-gray-500 uppercase">Curated Description / Research Summary</label>
                <textarea
                  value={curatedDesc}
                  onChange={e => setCuratedDesc(e.target.value)}
                  rows={4}
                  className="w-full bg-[#090909] border border-[#262626] text-white p-2 focus:border-[#00ff00]/40 focus:outline-none rounded-none resize-none leading-relaxed"
                  placeholder="Summarize regulatory catalyst detail, financial impact, dilution risk..."
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[9px] text-gray-500 uppercase">Associated Tickers (Comma separated)</label>
                  <input
                    type="text"
                    value={curatedTickers}
                    onChange={e => setCuratedTickers(e.target.value)}
                    className="w-full bg-[#090909] border border-[#262626] text-white p-2 focus:border-[#00ff00]/40 focus:outline-none rounded-none uppercase"
                    placeholder="BIIB, MRNA"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[9px] text-gray-500 uppercase">Internal Curation Notes (Optional)</label>
                  <input
                    type="text"
                    value={curatedNotes}
                    onChange={e => setCuratedNotes(e.target.value)}
                    className="w-full bg-[#090909] border border-[#262626] text-white p-2 focus:border-[#00ff00]/40 focus:outline-none rounded-none"
                    placeholder="e.g. Added to priority gap list"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-[#262626] pt-3">
              <span className="font-mono text-[9px] text-gray-600">
                Note: Approving will immediately trigger Telegram Alert broadcast
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setCuratingItem(null)}
                  className="font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-[#262626] bg-black text-gray-400 hover:text-white hover:border-gray-600 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handlePublishCuration}
                  disabled={publishing}
                  className="font-mono text-[11px] uppercase tracking-wider px-4 py-1.5 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/20 hover:bg-emerald-950/45 disabled:opacity-50 transition-all flex items-center gap-1.5"
                >
                  <Send size={12} />
                  {publishing ? 'Publishing...' : 'Approve & Publish'}
                </button>
              </div>
            </div>

          </div>
        </div>
      )}

    </main>
  )
}
