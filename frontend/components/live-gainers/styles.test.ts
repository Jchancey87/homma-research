import { describe, it, expect, vi, afterEach } from 'vitest'
import {
  getRvolBadgeStyle, getRvolColor,
  getFloatBadgeStyle, getSpreadBadgeStyle,
  getAtrHodColor, getAtrSpreadStyle, getAtrVwapStyle, getZenVStyle,
  getTimeAgoBadge,
} from './styles'

describe('getRvolBadgeStyle', () => {
  it('returns em-dash for null', () => {
    expect(getRvolBadgeStyle(null).label).toBe('—')
  })

  it('tiers: Extreme / Mega / Strong / Above Avg / default', () => {
    expect(getRvolBadgeStyle(1500).label).toContain('Extreme')
    expect(getRvolBadgeStyle(300).label).toContain('Mega')
    expect(getRvolBadgeStyle(75).label).toContain('Strong')
    expect(getRvolBadgeStyle(7).label).toContain('Above Avg')
    expect(getRvolBadgeStyle(2).label).not.toContain('Strong')
  })

  it('formats label with 1-decimal x', () => {
    expect(getRvolBadgeStyle(123.456).label).toContain('123.5x')
  })
})

describe('getRvolColor', () => {
  it('returns muted color for null', () => {
    expect(getRvolColor(null)).toBe('text-gray-400')
  })

  it('escalates class with tier', () => {
    expect(getRvolColor(1500)).toContain('rose')
    expect(getRvolColor(300)).toContain('emerald-200')
    expect(getRvolColor(75)).toContain('emerald-300')
    expect(getRvolColor(7)).toContain('emerald-400')
  })
})

describe('getFloatBadgeStyle', () => {
  it('returns em-dash for null', () => {
    expect(getFloatBadgeStyle(null).label).toBe('—')
  })

  it('tiers by float size', () => {
    expect(getFloatBadgeStyle(500_000).label).toContain('Small')
    expect(getFloatBadgeStyle(5_000_000).label).toContain('Medium')
    expect(getFloatBadgeStyle(30_000_000).label).toContain('Normal')
    expect(getFloatBadgeStyle(100_000_000).label).toContain('Large')
  })
})

describe('getSpreadBadgeStyle', () => {
  it('returns em-dash for null', () => {
    expect(getSpreadBadgeStyle(null).label).toBe('—')
  })

  it('tiers: tight / Elevated / High / Extreme', () => {
    expect(getSpreadBadgeStyle(0.5).label).not.toContain('Elevated')
    expect(getSpreadBadgeStyle(2).label).toContain('Elevated')
    expect(getSpreadBadgeStyle(4).label).toContain('High')
    expect(getSpreadBadgeStyle(6).label).toContain('Extreme')
  })
})

describe('getAtrHodColor', () => {
  it('muted for null', () => {
    expect(getAtrHodColor(null)).toBe('text-slate-500')
    expect(getAtrHodColor(undefined)).toBe('text-slate-500')
  })

  it('emphasises 0 with underline (at HOD)', () => {
    expect(getAtrHodColor(0)).toContain('underline')
  })

  it('fades as value grows', () => {
    expect(getAtrHodColor(0.1)).toContain('emerald-300')
    expect(getAtrHodColor(0.3)).toContain('emerald-400/70')
    expect(getAtrHodColor(0.7)).toBe('text-slate-300')
    expect(getAtrHodColor(1.5)).toBe('text-slate-400')
    expect(getAtrHodColor(3)).toBe('text-slate-500')
  })
})

describe('getAtrSpreadStyle', () => {
  it('em-dash for null', () => {
    expect(getAtrSpreadStyle(null).text).toBe('—')
    expect(getAtrSpreadStyle(undefined).text).toBe('—')
  })

  it('tight at <= 0.3', () => {
    expect(getAtrSpreadStyle(0.2).text).toContain('Tight')
  })

  it('wide at > 1.0', () => {
    expect(getAtrSpreadStyle(1.5).text).toContain('Dangerously Wide')
  })

  it('moderate in between', () => {
    expect(getAtrSpreadStyle(0.5).text).toContain('Moderate')
  })
})

describe('getAtrVwapStyle', () => {
  it('em-dash for null', () => {
    expect(getAtrVwapStyle(null).text).toBe('—')
  })

  it('overextended at > 3.0', () => {
    expect(getAtrVwapStyle(4).text).toContain('Overextended')
  })

  it('short-extended at < -3.0', () => {
    expect(getAtrVwapStyle(-4).text).toContain('Short-Extended')
  })

  it('mean reversion at |val| <= 1.0', () => {
    expect(getAtrVwapStyle(0.5).text).toContain('Mean Reversion')
    expect(getAtrVwapStyle(-0.5).text).toContain('Mean Reversion')
  })
})

describe('getZenVStyle', () => {
  it('em-dash for null/undefined', () => {
    expect(getZenVStyle(null).text).toBe('—')
    expect(getZenVStyle(undefined).text).toBe('—')
  })

  it('up arrow for positive', () => {
    expect(getZenVStyle(0.5).text).toContain('▲')
  })

  it('down arrow for negative', () => {
    expect(getZenVStyle(-0.5).text).toContain('▼')
  })

  it('flat triangle for zero', () => {
    expect(getZenVStyle(0).text).toContain('▶')
  })
})

describe('getTimeAgoBadge', () => {
  afterEach(() => { vi.restoreAllMocks() })

  it('returns null for null input', () => {
    expect(getTimeAgoBadge(null)).toBeNull()
  })

  it('Fresh for < 5 min', () => {
    const now = 60 * 60 * 1000
    vi.spyOn(Date, 'now').mockReturnValue(now)
    // 60s ago
    expect(getTimeAgoBadge(now - 60_000)!.label).toContain('Fresh')
  })

  it('Recent for 5-15 min', () => {
    const now = 60 * 60 * 1000
    vi.spyOn(Date, 'now').mockReturnValue(now)
    // 10 min ago
    expect(getTimeAgoBadge(now - 10 * 60_000)!.label).toContain('Recent')
  })

  it('Stale for 15-60 min', () => {
    const now = 60 * 60 * 1000
    vi.spyOn(Date, 'now').mockReturnValue(now)
    // 30 min ago
    expect(getTimeAgoBadge(now - 30 * 60_000)!.label).toContain('Stale')
  })

  it('Old for > 60 min', () => {
    const now = 2 * 60 * 60 * 1000
    vi.spyOn(Date, 'now').mockReturnValue(now)
    // 90 min ago
    expect(getTimeAgoBadge(now - 90 * 60_000)!.label).toContain('Old')
  })
})
