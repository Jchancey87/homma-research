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

export interface PriceTick {
  symbol: string
  price: number
  volume?: number
  high?: number
  low?: number
  open?: number
}

const TOAST_TTL_MS       = 6_000
const FLASH_TTL_MS       = 200
const RECENT_ALERTS_CAP  = 50
const TOAST_STACK_CAP    = 5

// Shared WS module-level state
let sharedWs: WebSocket | null = null
let subscriberCount = 0
let isConnected = false
const messageListeners = new Set<(data: Record<string, unknown>) => void>()
const statusListeners = new Set<(status: boolean) => void>()
let reconnectTimer: NodeJS.Timeout | null = null

export const getWsUrl = () => {
  if (typeof window === 'undefined') return ''
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsHost = window.location.hostname
  return `${protocol}//${wsHost}:5000/ws/alerts`
}

function initWs() {
  if (typeof window === 'undefined') return
  if (sharedWs) return
  
  const url = getWsUrl()
  if (!url) return
  
  const ws = new WebSocket(url)
  sharedWs = ws
  
  ws.onopen = () => {
    console.log('WebSocket connected (shared)')
    isConnected = true
    statusListeners.forEach(l => l(true))
    if (reconnectTimer) clearTimeout(reconnectTimer)
  }
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      messageListeners.forEach(l => l(data))
    } catch {
      // Empty catch
    }
  }
  
  ws.onclose = () => {
    console.log('WebSocket disconnected (shared)')
    sharedWs = null
    isConnected = false
    statusListeners.forEach(l => l(false))
    if (subscriberCount > 0) {
      reconnectTimer = setTimeout(initWs, 5000)
    }
  }
  
  ws.onerror = (err) => {
    console.error('WebSocket error:', err)
    ws.close()
  }
}

export function useSharedWebSocket() {
  const [connected, setConnected] = useState(isConnected)
  
  useEffect(() => {
    subscriberCount++
    if (subscriberCount === 1) {
      initWs()
    }
    
    const handleStatus = (status: boolean) => setConnected(status)
    statusListeners.add(handleStatus)
    
    return () => {
      statusListeners.delete(handleStatus)
      subscriberCount--
      if (subscriberCount === 0) {
        if (sharedWs) {
          sharedWs.close()
          sharedWs = null
        }
        if (reconnectTimer) {
          clearTimeout(reconnectTimer)
        }
      }
    }
  }, [])
  
  const subscribe = useCallback((callback: (data: Record<string, unknown>) => void) => {
    messageListeners.add(callback)
    return () => { messageListeners.delete(callback) }
  }, [])
  
  return { connected, subscribe, ws: sharedWs }
}

interface UseAlertStreamResult {
  wsConnected:           boolean
  flashingTickers:       Record<string, boolean>
  toasts:                AlertItem[]
  dismissToast:          (id: string) => void
  audioChimesEnabled:    boolean
  setAudioChimesEnabled: (v: boolean) => void
  toastStackEnabled:     boolean
  setToastStackEnabled:  (v: boolean) => void
  prices:                Record<string, PriceTick>
  recentAlerts:          AlertItem[]
}

