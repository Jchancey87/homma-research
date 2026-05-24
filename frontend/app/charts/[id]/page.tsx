'use client'
import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Trash2 } from 'lucide-react'
import { getChart, updateChart, deleteChart, ChartCapture, chartImageUrl } from '@/lib/api'
import GeminiImportPanel from '@/components/GeminiImportPanel'
import TagSelector from '@/components/TagSelector'
import { PatternTag } from '@/lib/geminiPrompt'

export default function ChartDetailPage() {
  const { id }    = useParams<{ id: string }>()
  const router    = useRouter()
  const chartId   = Number(id)

  const [chart, setChart]       = useState<ChartCapture | null>(null)
  const [loading, setLoading]   = useState(true)
  const [editing, setEditing]   = useState(false)
  const [notes, setNotes]       = useState('')
  const [score, setScore]       = useState<number>(5)
  const [tags, setTags]         = useState<PatternTag[]>([])
  const [saving, setSaving]     = useState(false)
  const [tab, setTab]           = useState<'info' | 'gemini'>('info')

  const reload = useCallback(async () => {
    const c = await getChart(chartId)
    setChart(c)
    setNotes(c.notes ?? '')
    setScore(c.cleanliness_score ?? 5)
    try { setTags(JSON.parse(c.tags) as PatternTag[]) } catch { setTags([]) }
  }, [chartId])

  useEffect(() => {
    reload().finally(() => setLoading(false))
  }, [reload])

  const handleSave = async () => {
    setSaving(true)
    await updateChart(chartId, { notes, cleanliness_score: score, tags })
    setSaving(false); setEditing(false); reload()
  }

  const handleDelete = async () => {
    if (!confirm('Delete this chart capture and its image file?')) return
    await deleteChart(chartId)
    router.push('/charts')
  }

  if (loading) return <div className="text-gray-500 text-sm p-8">Loading…</div>
  if (!chart)  return <div className="text-red-400 text-sm p-8">Chart not found.</div>

  const parsedTags: string[] = (() => { try { return JSON.parse(chart.tags) } catch { return [] } })()

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => router.back()}
          className="text-gray-400 hover:text-white transition-colors"><ArrowLeft size={20} /></button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-white">{chart.ticker}
            <span className="text-gray-400 font-normal text-base ml-3">{chart.capture_date}</span>
            {chart.timeframe && <span className="text-gray-500 text-sm ml-2">· {chart.timeframe}</span>}
          </h1>
          {chart.setup_type && <p className="text-emerald-400 text-sm mt-0.5">{chart.setup_type}</p>}
        </div>
        <button onClick={handleDelete}
          className="flex items-center gap-1.5 px-3 py-2 text-red-400 hover:text-red-300 bg-red-500/10 hover:bg-red-500/20 rounded-lg text-sm transition-colors">
          <Trash2 size={14} /> Delete
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Chart image — takes 3 cols */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={chartImageUrl(chart.image_path)} alt={`${chart.ticker} chart`}
              className="w-full object-contain max-h-[480px]" />
          </div>
          {chart.gemini_image_path && (
            <div className="bg-gray-900 border border-violet-800/50 rounded-2xl overflow-hidden">
              <div className="px-4 py-2 border-b border-gray-800 text-xs text-violet-400 font-semibold">✦ Gemini Annotated</div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={chartImageUrl(chart.gemini_image_path)} alt="Gemini annotated"
                className="w-full object-contain max-h-[480px]" />
            </div>
          )}
        </div>

        {/* Sidebar — takes 2 cols */}
        <div className="lg:col-span-2 space-y-4">
          {/* Tab switch */}
          <div className="flex gap-2">
            {(['info', 'gemini'] as const).map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                  ${tab === t ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'}`}>
                {t === 'info' ? 'Info & Notes' : '✦ Gemini Import'}
              </button>
            ))}
          </div>

          {tab === 'info' ? (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 space-y-4">
              {/* Meta */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-gray-500 text-xs block mb-0.5">Cleanliness</span>
                  {editing ? (
                    <div className="space-y-1">
                      <input type="range" min={1} max={10} value={score}
                        onChange={e => setScore(Number(e.target.value))}
                        className="w-full accent-emerald-500" />
                      <span className="text-white font-semibold">{score}/10</span>
                    </div>
                  ) : (
                    <span className="text-white font-semibold">{chart.cleanliness_score ?? '—'}/10</span>
                  )}
                </div>
                <div>
                  <span className="text-gray-500 text-xs block mb-0.5">Gemini imported</span>
                  <span className="text-white">{chart.gemini_imported_at ? new Date(chart.gemini_imported_at).toLocaleDateString() : '—'}</span>
                </div>
              </div>

              {/* Tags */}
              <div>
                <span className="text-gray-500 text-xs block mb-2">Tags</span>
                {editing
                  ? <TagSelector selected={tags} onChange={setTags} />
                  : parsedTags.length > 0
                    ? <div className="flex flex-wrap gap-1.5">
                        {parsedTags.map(t => (
                          <span key={t} className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded-full">{t}</span>
                        ))}
                      </div>
                    : <span className="text-gray-500 text-sm">No tags</span>
                }
              </div>

              {/* Notes */}
              <div>
                <span className="text-gray-500 text-xs block mb-2">Notes</span>
                {editing ? (
                  <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={5}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-500 resize-none" />
                ) : (
                  <div className="text-sm text-gray-300 whitespace-pre-wrap">
                    {chart.notes || <span className="text-gray-500">No notes yet.</span>}
                  </div>
                )}
              </div>

              {/* Edit/Save */}
              <div className="flex gap-2 pt-2">
                {editing ? (
                  <>
                    <button onClick={handleSave} disabled={saving}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg transition-colors">
                      {saving ? 'Saving…' : 'Save'}
                    </button>
                    <button onClick={() => setEditing(false)}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg transition-colors">
                      Cancel
                    </button>
                  </>
                ) : (
                  <button onClick={() => setEditing(true)}
                    className="w-full bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium py-2 rounded-lg transition-colors">
                    Edit
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
              <GeminiImportPanel
                chartId={chartId}
                existingAnnotation={chart.gemini_annotation}
                onImported={reload}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
