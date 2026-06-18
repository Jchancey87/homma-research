import { describe, it, expect } from 'vitest'
import { fmt1, fmtFloat, fmtVol, addDays, todayET } from './format'

describe('fmt1', () => {
  it('returns em-dash for null/undefined', () => {
    expect(fmt1(null)).toBe('—')
    expect(fmt1(undefined)).toBe('—')
  })

  it('formats to 1 decimal', () => {
    expect(fmt1(0)).toBe('0.0')
    expect(fmt1(3.14159)).toBe('3.1')
    expect(fmt1(-7.8)).toBe('-7.8')
  })

  it('appends suffix when provided', () => {
    expect(fmt1(15, 'x')).toBe('15.0x')
    expect(fmt1(2.5, '%')).toBe('2.5%')
  })
})

describe('fmtFloat', () => {
  it('returns em-dash for null/undefined', () => {
    expect(fmtFloat(null)).toBe('—')
    expect(fmtFloat(undefined)).toBe('—')
  })

  it('formats raw share count as M', () => {
    expect(fmtFloat(0)).toBe('0.0M')
    expect(fmtFloat(1_000_000)).toBe('1.0M')
    expect(fmtFloat(15_500_000)).toBe('15.5M')
  })

  it('rolls over to B for >= 1000M', () => {
    expect(fmtFloat(999_999_999)).toBe('1000.0M')
    expect(fmtFloat(1_000_000_000)).toBe('1.0B')
    expect(fmtFloat(2_500_000_000)).toBe('2.5B')
  })
})

describe('fmtVol', () => {
  it('returns em-dash for null/undefined', () => {
    expect(fmtVol(null)).toBe('—')
    expect(fmtVol(undefined)).toBe('—')
  })

  it('uses raw locale formatting for < 1K', () => {
    expect(fmtVol(0)).toBe('0')
    expect(fmtVol(999)).toBe('999')
  })

  it('formats K for 1K-1M', () => {
    expect(fmtVol(1_000)).toBe('1K')
    expect(fmtVol(15_500)).toBe('16K')
  })

  it('formats M for >= 1M', () => {
    expect(fmtVol(1_000_000)).toBe('1.0M')
    expect(fmtVol(2_500_000)).toBe('2.5M')
  })
})

describe('addDays', () => {
  it('adds positive days', () => {
    expect(addDays('2026-06-18', 1)).toBe('2026-06-19')
    expect(addDays('2026-06-18', 7)).toBe('2026-06-25')
  })

  it('subtracts with negative offset', () => {
    expect(addDays('2026-06-18', -1)).toBe('2026-06-17')
    expect(addDays('2026-06-01', -1)).toBe('2026-05-31')
  })

  it('handles month boundaries', () => {
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01')
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28')
  })

  it('handles year boundaries', () => {
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  })
})

describe('todayET', () => {
  it('returns ISO YYYY-MM-DD format', () => {
    expect(todayET()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})
