export interface ToolRow {
  tool_key: string
  tool_name: string
  samples: number
  adopt_rate: number
  exact_adopt_rate: number
  modify_p50_chars: number
  reject_rate: number
  low_sample: boolean
}

export interface RejectReason {
  key: string
  name: string
  count: number
}

export interface Summary {
  cards: {
    adopt_rate: number
    exact_adopt_rate: number
    modify_p50_chars: number
    reject_rate: number
    pending_backlog: number
  }
  by_tool: ToolRow[]
  reject_reasons: RejectReason[]
  low_sample_threshold: number
}

export interface TrendPoint {
  label: string
  adopt_rate: number
  reject_rate: number
}

export interface Trend {
  granularity: 'day' | 'week'
  points: TrendPoint[]
}

export interface PromptRow {
  tool_key: string
  tool_name: string
  version: string
  released_on: string
  adopt_rate: number
  modify_p50_chars: number
}

export interface RejectedRow {
  draft_id: string
  tool_key: string
  scenario: string
  reject_reason: string
  rejected_at: string
}
