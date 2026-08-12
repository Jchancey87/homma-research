import { CommandSummaryData } from '@/lib/api'

export type CardId = 'sector_strength' | 'breadth' | 'liquidity' | 'risk'

export interface CardBaseProps {
  expanded: boolean
  onToggle: () => void
}

export type { CommandSummaryData }
