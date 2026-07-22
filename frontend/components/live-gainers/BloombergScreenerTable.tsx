'use client'

import React, { useState, useEffect } from 'react'
import { ArrowUpRight, ArrowDownRight, Activity, Zap, Filter } from 'lucide-react'
import { fmtVol } from '@/lib/format'

export interface ScreenerRowData {
  rank: number
  ticker: string
  name?: string
  price: number
  changePct: number
  rvol: number
  floatShares: number
  volume: number
  hodDistPct?: number
  spreadCents?: number
  status: 'SQUEEZE' | 'RUNNER' | 'HALTED' | 'PULLBACK' | 'NORMAL'
  lastTickDir?: 'up' | 'down' | 'flat'
  lastTickTs?: number
}

const SAMPLE_SCREENER_DATA: ScreenerRowData[] = [
  { rank: 1, ticker: 'NVDA', name: 'NVIDIA Corp', price: 128.45, changePct: 14.82, rvol: 34.2, floatShares: 24500000, volume: 84200000, hodDistPct: 0.12, status: 'SQUEEZE' },
  { rank: 2, ticker: 'SOUN', name: 'SoundHound AI', price: 6.78, changePct: 28.40, rvol: 128.5, floatShares: 8900000, volume: 45100000, hodDistPct: 0.00, status: 'SQUEEZE' },
  { rank: 3, ticker: 'TSLA', name: 'Tesla Inc', price: 254.10, changePct: 11.25, rvol: 12.4, floatShares: 318000000, volume: 92400000, hodDistPct: 0.85, status: 'RUNNER' },
  { rank: 4, ticker: 'BBAI', name: 'BigBear.ai', price: 3.42, changePct: 22.14, rvol: 85.0, floatShares: 14200000, volume: 28900000, hodDistPct: 0.30, status: 'RUNNER' },
  { rank: 5, ticker: 'SMCI', name: 'Super Micro', price: 485.60, changePct: -4.35, rvol: 18.2, floatShares: 52000000, volume: 15600000, hodDistPct: 3.10, status: 'PULLBACK' },
  { rank: 6, ticker: 'PLTR', name: 'Palantir Tech', price: 28.95, changePct: 10.15, rvol: 9.8, floatShares: 210000000, volume: 61300000, hodDistPct: 0.45, status: 'RUNNER' },
  { rank: 7, ticker: 'HOLO', name: 'MicroCloud', price: 2.15, changePct: 45.27, rvol: 412.0, floatShares: 3100000, volume: 112000000, hodDistPct: 0.05, status: 'SQUEEZE' },
  { rank: 8, ticker: 'AMD', name: 'Advanced Micro', price: 162.30, changePct: -2.10, rvol: 5.4, floatShares: 161000000, volume: 38400000, hodDistPct: 4.20, status: 'PULLBACK' },
]

