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
          className="pointer-events-auto bg-[#0b0b0f] border border-gray-800 rounded-xl p-4 shadow-2xl flex flex-col gap-2 hover:border-emerald-500/50 transition-all cursor-pointer transform hover:scale-[1.02] active:scale-[0.98] animate-in slide-in-from-bottom duration-200"
          onClick={() => {
            router.push(`/research?ticker=${toast.ticker}&date=${today}`)
            onDismiss(toast.id)
          }}
        >
          <div className="flex items-center justify-between">
            <span className="font-bold text-white font-mono flex items-center gap-1.5 text-sm">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              {toast.ticker}
            </span>
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
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400">
              Trigger: <span className="font-mono text-white font-semibold">${toast.price.toFixed(2)}</span>
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              {toast.alertType}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
