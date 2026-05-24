'use client'
import { useState, useRef } from 'react'
import { Copy, Check, Upload, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { GEMINI_CHART_PROMPT, copyGeminiPrompt } from '@/lib/geminiPrompt'
import { importGeminiAnalysis } from '@/lib/api'

interface Props {
  chartId: number
  existingAnnotation?: string | null
  onImported?: () => void
}

export default function GeminiImportPanel({ chartId, existingAnnotation, onImported }: Props) {
  const [copied, setCopied]         = useState(false)
  const [text, setText]             = useState(existingAnnotation ?? '')
  const [annotImage, setAnnotImage] = useState<File | null>(null)
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState<string | null>(null)
  const [success, setSuccess]       = useState(false)
  const fileRef                     = useRef<HTMLInputElement>(null)

  const handleCopy = async () => {
    const ok = await copyGeminiPrompt()
    if (ok) { setCopied(true); setTimeout(() => setCopied(false), 2000) }
  }

  const handleImport = async () => {
    if (!text.trim()) { setError('Paste the Gemini analysis text first.'); return }
    setLoading(true); setError(null)
    try {
      await importGeminiAnalysis(chartId, text.trim(), annotImage ?? undefined)
      setSuccess(true)
      onImported?.()
    } catch (e) {
      const err = e as { response?: { data?: { error?: string } } }
      setError(err?.response?.data?.error ?? 'Import failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Prompt copy */}
      <div className="bg-gray-800/60 border border-gray-700 rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-gray-200">Step 1 — Copy prompt → paste into Gemini</h4>
          <button onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/40 text-violet-300 text-xs font-medium rounded-lg transition-colors">
            {copied ? <><Check size={13} /> Copied!</> : <><Copy size={13} /> Copy Prompt</>}
          </button>
        </div>
        <pre className="text-xs text-gray-400 whitespace-pre-wrap leading-relaxed max-h-40 overflow-y-auto">
          {GEMINI_CHART_PROMPT}
        </pre>
      </div>

      {/* Paste result */}
      <div className="space-y-2">
        <label className="text-sm font-semibold text-gray-200">Step 2 — Paste Gemini analysis</label>
        <textarea
          value={text}
          onChange={e => { setText(e.target.value); setSuccess(false) }}
          rows={10}
          placeholder="Paste structured Gemini analysis here…"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-violet-500 resize-none"
        />
      </div>

      {/* Optional annotated image */}
      <div className="space-y-2">
        <label className="text-sm font-semibold text-gray-200">Step 3 — Upload annotated image (optional)</label>
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => fileRef.current?.click()}
            className="flex items-center gap-2 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-300 hover:border-gray-500 transition-colors">
            <Upload size={14} />
            {annotImage ? annotImage.name : 'Choose file'}
          </button>
          {annotImage && (
            <button type="button" onClick={() => setAnnotImage(null)}
              className="text-xs text-red-400 hover:text-red-300">Remove</button>
          )}
        </div>
        <input ref={fileRef} type="file" accept="image/*" className="hidden"
          onChange={e => setAnnotImage(e.target.files?.[0] ?? null)} />
      </div>

      {error   && <p className="text-red-400 text-sm">{error}</p>}
      {success && <p className="text-emerald-400 text-sm">✓ Analysis imported successfully</p>}

      <button onClick={handleImport} disabled={loading}
        className="w-full bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg transition-colors text-sm flex items-center justify-center gap-2">
        {loading ? <><Loader2 size={15} className="animate-spin" /> Importing…</> : 'Import Analysis'}
      </button>

      {/* Preview imported */}
      {existingAnnotation && (
        <div className="mt-4 bg-gray-800/40 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-violet-400 mb-3 uppercase tracking-wide">Gemini Analysis</h4>
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown>{existingAnnotation}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}
