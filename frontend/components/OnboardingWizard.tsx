'use client'

import { useState, useEffect } from 'react'
import { Check, Rocket, Compass, ChevronRight, ChevronLeft } from 'lucide-react'

export default function OnboardingWizard() {
  const [isMounted, setIsMounted] = useState(false)
  const [visible, setVisible] = useState(false)
  const [step, setStep] = useState(1)

  // User selections
  const [tradingTypes, setTradingTypes] = useState<string[]>([])
  const [platforms, setPlatforms] = useState<string[]>([])
  const [tools, setTools] = useState<string[]>([])

  useEffect(() => {
    setIsMounted(true)
    const onboarded = localStorage.getItem('trading-journal-onboarded')
    if (onboarded !== 'true') {
      setVisible(true)
    }
  }, [])

  if (!isMounted || !visible) return null

  const handleComplete = () => {
    localStorage.setItem('trading-journal-onboarded', 'true')
    // Save settings if needed
    localStorage.setItem('tj-pref-types', JSON.stringify(tradingTypes))
    localStorage.setItem('tj-pref-platforms', JSON.stringify(platforms))
    localStorage.setItem('tj-pref-tools', JSON.stringify(tools))
    setVisible(false)
  }

  const toggleSelect = (val: string, list: string[], setList: (arr: string[]) => void) => {
    if (list.includes(val)) {
      setList(list.filter(x => x !== val))
    } else {
      setList([...list, val])
    }
  }

  const steps = [
    // Step 1: Welcome
    {
      title: 'Welcome to TradeJournal',
      desc: 'Accelerate your trading lifecycle with institutional-grade data, charts logging, and automated screener workflows.',
      icon: Rocket,
    },
    // Step 2: Types
    {
      title: 'Asset Classes',
      desc: 'What markets do you actively trade or analyze?',
      options: ['Stocks', 'Crypto', 'Futures', 'Options'],
      selected: tradingTypes,
      setSelected: setTradingTypes,
    },
    // Step 3: Platforms
    {
      title: 'Trading Platforms',
      desc: 'Which brokerages or platforms do you connect/use?',
      options: ['Schwab API', 'Robinhood', 'Binance', 'Interactive Brokers', 'Manual Entry Only'],
      selected: platforms,
      setSelected: setPlatforms,
    },
    // Step 4: Tools
    {
      title: 'Workspace Modules',
      desc: 'Select the primary tools you want enabled in your command center:',
      options: ['Real-time Gainer Screener', 'AI Continuation Picks', 'Chart Annotations', 'Observations Feed', 'Market Breadth Analysis'],
      selected: tools,
      setSelected: setTools,
    },
    // Step 5: Ready
    {
      title: 'Command Center Configured!',
      desc: 'Your custom view is tailored. You are ready to log trades, review nightly reports, and track momentum.',
      icon: Compass,
    }
  ]

  const current = steps[step - 1]
  const Icon = current.icon

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-3xl overflow-hidden shadow-2xl transition-all duration-300 transform scale-100 flex flex-col">
        
        {/* Step progress bar */}
        <div className="w-full bg-gray-100 dark:bg-gray-800 h-1.5 flex">
          {steps.map((_, idx) => (
            <div
              key={idx}
              className={`flex-1 h-full transition-all duration-300 ${
                idx < step ? 'bg-emerald-500' : 'bg-transparent'
              }`}
            />
          ))}
        </div>

        {/* Content Area */}
        <div className="p-6 md:p-8 flex-1 flex flex-col items-center text-center">
          {Icon ? (
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center mb-6 animate-bounce">
              <Icon size={32} />
            </div>
          ) : (
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center mb-6 font-bold text-xl">
              {step}
            </div>
          )}

          <h2 className="text-xl md:text-2xl font-bold text-gray-900 dark:text-white tracking-tight">
            {current.title}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-2 max-w-md">
            {current.desc}
          </p>

          {/* Options List */}
          {current.options && current.selected && current.setSelected && (
            <div className="grid grid-cols-1 gap-2.5 w-full mt-6 text-left">
              {current.options.map(opt => {
                const isSelected = current.selected.includes(opt)
                return (
                  <button
                    key={opt}
                    onClick={() => toggleSelect(opt, current.selected!, current.setSelected!)}
                    className={`flex items-center justify-between w-full px-4 py-3 rounded-xl border transition-all ${
                      isSelected
                        ? 'bg-emerald-500/10 border-emerald-500 text-emerald-600 dark:text-emerald-400 font-semibold'
                        : 'bg-gray-50 dark:bg-gray-800/40 border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-300 hover:border-gray-300 dark:hover:border-gray-700'
                    }`}
                  >
                    <span className="text-sm">{opt}</span>
                    <div
                      className={`w-5 h-5 rounded-md border flex items-center justify-center transition-all ${
                        isSelected
                          ? 'bg-emerald-500 border-emerald-500 text-black'
                          : 'border-gray-300 dark:border-gray-700 bg-transparent'
                      }`}
                    >
                      {isSelected && <Check size={12} strokeWidth={3} />}
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="p-6 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-150 dark:border-gray-850 flex items-center justify-between">
          <button
            onClick={() => setStep(v => Math.max(1, v - 1))}
            disabled={step === 1}
            className="flex items-center gap-1 text-sm font-medium text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-white transition-colors disabled:opacity-30 disabled:pointer-events-none"
          >
            <ChevronLeft size={16} /> Back
          </button>

          <span className="text-xs text-gray-400 dark:text-gray-500 font-semibold uppercase tracking-wider">
            Step {step} of {steps.length}
          </span>

          {step < steps.length ? (
            <button
              onClick={() => setStep(v => Math.min(steps.length, v + 1))}
              className="flex items-center gap-1 px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-black text-sm font-bold rounded-xl transition-colors shadow-lg shadow-emerald-500/10"
            >
              Continue <ChevronRight size={16} />
            </button>
          ) : (
            <button
              onClick={handleComplete}
              className="px-5 py-2 bg-emerald-500 hover:bg-emerald-400 text-black text-sm font-bold rounded-xl transition-colors shadow-lg shadow-emerald-500/10"
            >
              Launch Command Center
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
