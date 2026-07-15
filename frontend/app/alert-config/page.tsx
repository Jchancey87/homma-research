'use client'
import { useEffect, useState } from 'react'
import { getAlertConfig, updateAlertConfig, AlertConfig } from '@/lib/api'
import { Save, RefreshCw, Settings, Sliders, ToggleLeft, Activity } from 'lucide-react'

export default function AlertConfigPage() {
  const [config, setConfig] = useState<AlertConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    fetchConfig()
  }, [])

  async function fetchConfig() {
    try {
      setLoading(true)
      const data = await getAlertConfig()
      setConfig(data)
      setMessage(null)
    } catch (err) {
      console.error(err)
      setMessage({ type: 'error', text: 'Failed to load alert configuration.' })
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!config) return
    try {
      setSaving(true)
      setMessage(null)
      await updateAlertConfig(config)
      setMessage({ type: 'success', text: 'Alert configuration saved successfully.' })
    } catch (err) {
      console.error(err)
      setMessage({ type: 'error', text: 'Failed to save alert configuration.' })
    } finally {
      setSaving(false)
    }
  }

  function handleWeightChange(field: string, val: number) {
    setConfig((prev) => {
      if (!prev) return null
      return {
        ...prev,
        [field]: val
      }
    })
  }

  function handleToggleAlert(alertType: string) {
    setConfig((prev) => {
      if (!prev) return null
      return {
        ...prev,
        enabled_alerts: {
          ...prev.enabled_alerts,
          [alertType]: !prev.enabled_alerts[alertType]
        }
      }
    })
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <RefreshCw className="animate-spin text-gray-500" size={32} />
      </div>
    )
  }

  if (!config) {
    return (
      <div className="p-6 text-red-500 font-mono">
        Error: Could not load configuration values.
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 pb-4">
        <div className="flex items-center gap-2">
          <Settings className="text-[#00ff00]" size={28} />
          <h1 className="text-xl font-bold tracking-wider font-mono uppercase text-white">Alert System Control Panel</h1>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-[#00ff00]/10 hover:bg-[#00ff00]/25 text-[#00ff00] border border-[#00ff00]/45 font-mono text-sm uppercase font-bold transition-all disabled:opacity-50"
        >
          {saving ? <RefreshCw className="animate-spin" size={16} /> : <Save size={16} />}
          {saving ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>

      {message && (
        <div
          className={`p-4 border font-mono text-sm uppercase ${
            message.type === 'success'
              ? 'bg-emerald-950/20 text-[#00ff00] border-[#00ff00]/25'
              : 'bg-red-950/20 text-[#ff003c] border-[#ff003c]/25'
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left Column: Core Thresholds & Confluence Weights */}
        <div className="space-y-6">
          {/* Card 1: Core Thresholds */}
          <div className="bg-[#111] border border-[#262626] p-5 space-y-4">
            <div className="flex items-center gap-2 border-b border-gray-800 pb-2">
              <Sliders className="text-blue-400" size={18} />
              <h2 className="font-mono text-sm font-bold uppercase text-white">Screener Trigger Thresholds</h2>
            </div>
            
            {/* alert_min_pct_increase */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono text-gray-400">
                <span>Min Price Increase (Bucket 3):</span>
                <span className="text-blue-400 font-bold">{(config.alert_min_pct_increase * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0.01"
                max="0.10"
                step="0.01"
                value={config.alert_min_pct_increase}
                onChange={(e) => handleWeightChange('alert_min_pct_increase', parseFloat(e.target.value))}
                className="w-full accent-[#00ff00]"
              />
            </div>

            {/* alert_min_time_cooldown_mins */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono text-gray-400">
                <span>Min Alert Cooldown:</span>
                <span className="text-blue-400 font-bold">{config.alert_min_time_cooldown_mins} Minutes</span>
              </div>
              <input
                type="range"
                min="1"
                max="30"
                step="1"
                value={config.alert_min_time_cooldown_mins}
                onChange={(e) => handleWeightChange('alert_min_time_cooldown_mins', parseInt(e.target.value))}
                className="w-full accent-[#00ff00]"
              />
            </div>

            {/* Tier Thresholds */}
            <div className="grid grid-cols-2 gap-4 pt-2">
              <div className="space-y-1">
                <span className="block text-xs font-mono text-gray-400">Tier 1 Target Score:</span>
                <input
                  type="number"
                  min="50"
                  max="100"
                  value={config.tier_1_threshold}
                  onChange={(e) => handleWeightChange('tier_1_threshold', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
              <div className="space-y-1">
                <span className="block text-xs font-mono text-gray-400">Tier 2 Target Score:</span>
                <input
                  type="number"
                  min="20"
                  max="80"
                  value={config.tier_2_threshold}
                  onChange={(e) => handleWeightChange('tier_2_threshold', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
            </div>
          </div>

          {/* Card 2: Confluence Weights */}
          <div className="bg-[#111] border border-[#262626] p-5 space-y-4">
            <div className="flex items-center gap-2 border-b border-gray-800 pb-2">
              <Activity className="text-amber-400" size={18} />
              <h2 className="font-mono text-sm font-bold uppercase text-white">Confluence Scoring Weights</h2>
            </div>

            {/* Watchlist Weights */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <span className="block text-[11px] font-mono text-gray-400">Watchlist Presence:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.watchlist_presence_weight}
                  onChange={(e) => handleWeightChange('watchlist_presence_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
              <div className="space-y-1">
                <span className="block text-[11px] font-mono text-gray-400">Priority Tag Weight:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.watchlist_priority_tag_weight}
                  onChange={(e) => handleWeightChange('watchlist_priority_tag_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
            </div>

            {/* Catalyst Weights */}
            <div className="grid grid-cols-3 gap-2">
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">Catalyst Confirmed:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.catalyst_confirmed_weight}
                  onChange={(e) => handleWeightChange('catalyst_confirmed_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">Catalyst Spec:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.catalyst_speculative_weight}
                  onChange={(e) => handleWeightChange('catalyst_speculative_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">Catalyst Tech:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.catalyst_technical_weight}
                  onChange={(e) => handleWeightChange('catalyst_technical_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
            </div>

            {/* Float Weights */}
            <div className="grid grid-cols-3 gap-2">
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">Float Micro:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.float_micro_weight}
                  onChange={(e) => handleWeightChange('float_micro_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">Float Low:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.float_low_weight}
                  onChange={(e) => handleWeightChange('float_low_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">Float Mid:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.float_mid_weight}
                  onChange={(e) => handleWeightChange('float_mid_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
            </div>

            {/* Market Session Weights */}
            <div className="grid grid-cols-3 gap-2">
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">Session Regular:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.session_regular_weight}
                  onChange={(e) => handleWeightChange('session_regular_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">Session Pre:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.session_pre_weight}
                  onChange={(e) => handleWeightChange('session_pre_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">Session Post:</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.session_post_weight}
                  onChange={(e) => handleWeightChange('session_post_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
            </div>

            {/* RVOL Weights */}
            <div className="grid grid-cols-3 gap-2">
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">RVOL High (&gt;=5.0):</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.rvol_high_weight}
                  onChange={(e) => handleWeightChange('rvol_high_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">RVOL Mid (&gt;=3.0):</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.rvol_mid_weight}
                  onChange={(e) => handleWeightChange('rvol_mid_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
              <div className="space-y-1">
                <span className="block text-[10px] font-mono text-gray-400 truncate">RVOL Low (&gt;=1.5):</span>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={config.rvol_low_weight}
                  onChange={(e) => handleWeightChange('rvol_low_weight', parseInt(e.target.value))}
                  className="w-full bg-[#161616] border border-[#262626] p-2 text-white font-mono text-sm"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Toggle Alert Types */}
        <div className="space-y-6">
          <div className="bg-[#111] border border-[#262626] p-5 space-y-4">
            <div className="flex items-center gap-2 border-b border-gray-800 pb-2">
              <ToggleLeft className="text-purple-400" size={18} />
              <h2 className="font-mono text-sm font-bold uppercase text-white">Enable / Disable Alert Strategies</h2>
            </div>
            
            <div className="space-y-3 font-mono text-sm">
              {Object.keys(config.enabled_alerts || {}).map((alertType) => (
                <div key={alertType} className="flex items-center justify-between p-2.5 bg-[#161616] border border-[#262626]">
                  <span className="text-gray-300 text-xs tracking-wide">{alertType}</span>
                  <button
                    onClick={() => handleToggleAlert(alertType)}
                    className={`px-3 py-1 border text-[11px] uppercase font-bold transition-all ${
                      config.enabled_alerts[alertType]
                        ? 'bg-[#00ff00]/10 text-[#00ff00] border-[#00ff00]/30 hover:bg-[#00ff00]/20'
                        : 'bg-[#ff003c]/10 text-[#ff003c] border-[#ff003c]/30 hover:bg-[#ff003c]/20'
                    }`}
                  >
                    {config.enabled_alerts[alertType] ? 'Active' : 'Disabled'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
