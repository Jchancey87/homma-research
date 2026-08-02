/**
 * Market Hours Utilities
 * Extended trading hours: Monday - Friday, 4:00 AM ET to 8:00 PM ET.
 */

export function isMarketOpen(now: Date = new Date()): boolean {
  try {
    const nyTimeString = now.toLocaleString('en-US', { timeZone: 'America/New_York' })
    const nyDate = new Date(nyTimeString)

    const day = nyDate.getDay() // 0 = Sun, 1 = Mon, ..., 6 = Sat
    if (day === 0 || day === 6) {
      return false
    }

    const hours = nyDate.getHours()
    const minutes = nyDate.getMinutes()
    const timeInMinutes = hours * 60 + minutes

    const openTimeMinutes = 4 * 60 // 4:00 AM ET (240 mins)
    const closeTimeMinutes = 20 * 60 // 8:00 PM ET (1200 mins)

    return timeInMinutes >= openTimeMinutes && timeInMinutes < closeTimeMinutes
  } catch {
    return false
  }
}
