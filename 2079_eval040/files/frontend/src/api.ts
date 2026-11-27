// 4 个查询接口。默认走本地 mock（VITE_USE_MOCK 未设为 0 时），
// 结构按 EVAL-039 的接口约定：{ code, data }。
import type { Summary, Trend, PromptRow, RejectedRow, ToolRow } from './types'

export const USE_MOCK = import.meta.env?.VITE_USE_MOCK !== '0'

let mockCache: any = null

async function loadMock() {
  if (mockCache) return mockCache
  const res = await fetch('/mock.json')
  mockCache = await res.json()
  return mockCache
}

async function getJSON<T>(url: string, mock: () => Promise<T>): Promise<T> {
  if (USE_MOCK) return mock()
  const r = await fetch(url)
  const body = await r.json()
  return (body.data ?? body) as T
}

export const api = {
  summary: () =>
    getJSON<Summary>('/api/eval/quality/summary',
      async () => (await loadMock()).summary),

  trend: (granularity: 'day' | 'week') =>
    getJSON<Trend>(`/api/eval/quality/trend?granularity=${granularity}`,
      async () => (await loadMock())[granularity === 'day' ? 'trend_day' : 'trend_week']),

  tools: () =>
    getJSON<{ rows: ToolRow[]; low_sample_threshold: number }>(
      '/api/eval/quality/tools', async () => (await loadMock()).tools),

  rejected: (toolKey: string) =>
    getJSON<{ rows: RejectedRow[]; note: string }>(
      `/api/eval/quality/rejected?tool=${toolKey}`,
      async () => (await loadMock()).rejected),

  promptCompare: () =>
    getJSON<{ rows: PromptRow[] }>('/api/eval/quality/prompt-compare',
      async () => (await loadMock()).prompt_compare),
}
