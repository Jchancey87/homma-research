'use client'
import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X } from 'lucide-react'
import TagSelector from './TagSelector'
import { uploadChart } from '@/lib/api'
import { PatternTag } from '@/lib/geminiPrompt'

interface Props {
  onSuccess?: (id: number) => void
}

const SETUP_TYPES = ['gap-up', 'gap-down', 'breakout', 'breakdown', 'continuation', 'reversal']
const TIMEFRAMES  = ['1m', '2m', '5m', '15m', '30m', '1h', 'daily']

export default function ChartUpload({ onSuccess }: Props) {
  const [file, setFile]       = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [ticker, setTicker]   = useState('')
  const [date, setDate]       = useState('')
  const [timeframe, setTimeframe] = useState('')
  const [setupType, setSetupType] = useState('')
  const [score, setScore]     = useState<number>(5)
  const [notes, setNotes]     = useState('')
  const [tags, setTags]       = useState<PatternTag[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const onDrop = useCallback((accepted: File[]) => {
    const f = accepted[0]
    if (!f) return
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setSuccess(false)
    setError(null)
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { 'image/*': ['.png', '.jpg', '.jpeg', '.webp'] }, maxFiles: 1,
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file || !ticker || !date) {
      setError('Image, ticker, and date are required.')
      return
    }
    setLoading(true); setError(null)
    try {
      const fd = new FormData()
      fd.append('image', file)
      fd.append('ticker', ticker.toUpperCase())
      fd.append('capture_date', date)
      fd.append('timeframe', timeframe)
      fd.append('setup_type', setupType)
      fd.append('cleanliness_score', String(score))
      fd.append('notes', notes)
      fd.append('tags', JSON.stringify(tags))
      const res = await uploadChart(fd)
      setSuccess(true)
      onSuccess?.(res.id)
      // Reset
      setFile(null); setPreview(null); setTicker(''); setDate('')
      setTimeframe(''); setSetupType(''); setScore(5); setNotes(''); setTags([])
    } catch (e) {
      const err = e as { response?: { data?: { error?: string } } }
      setError(err?.response?.data?.error ?? 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors
          ${isDragActive
            ? 'border-emerald-500 bg-emerald-500/5 dark:bg-emerald-500/10'
            : 'border-gray-300 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-500 bg-gray-50/50 dark:bg-gray-900/50'}`}
      >
        <input {...getInputProps()} />
        {preview ? (
          <div className="relative inline-block">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="preview" className="max-h-48 rounded-lg mx-auto" />
            <button type="button" onClick={e => { e.stopPropagation(); setFile(null); setPreview(null) }}
              className="absolute -top-2 -right-2 bg-red-650 text-white rounded-full p-1 shadow-md hover:bg-red-700 transition-colors">
              <X size={14} />
            </button>
          </div>
        ) : (
          <div className="space-y-2 text-gray-500 dark:text-gray-400">
            <Upload className="mx-auto text-emerald-500 dark:text-emerald-400" size={32} />
            <p className="text-sm font-medium">Drop chart screenshot here or click to browse</p>
            <p className="text-xs text-gray-450 dark:text-gray-500">PNG, JPG, WEBP — max 10 MB</p>
          </div>
        )}
      </div>

      {/* Fields */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-505 dark:text-gray-405 mb-1 block font-medium">Ticker *</label>
          <input value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())}
            placeholder="NVDA" maxLength={10}
            className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-905 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500" />
        </div>
        <div>
          <label className="text-xs text-gray-505 dark:text-gray-405 mb-1 block font-medium">Date *</label>
          <input type="date" value={date} onChange={e => setDate(e.target.value)}
            className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-905 dark:text-white focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500" />
        </div>
        <div>
          <label className="text-xs text-gray-505 dark:text-gray-405 mb-1 block font-medium">Timeframe</label>
          <select value={timeframe} onChange={e => setTimeframe(e.target.value)}
            className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-905 dark:text-white focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500">
            <option value="" className="text-gray-500 dark:text-gray-400">— select —</option>
            {TIMEFRAMES.map(t => <option key={t} value={t} className="text-gray-900 dark:text-white">{t}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-505 dark:text-gray-405 mb-1 block font-medium">Setup Type</label>
          <select value={setupType} onChange={e => setSetupType(e.target.value)}
            className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-905 dark:text-white focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500">
            <option value="" className="text-gray-500 dark:text-gray-400">— select —</option>
            {SETUP_TYPES.map(s => <option key={s} value={s} className="text-gray-900 dark:text-white">{s}</option>)}
          </select>
        </div>
      </div>

      {/* Cleanliness score */}
      <div>
        <label className="text-xs text-gray-505 dark:text-gray-405 mb-1 block font-medium">
          Cleanliness Score: <span className="text-gray-900 dark:text-white font-bold">{score}/10</span>
        </label>
        <input type="range" min={1} max={10} value={score} onChange={e => setScore(Number(e.target.value))}
          className="w-full accent-emerald-500 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none h-2" />
      </div>

      {/* Tags */}
      <div>
        <label className="text-xs text-gray-505 dark:text-gray-405 mb-2 block font-medium">Pattern Tags</label>
        <TagSelector selected={tags} onChange={setTags} />
      </div>

      {/* Notes */}
      <div>
        <label className="text-xs text-gray-505 dark:text-gray-405 mb-1 block font-medium">Notes</label>
        <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3}
          placeholder="Trade notes, observations…"
          className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-905 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 resize-none" />
      </div>

      {error   && <p className="text-red-500 dark:text-red-400 text-sm font-medium">{error}</p>}
      {success && <p className="text-emerald-600 dark:text-emerald-450 text-sm font-medium">✓ Chart uploaded successfully</p>}

      <button type="submit" disabled={loading}
        className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold py-2.5 rounded-xl transition-colors text-sm shadow-md shadow-emerald-650/10">
        {loading ? 'Uploading…' : 'Upload Chart'}
      </button>
    </form>
  )
}