export function useAlertStream(): UseAlertStreamResult {
  const { connected, subscribe, ws } = useSharedWebSocket()
  const [audioChimesEnabled, setAudioChimesEnabled] = useState(false)
  const [toastStackEnabled,  setToastStackEnabled]  = useState(true)
  const [flashingTickers,    setFlashingTickers]    = useState<Record<string, boolean>>({})
  const [toasts,             setToasts]             = useState<AlertItem[]>([])
  const [prices,             setPrices]             = useState<Record<string, PriceTick>>({})
  const [recentAlerts,       setRecentAlerts]       = useState<AlertItem[]>([])

  const audioChimesEnabledRef = useRef(audioChimesEnabled)
  const toastStackEnabledRef  = useRef(toastStackEnabled)
  const audioCtxRef           = useRef<AudioContext | null>(null)
  const timeoutsRef           = useRef<NodeJS.Timeout[]>([])

  const safeTimeout = useCallback((fn: () => void, delay: number) => {
    const id = setTimeout(() => {
      timeoutsRef.current = timeoutsRef.current.filter(t => t !== id)
      fn()
    }, delay)
    timeoutsRef.current.push(id)
    return id
  }, [])

  useEffect(() => { audioChimesEnabledRef.current = audioChimesEnabled }, [audioChimesEnabled])
  useEffect(() => { toastStackEnabledRef.current  = toastStackEnabled  }, [toastStackEnabled])

  const playTierAudio = useCallback((tier: string) => {
    try {
      if (typeof window === 'undefined') return
      if (tier === 'Tier 3') return

      if (!audioCtxRef.current) {
        const AudioContextClass = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
        if (!AudioContextClass) return
        audioCtxRef.current = new AudioContextClass()
      }
      const ctx = audioCtxRef.current
      if (ctx.state === 'suspended') ctx.resume()

      const now = ctx.currentTime

      if (tier === 'Tier 1') {
        const playBeep = (startTime: number) => {
          const osc = ctx.createOscillator()
          const gain = ctx.createGain()
          osc.connect(gain)
          gain.connect(ctx.destination)
          osc.type = 'sine'
          osc.frequency.setValueAtTime(880, startTime)
          gain.gain.setValueAtTime(0.15, startTime)
          gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.1)
          osc.start(startTime)
          osc.stop(startTime + 0.12)
        }
        playBeep(now)
        playBeep(now + 0.15)
      } else if (tier === 'Tier 2') {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.type = 'sine'
        osc.frequency.setValueAtTime(554.37, now)
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
    const unsubscribe = subscribe((data: any) => {
      if (data.type === 'ping' || data.type === 'pong') return
      
      if (data.type === 'price' && data.symbol) {
        const sym = String(data.symbol)
        setPrices(prev => ({
          ...prev,
          [sym]: {
            symbol: sym,
            price: Number(data.price || 0),
            volume: Number(data.volume || 0),
            high: Number(data.high || 0),
            low: Number(data.low || 0),
            open: Number(data.open || 0)
          }
        }))
        return
      }
      
      if (data.type === 'alert' || data.alert_type) {
        const payload = data
        const ticker    = String(payload.symbol || 'UNKNOWN')
        const price     = Number(payload.price || payload.trigger_price || 0)
        const alertType = String(payload.alert_type || 'UNKNOWN')

        if (audioChimesEnabledRef.current) {
          playTierAudio(String(payload.priority_tier || 'Tier 3'))
        }

        if (toastStackEnabledRef.current) {
          const id = Math.random().toString(36).substring(2, 9)
          const newToast: AlertItem = {
            id, ticker, price, alertType,
            time: new Date().toLocaleTimeString(),
            priorityTier: payload.priority_tier ? String(payload.priority_tier) : undefined,
            strategyLabel: payload.strategy_label ? String(payload.strategy_label) : undefined,
            catalyst: payload.catalyst ? String(payload.catalyst) : undefined,
            confluenceScore: payload.priority_score ? Number(payload.priority_score) : undefined,
          }
          setToasts(prev => [newToast, ...prev].slice(0, TOAST_STACK_CAP))
          safeTimeout(() => {
            setToasts(prev => prev.filter(t => t.id !== id))
          }, TOAST_TTL_MS)
        }

        const recent: AlertItem = {
          id: Math.random().toString(36).substring(2, 9),
          ticker, price, alertType,
          time: new Date().toLocaleTimeString(),
          priorityTier: payload.priority_tier ? String(payload.priority_tier) : undefined,
          strategyLabel: payload.strategy_label ? String(payload.strategy_label) : undefined,
          catalyst: payload.catalyst ? String(payload.catalyst) : undefined,
          confluenceScore: payload.priority_score ? Number(payload.priority_score) : undefined,
          volume:     payload.volume ? Number(payload.volume) : undefined,
          rvol:       payload.rvol ? Number(payload.rvol) : undefined,
          gapPct:     payload.gap_pct ? Number(payload.gap_pct) : undefined,
          floatShares: payload.float_shares ? Number(payload.float_shares) : undefined,
        }
        setRecentAlerts(prev => [recent, ...prev].slice(0, RECENT_ALERTS_CAP))

        setFlashingTickers(prev => ({ ...prev, [ticker]: true }))
        safeTimeout(() => {
          setFlashingTickers(prev => ({ ...prev, [ticker]: false }))
        }, FLASH_TTL_MS)
      }
    })
    return () => { unsubscribe() }
  }, [subscribe, playTierAudio, safeTimeout])

  // Keep alive ping
  useEffect(() => {
    if (!connected) return
    const pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)
    return () => clearInterval(pingInterval)
  }, [connected, ws])

  useEffect(() => {
    return () => {
      timeoutsRef.current.forEach(clearTimeout)
      timeoutsRef.current = []
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(err => console.error("Error closing AudioContext:", err))
        audioCtxRef.current = null
      }
    }
  }, [])

  return {
    wsConnected: connected,
    flashingTickers,
    toasts,
    dismissToast: (id: string) => setToasts(prev => prev.filter(t => t.id !== id)),
    audioChimesEnabled,
    setAudioChimesEnabled,
    toastStackEnabled,
    setToastStackEnabled,
    prices,
    recentAlerts,
  }
}
