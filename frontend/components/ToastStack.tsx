'use client'

import { useRouter } from 'next/navigation'
import { X } from 'lucide-react'
import type { AlertItem } from './live-gainers/useAlertStream'

interface ToastStackProps {
  toasts: AlertItem[]
  onDismiss: (id: string) => void
}

/**
 * Fixed-position toast stack in the bottom-right corner. Each toast is
 * click-through to the research page for the alerted ticker. The parent
 * owns the alert queue and toast TTL; this component is purely presentational.
 */
export function ToastStack({ toasts, onDismiss }: ToastStackProps) {
  const router = useRouter()

  if (toasts.length === 0) return null

  const today = new Date().toISOString().slice(0, 10)

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-3 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto bg-[#0b0b0f] border rounded-xl p-4 shadow-2xl flex flex-col gap-2 hover:opacity-95 transition-all cursor-pointer transform hover:scale-[1.02] active:scale-[0.98] animate-in slide-in-from-bottom duration-200 ${
            toast.priorityTier === 'Tier 1'
              ? 'border-[#ff003c]/60 shadow-[#ff003c]/10'
              : toast.priorityTier === 'Tier 2'
              ? 'border-amber-500/50'
              : 'border-gray-800'
          }`}
          onClick={() => {
            router.push(`/research?ticker=${toast.ticker}&date=${today}`)
            onDismiss(toast.id)
          }}
        >
          <div className="flex items-center justify-between">
            <span className="font-bold text-white font-mono flex items-center gap-1.5 text-sm">
              <span className={`w-2 h-2 rounded-full ${
                toast.priorityTier === 'Tier 1' ? 'bg-[#ff003c] animate-pulse'
                : toast.priorityTier === 'Tier 2' ? 'bg-amber-400 animate-pulse'
                : 'bg-amber-500 animate-pulse'
              }`} />
              {toast.ticker}
            </span>
            <div className="flex items-center gap-1.5">
              {toast.priorityTier && (
                <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 border rounded-none ${
                  toast.priorityTier === 'Tier 1' ? 'text-[#ff003c] border-[#ff003c]/40 bg-red-950/20'
                  : toast.priorityTier === 'Tier 2' ? 'text-amber-400 border-amber-500/40 bg-amber-950/20'
                  : 'text-gray-600 border-[#333]'
                }`}>{toast.priorityTier}</span>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onDismiss(toast.id)
                }}
                className="text-gray-500 hover:text-white transition-colors p-0.5"
              >
                <X size={14} />
              </button>
            </div>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400">
              Trigger: <span className="font-mono text-white font-semibold">${toast.price.toFixed(2)}</span>
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              {toast.strategyLabel || toast.alertType}
            </span>
          </div>
          {toast.catalyst && toast.catalyst !== 'Technical / No News' && (
            <div className="text-[9px] font-mono text-[#00f0ff] truncate border-t border-[#1a1a1a] pt-1">
              📰 {toast.catalyst}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
