'use client'
import { VALID_TAGS, PatternTag } from '@/lib/geminiPrompt'

interface Props {
  selected: PatternTag[]
  onChange: (tags: PatternTag[]) => void
}

const TAG_COLORS: Record<string, string> = {
  'gap-and-hold':           'emerald',
  'gap-and-fade':           'red',
  'breakout-clean':         'sky',
  'breakout-whipsaw':       'orange',
  'multi-day-runner':       'violet',
  'sector-sympathy':        'yellow',
  'news-fresh':             'teal',
  'news-stale':             'gray',
  'halt-triggered':         'pink',
  'failed-follow-through':  'rose',
}

const COLOR_CLASSES: Record<string, string> = {
  emerald: 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-450 border-emerald-250 dark:border-emerald-500/30 hover:bg-emerald-100 dark:hover:bg-emerald-500/20',
  red:     'bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/30 hover:bg-red-100 dark:hover:bg-red-500/20',
  sky:     'bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-200 dark:border-sky-500/30 hover:bg-sky-100 dark:hover:bg-sky-500/20',
  orange:  'bg-orange-50 dark:bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-200 dark:border-orange-500/30 hover:bg-orange-100 dark:hover:bg-orange-500/20',
  violet:  'bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-400 border-violet-200 dark:border-violet-500/30 hover:bg-violet-100 dark:hover:bg-violet-500/20',
  yellow:  'bg-yellow-50 dark:bg-yellow-500/10 text-yellow-705 dark:text-yellow-400 border-yellow-200 dark:border-yellow-500/30 hover:bg-yellow-100 dark:hover:bg-yellow-500/20',
  teal:    'bg-teal-50 dark:bg-teal-500/10 text-teal-700 dark:text-teal-400 border-teal-200 dark:border-teal-500/30 hover:bg-teal-100 dark:hover:bg-teal-500/20',
  gray:    'bg-gray-150 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-750',
  pink:    'bg-pink-50 dark:bg-pink-500/10 text-pink-705 dark:text-pink-400 border-pink-200 dark:border-pink-500/30 hover:bg-pink-100 dark:hover:bg-pink-500/20',
  rose:    'bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-200 dark:border-rose-500/30 hover:bg-rose-100 dark:hover:bg-rose-500/20',
}

function colorClass(tag: string, active: boolean) {
  const c = TAG_COLORS[tag] ?? 'gray'
  return active
    ? COLOR_CLASSES[c]
    : 'bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-800 hover:border-gray-350 dark:hover:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-850'
}

export default function TagSelector({ selected, onChange }: Props) {
  const toggle = (tag: PatternTag) => {
    onChange(
      selected.includes(tag) ? selected.filter(t => t !== tag) : [...selected, tag]
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {VALID_TAGS.map(tag => (
        <button
          key={tag}
          type="button"
          onClick={() => toggle(tag)}
          className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-all ${colorClass(tag, selected.includes(tag))}`}
        >
          {tag}
        </button>
      ))}
    </div>
  )
}
