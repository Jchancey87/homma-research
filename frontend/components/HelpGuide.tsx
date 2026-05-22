'use client'

import { useState } from 'react'
import { HelpCircle, ChevronDown, ChevronUp, Layers, Zap, Flame, Eye } from 'lucide-react'

export default function HelpGuide() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="bg-emerald-500/5 dark:bg-emerald-500/10 border border-emerald-500/20 rounded-2xl overflow-hidden transition-all duration-300">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 text-left focus:outline-none"
      >
        <div className="flex items-center gap-2">
          <HelpCircle className="text-emerald-600 dark:text-emerald-400" size={18} />
          <div>
            <h3 className="font-semibold text-sm text-gray-900 dark:text-white">Workspace Quick Start Guide</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Click to expand tooltips, documentation, and page features.</p>
          </div>
        </div>
        <div className="p-1 rounded-lg hover:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 transition-colors">
          {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {isOpen && (
        <div className="p-4 md:p-6 border-t border-emerald-500/10 bg-white/50 dark:bg-gray-900/40 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 animate-fadeIn">
          
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 font-bold text-gray-900 dark:text-white text-xs uppercase tracking-wider">
              <Flame size={14} className="text-amber-500" />
              Screener & HOD
            </div>
            <p className="text-xs text-gray-650 dark:text-gray-400 leading-relaxed">
              The <span className="font-semibold">Live Gainer Screener</span> processes TradingView scans and enriches them with real-time Schwab quotes. Tickers near high-of-day are marked with <span className="text-amber-500 font-semibold">(HOD)</span>.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-1.5 font-bold text-gray-900 dark:text-white text-xs uppercase tracking-wider">
              <Zap size={14} className="text-emerald-500 animate-pulse" />
              Continuation
            </div>
            <p className="text-xs text-gray-650 dark:text-gray-400 leading-relaxed">
              <span className="font-semibold">AI Continuation Picks</span> runs nightly at 8:00 PM ET, screening for small-cap stocks with momentum setup and using LLM models to filter continuation candidates.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-1.5 font-bold text-gray-900 dark:text-white text-xs uppercase tracking-wider">
              <Layers size={14} className="text-sky-500" />
              Float & Sectors
            </div>
            <p className="text-xs text-gray-650 dark:text-gray-400 leading-relaxed">
              <span className="font-semibold">Float buckets</span> segment gainers to see where buying interest resides (e.g. micro-floats &lt; 5M). <span className="font-semibold">Sector Rotation</span> monitors industry group volume.
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-1.5 font-bold text-gray-900 dark:text-white text-xs uppercase tracking-wider">
              <Eye size={14} className="text-violet-500" />
              Observations
            </div>
            <p className="text-xs text-gray-650 dark:text-gray-400 leading-relaxed">
              Add custom logs, files, and patterns to individual tickers under the <span className="font-semibold">Observations</span> tab. Categorize notes by Bullish, Bearish, or Neutral sentiment.
            </p>
          </div>

        </div>
      )}
    </div>
  )
}
