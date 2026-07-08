'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

export interface AlertItem {
  id:            string
  ticker:        string
  price:         number
  alertType:     string
  time:          string
  priorityTier?: string
  strategyLabel?: string
  catalyst?:     string
  confluenceScore?: number
  volume?:       number
  rvol?:         number
  gapPct?:       number
  floatShares?:  number
}

const TOAST_TTL_MS       = 6_000
const FLASH_TTL_MS       = 200
const RECENT_ALERTS_CAP  = 50
const TOAST_STACK_CAP    = 5

interface UseAlertStreamResult {
  flashingTickers:       Record<string, boolean>
  toasts:                AlertItem[]
  dismissToast:          (id: string) => void
  audioChimesEnabled:    boolean
  setAudioChimesEnabled: (v: boolean) => void
  toastStackEnabled:     boolean
  setToastStackEnabled:  (v: boolean) => void
}

/**
 * Subscribe to /api/alerts/stream SSE. Owns the audio chime toggle, the
 * toast-stack toggle, the flashing-ticker map, and the toast queue.
 *
 * SSE leak fix: the `eventSource.close()` call in the effect cleanup
 * guarantees the connection is torn down on unmount / dep change / strict-
 * mode double-invoke, eliminating the ghost /api/alerts/stream connections
 * previously observable after route changes.
 */
export function useAlertStream(): UseAlertStreamResult {
  const [audioChimesEnabled, setAudioChimesEnabled] = useState(false)
  const [toastStackEnabled,  setToastStackEnabled]  = useState(true)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [recentAlerts,       setRecentAlerts]       = useState<AlertItem[]>([])
  const [flashingTickers,    setFlashingTickers]    = useState<Record<string, boolean>>({})
  const [toasts,             setToasts]             = useState<AlertItem[]>([])

  const audioChimesEnabledRef = useRef(audioChimesEnabled)
  const toastStackEnabledRef  = useRef(toastStackEnabled)
  const audioCtxRef           = useRef<AudioContext | null>(null)

  useEffect(() => { audioChimesEnabledRef.current = audioChimesEnabled }, [audioChimesEnabled])
  useEffect(() => { toastStackEnabledRef.current  = toastStackEnabled  }, [toastStackEnabled])

  const playTierAudio = useCallback((tier: string) => {
    try {
      if (typeof window === 'undefined') return
      if (tier === 'Tier 3') return // Tier 3 is silent

      if (!audioCtxRef.current) {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
        if (!AudioContextClass) return
        audioCtxRef.current = new AudioContextClass()
      }
      const ctx = audioCtxRef.current
      if (ctx.state === 'suspended') ctx.resume()

      const now = ctx.currentTime

      if (tier === 'Tier 1') {
        // Double-beep: beep 1 -> brief silence -> beep 2
        const playBeep = (startTime: number) => {
          const osc = ctx.createOscillator()
          const gain = ctx.createGain()
          osc.connect(gain)
          gain.connect(ctx.destination)
          osc.type = 'sine'
          osc.frequency.setValueAtTime(880, startTime) // A5 note
          gain.gain.setValueAtTime(0.15, startTime)
          gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.1)
          osc.start(startTime)
          osc.stop(startTime + 0.12)
        }
        playBeep(now)
        playBeep(now + 0.15)
      } else if (tier === 'Tier 2') {
        // Single warm tone: 554.37Hz sine wave decaying smoothly
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.type = 'sine'
        osc.frequency.setValueAtTime(554.37, now) // C#5 warm tone
        gain.gain.setValueAtTime(0.12, now)
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4)
        osc.start(now)
        osc.stop(now + 0.42)
      }
    } catch (e) {
      console.error('Web Audio error:', e)
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const eventSource = new EventSource('/api/alerts/stream')

    eventSource.onmessage = (event) => {
      try {
        const payload   = JSON.parse(event.data) as {
          symbol: string
          price:  number
          alert_type: string
          volume?: number
          rvol?:   number
          gap_pct?: number
          float_shares?: number
          priority_tier?: string
          priority_score?: number
          strategy_label?: string
          catalyst?: string
        }
        const ticker    = payload.symbol
        const price     = payload.price
        const alertType = payload.alert_type

        if (audioChimesEnabledRef.current) {
          playTierAudio(payload.priority_tier || 'Tier 3')
        }

        if (toastStackEnabledRef.current) {
          const id = Math.random().toString(36).substring(2, 9)
          const newToast: AlertItem = {
            id, ticker, price, alertType,
            time: new Date().toLocaleTimeString(),
            priorityTier: payload.priority_tier,
            strategyLabel: payload.strategy_label,
            catalyst: payload.catalyst,
            confluenceScore: payload.priority_score,
          }
          setToasts(prev => [newToast, ...prev].slice(0, TOAST_STACK_CAP))
          setTimeout(() => {
            setToasts(prev => prev.filter(t => t.id !== id))
          }, TOAST_TTL_MS)
        }

        const recent: AlertItem = {
          id: Math.random().toString(36).substring(2, 9),
          ticker, price, alertType,
          time: new Date().toLocaleTimeString(),
          priorityTier: payload.priority_tier,
          strategyLabel: payload.strategy_label,
          catalyst: payload.catalyst,
          confluenceScore: payload.priority_score,
          volume:     payload.volume,
          rvol:       payload.rvol,
          gapPct:     payload.gap_pct,
          floatShares: payload.float_shares,
        }
        setRecentAlerts(prev => [recent, ...prev].slice(0, RECENT_ALERTS_CAP))

        setFlashingTickers(prev => ({ ...prev, [ticker]: true }))
        setTimeout(() => {
          setFlashingTickers(prev => ({ ...prev, [ticker]: false }))
        }, FLASH_TTL_MS)
      } catch (err) {
        console.error('Failed to process SSE message:', err)
      }
    }

    eventSource.onerror = (err) => {
      console.error('SSE Stream Error:', err)
    }

    return () => {
      // Leak fix: always close the connection on unmount / dep change /
      // strict-mode double-invoke. Without this, ghost /api/alerts/stream
      // connections leak across route changes.
      eventSource.close()
    }
  }, [playTierAudio])

  return {
    flashingTickers,
    toasts,
    dismissToast: (id: string) => setToasts(prev => prev.filter(t => t.id !== id)),
    audioChimesEnabled,
    setAudioChimesEnabled,
    toastStackEnabled,
    setToastStackEnabled,
  }
}
