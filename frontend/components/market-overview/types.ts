import { CommandSummaryData } from '@/lib/api'

export type CardId = 'regime' | 'breadth' | 'liquidity' | 'risk'

export interface CardBaseProps {
  expanded: boolean
  onToggle: () => void
}

export type { CommandSummaryData }
