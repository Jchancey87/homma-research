import { describe, it, expect } from 'vitest'
import type { UTCTimestamp } from 'lightweight-charts'
import { dedupSort, shiftChartDataTime } from './chart'
import type { ChartData } from './chart'

// Test helpers use plain numbers as time values. lightweight-charts'
// UTCTimestamp is a branded number type but the runtime values are
// interchangeable, so the cast is safe.
const t = (n: number): UTCTimestamp => n as UTCTimestamp

const makeData = (ohlcvTimes: number[], emaTimes: number[] = []): ChartData => ({
  ohlcv:   ohlcvTimes.map(n => ({ time: t(n), open: 0, high: 0, low: 0, close: 0 })),
  volume:  ohlcvTimes.map(n => ({ time: t(n), value: 0 })),
  ema_21:  emaTimes.map(n => ({ time: t(n), value: 0 })),
})

describe('dedupSort', () => {
  it('sorts ascending by time', () => {
    const result = dedupSort([
      { time: t(30), value: 'c' },
      { time: t(10), value: 'a' },
      { time: t(20), value: 'b' },
    ])
    expect(result.map(r => r.value)).toEqual(['a', 'b', 'c'])
  })

  it('keeps the last occurrence on duplicate timestamps', () => {
    const result = dedupSort([
      { time: t(10), value: 'first' },
      { time: t(10), value: 'second' },
      { time: t(10), value: 'third' },
    ])
    expect(result.length).toBe(1)
    expect(result[0].value).toBe('third')
  })

  it('handles empty input', () => {
    expect(dedupSort([])).toEqual([])
  })

  it('handles unsorted with duplicates', () => {
    const result = dedupSort([
      { time: t(30), value: 'c' },
      { time: t(10), value: 'a' },
      { time: t(20), value: 'b' },
      { time: t(10), value: 'A' },
    ])
    expect(result.map(r => r.value)).toEqual(['A', 'b', 'c'])
  })
})

describe('shiftChartDataTime', () => {
  it('returns same data when offset is 0', () => {
    const data = makeData([100, 200, 300])
    const result = shiftChartDataTime(data, 0)
    expect(result).toBe(data) // Same reference — short-circuited
  })

  it('shifts all timestamps by offset seconds', () => {
    const data = makeData([1000, 2000, 3000], [1500])
    const result = shiftChartDataTime(data, 3600)
    expect(result.ohlcv.map(b => b.time)).toEqual([t(4600), t(5600), t(6600)])
    expect(result.volume.map(b => b.time)).toEqual([t(4600), t(5600), t(6600)])
    expect(result.ema_21.map(b => b.time)).toEqual([t(5100)])
  })

  it('handles negative offset (UTC → viewer-local)', () => {
    const data = makeData([1000])
    const result = shiftChartDataTime(data, -18000) // EST = UTC-5
    expect(result.ohlcv[0].time).toBe(t(-17000))
  })

  it('preserves empty arrays', () => {
    const data: ChartData = { ohlcv: [], volume: [], ema_21: [] }
    const result = shiftChartDataTime(data, 100)
    expect(result.ohlcv).toEqual([])
    expect(result.volume).toEqual([])
    expect(result.ema_21).toEqual([])
  })
})