export default function BloombergScreenerTable({
  initialData = SAMPLE_SCREENER_DATA,
  enableSimulatedTicks = true,
}: {
  initialData?: ScreenerRowData[]
  enableSimulatedTicks?: boolean
}) {
  const [rows, setRows] = useState<ScreenerRowData[]>(initialData)
  const [density, setDensity] = useState<'compact' | 'ultra' | 'normal'>('compact')
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState<'changePct' | 'rvol' | 'price' | 'volume'>('changePct')
  const [sortDesc, setSortDesc] = useState(true)

  // Real-time tick simulator mimicking Bloomberg Level 1 WebSocket updates
  useEffect(() => {
    if (!enableSimulatedTicks) return

    const interval = setInterval(() => {
      setRows(prevRows => {
        const targetIndex = Math.floor(Math.random() * prevRows.length)
        return prevRows.map((row, idx) => {
          if (idx !== targetIndex) return row
          const deltaPct = (Math.random() - 0.48) * 0.4
          const newPrice = Math.max(0.1, Number((row.price * (1 + deltaPct / 100)).toFixed(2)))
          const newChangePct = Number((row.changePct + deltaPct).toFixed(2))
          const tickDir = deltaPct >= 0 ? 'up' : 'down'
          return {
            ...row,
            price: newPrice,
            changePct: newChangePct,
            lastTickDir: tickDir,
            lastTickTs: Date.now(),
          }
        })
      })
    }, 1800)

    return () => clearInterval(interval)
  }, [enableSimulatedTicks])

  const filteredRows = rows
    .filter(r => r.ticker.toLowerCase().includes(searchTerm.toLowerCase()) || (r.name && r.name.toLowerCase().includes(searchTerm.toLowerCase())))
    .sort((a, b) => {
      const valA = a[sortBy] ?? 0
      const valB = b[sortBy] ?? 0
      return sortDesc ? valB - valA : valA - valB
    })

  const handleSort = (field: 'changePct' | 'rvol' | 'price' | 'volume') => {
    if (sortBy === field) {
      setSortDesc(!sortDesc)
    } else {
      setSortBy(field)
      setSortDesc(true)
    }
  }

  // Row padding based on density preference
  const pyClass = density === 'ultra' ? 'py-[3px]' : density === 'compact' ? 'py-[5px]' : 'py-[8px]'

  return (
    <div className="w-full bg-[#0D0E12] text-[#E0E3EB] border border-[#1E222D] shadow-2xl font-sans">
      {/* Bloomberg Terminal Top Header Controls */}
      <div className="flex flex-wrap items-center justify-between px-3 py-2 bg-[#131722] border-b border-[#1E222D] gap-2">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#089981]" />
          <span className="font-ticker text-xs tracking-wider text-[#FFFFFF] font-bold">
            MOMENTUM SCREENER <span className="text-[#089981] font-mono">[TERMINAL DENSITY]</span>
          </span>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          <div className="flex items-center bg-[#0D0E12] border border-[#1E222D] px-2 py-0.5">
            <Filter className="w-3.0 h-3.0 text-[#9B9EAE] mr-1.5" />
            <input
              type="text"
              placeholder="SEARCH TICKER..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="bg-transparent text-[#E0E3EB] placeholder-[#505668] focus:outline-none w-28 uppercase text-[11px]"
            />
          </div>

          <div className="flex items-center border border-[#1E222D] bg-[#0D0E12]">
            <button
              onClick={() => setDensity('ultra')}
              className={`px-2 py-0.5 text-[10px] uppercase font-semibold ${density === 'ultra' ? 'bg-[#1E2433] text-[#FFFFFF]' : 'text-[#9B9EAE]'}`}
            >
              4px Ultra
            </button>
            <button
              onClick={() => setDensity('compact')}
              className={`px-2 py-0.5 text-[10px] uppercase font-semibold border-l border-[#1E222D] ${density === 'compact' ? 'bg-[#1E2433] text-[#FFFFFF]' : 'text-[#9B9EAE]'}`}
            >
              5px Compact
            </button>
            <button
              onClick={() => setDensity('normal')}
              className={`px-2 py-0.5 text-[10px] uppercase font-semibold border-l border-[#1E222D] ${density === 'normal' ? 'bg-[#1E2433] text-[#FFFFFF]' : 'text-[#9B9EAE]'}`}
            >
              8px Normal
            </button>
          </div>
        </div>
      </div>

      {/* Main High-Density Financial Table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-xs font-mono select-none">
          <thead>
            <tr className="bg-[#131722] text-[#9B9EAE] border-b border-[#1E222D] text-[10px] font-sans uppercase tracking-wider">
              <th className="text-left px-2 py-1.5 w-10">#</th>
              <th className="text-left px-2.5 py-1.5">Ticker</th>
              <th className="text-right px-2.5 py-1.5 cursor-pointer hover:text-[#FFFFFF]" onClick={() => handleSort('price')}>
                Price {sortBy === 'price' && (sortDesc ? '▼' : '▲')}
              </th>
              <th className="text-right px-2.5 py-1.5 cursor-pointer hover:text-[#FFFFFF]" onClick={() => handleSort('changePct')}>
                % Change {sortBy === 'changePct' && (sortDesc ? '▼' : '▲')}
              </th>
              <th className="text-right px-2.5 py-1.5 cursor-pointer hover:text-[#FFFFFF]" onClick={() => handleSort('rvol')}>
                RVOL {sortBy === 'rvol' && (sortDesc ? '▼' : '▲')}
              </th>
              <th className="text-right px-2.5 py-1.5 cursor-pointer hover:text-[#FFFFFF]" onClick={() => handleSort('volume')}>
                Volume {sortBy === 'volume' && (sortDesc ? '▼' : '▲')}
              </th>
              <th className="text-right px-2.5 py-1.5">Float</th>
              <th className="text-right px-2.5 py-1.5">HOD Dist</th>
              <th className="text-center px-2.5 py-1.5">Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map(row => {
              const isGainer = row.changePct >= 0
              const isRecentTick = row.lastTickTs && Date.now() - row.lastTickTs < 1200
              const tickFlashBg = isRecentTick
                ? row.lastTickDir === 'up'
                  ? 'bg-[#089981]/25'
                  : 'bg-[#F23645]/25'
                : ''

              return (
                <tr
                  key={row.ticker}
                  className={`border-b border-[#1E222D] hover:bg-[#1E2433] transition-colors duration-100 ${tickFlashBg}`}
                >
                  {/* Rank */}
                  <td className={`px-2 ${pyClass} text-left text-[#505668] text-[11px] font-tabular`}>
                    {row.rank}
                  </td>

                  {/* Ticker Symbol & Name */}
                  <td className={`px-2.5 ${pyClass} text-left`}>
                    <div className="flex items-center gap-1.5">
                      <span className="font-ticker text-[13px] text-[#FFFFFF] tracking-[0.03em] font-bold">
                        {row.ticker}
                      </span>
                      {row.name && (
                        <span className="text-[10px] text-[#505668] font-sans truncate max-w-[80px] hidden sm:inline">
                          {row.name}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Dynamic Price Cell with Tabular Figures */}
                  <td
                    className={`px-2.5 ${pyClass} text-right font-tabular text-[12px] font-medium text-[#FFFFFF]`}
                    style={{ fontVariantNumeric: 'tabular-nums lining-nums' }}
                  >
                    ${row.price.toFixed(2)}
                  </td>

                  {/* Day % Change Cell */}
                  <td
                    className={`px-2.5 ${pyClass} text-right font-tabular text-[12px] font-bold ${
                      isGainer ? 'text-[#089981]' : 'text-[#F23645]'
                    }`}
                    style={{ fontVariantNumeric: 'tabular-nums lining-nums' }}
                  >
                    <div className="flex items-center justify-end gap-0.5">
                      {isGainer ? (
                        <ArrowUpRight className="w-3 h-3 text-[#089981] inline" />
                      ) : (
                        <ArrowDownRight className="w-3 h-3 text-[#F23645] inline" />
                      )}
                      <span>{isGainer ? `+${row.changePct.toFixed(2)}%` : `${row.changePct.toFixed(2)}%`}</span>
                    </div>
                  </td>

                  {/* RVOL */}
                  <td
                    className={`px-2.5 ${pyClass} text-right font-tabular text-[12px] ${
                      row.rvol >= 100
                        ? 'text-[#089981] font-bold'
                        : row.rvol >= 20
                        ? 'text-[#089981]'
                        : 'text-[#9B9EAE]'
                    }`}
                    style={{ fontVariantNumeric: 'tabular-nums lining-nums' }}
                  >
                    {row.rvol.toFixed(1)}x
                  </td>

                  {/* Volume */}
                  <td
                    className={`px-2.5 ${pyClass} text-right font-tabular text-[12px] text-[#E0E3EB]`}
                    style={{ fontVariantNumeric: 'tabular-nums lining-nums' }}
                  >
                    {fmtVol(row.volume)}
                  </td>

                  {/* Float Shares */}
                  <td
                    className={`px-2.5 ${pyClass} text-right font-tabular text-[11px] ${
                      row.floatShares < 10000000
                        ? 'text-[#F59E0B] font-semibold'
                        : 'text-[#9B9EAE]'
                    }`}
                    style={{ fontVariantNumeric: 'tabular-nums lining-nums' }}
                  >
                    {fmtVol(row.floatShares)}
                  </td>

                  {/* Distance from HOD */}
                  <td
                    className={`px-2.5 ${pyClass} text-right font-tabular text-[11px] ${
                      (row.hodDistPct ?? 99) <= 0.1
                        ? 'text-[#089981] font-bold underline underline-offset-2 decoration-[#089981]/40'
                        : 'text-[#9B9EAE]'
                    }`}
                    style={{ fontVariantNumeric: 'tabular-nums lining-nums' }}
                  >
                    {row.hodDistPct !== undefined ? `${row.hodDistPct.toFixed(2)}%` : '—'}
                  </td>

                  {/* Status Badge */}
                  <td className={`px-2.5 ${pyClass} text-center`}>
                    <span
                      className={`badge-terminal text-[9px] px-1.5 py-0.5 border ${
                        row.status === 'SQUEEZE'
                          ? 'bg-[#089981]/15 text-[#089981] border-[#089981]/30 font-bold'
                          : row.status === 'RUNNER'
                          ? 'bg-[#2979FF]/15 text-[#2979FF] border-[#2979FF]/30 font-semibold'
                          : row.status === 'PULLBACK'
                          ? 'bg-[#F23645]/15 text-[#F23645] border-[#F23645]/30'
                          : 'bg-[#181C28] text-[#9B9EAE] border-[#1E222D]'
                      }`}
                    >
                      {row.status === 'SQUEEZE' && <Zap className="w-2.5 h-2.5 inline mr-0.5" />}
                      {row.status}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Terminal Footer Summary Bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#131722] border-t border-[#1E222D] text-[10px] font-mono text-[#9B9EAE]">
        <div className="flex items-center gap-4">
          <span>MONITORING: <strong className="text-[#FFFFFF]">{filteredRows.length} TICKERS</strong></span>
          <span>HIGH RVOL (&gt;50x): <strong className="text-[#089981]">{filteredRows.filter(r => r.rvol >= 50).length}</strong></span>
          <span>LOW FLOAT (&lt;10M): <strong className="text-[#F59E0B]">{filteredRows.filter(r => r.floatShares < 10000000).length}</strong></span>
        </div>
        <div className="flex items-center gap-1 text-[#089981]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#089981] animate-pulse"></span>
          <span>BLOOMBERG FEED ACTIVE</span>
        </div>
      </div>
    </div>
  )
}
