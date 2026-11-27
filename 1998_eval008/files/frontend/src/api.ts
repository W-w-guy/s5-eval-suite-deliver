// 接口封装。BASE 默认同源（后端 serve 前端构建产物），也可用 VITE_API_BASE 指到别处。
export type Suite = {
  id: string; key: string; name: string
  case_count: number; reviewed_count: number; latest_pass_rate: number | null
}
export type Review = {
  reviewer_id: string; verdict: string
  point_comments: Record<string, string>; comment: string | null
}
export type CaseDetail = {
  id: string; case_key: string; input: string; context: Record<string, unknown>
  points: string[]; content_hash: string; review_status: string
  recent_runs: unknown[]; reviews: Review[]
}
export type Verdict = 'approve' | 'revise' | 'remove'

const BASE = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE ?? ''

// 身份与权限：真实环境由 S2-IAM 下发（登录态/令牌），本单用请求头模拟，
// 所以每个请求都要带上，否则后端只会返回 401。
let IDENT: { userId: string; perms: string } = { userId: '', perms: '' }
export function setIdentity(w: { userId: string; perms: string }) {
  IDENT = w
}
function identHeaders(): Record<string, string> {
  return IDENT.userId
    ? { 'X-User-Id': IDENT.userId, 'X-Permissions': IDENT.perms }
    : {}
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(BASE + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...identHeaders(), ...(init.headers || {}) },
  })
  if (!r.ok) throw new Error((await r.text()) || `HTTP ${r.status}`)
  return (await r.json()) as T
}

export const getSuites = () => req<{ items: Suite[] }>('/api/eval/suites')

// 详情按 case_key 取：后端 {id} 段同时接受 UUID 与 case_key，避免为此新增第 4 个接口。
export const getCase = (idOrKey: string) =>
  req<CaseDetail>(`/api/eval/cases/${encodeURIComponent(idOrKey)}`)

export const postReview = (
  caseId: string,
  body: { verdict: Verdict; point_comments?: Record<string, string>; comment?: string },
  who: { userId: string; perms: string },
) =>
  req<{ review_status: string; approvers: string[]; required: number }>(
    `/api/eval/cases/${caseId}/reviews`,
    {
      method: 'POST',
      headers: { 'X-User-Id': who.userId, 'X-Permissions': who.perms },
      body: JSON.stringify(body),
    },
  )

export const REVIEW_PERM = 'eval.case.review'
export const canReview = (perms: string) =>
  perms.split(',').map((s) => s.trim()).filter(Boolean).includes(REVIEW_PERM)

export type Mark = { verdict: Verdict | null; comment: string }

/**
 * 导出「修改建议 JSON」——页面只产出建议，不改用例文件本身。
 * 文件由维护者改完再提 PR，这是工单明确要求的分工。
 */
export function buildSuggestionJSON(
  c: CaseDetail,
  marks: Record<number, Mark>,
  reviewer: string,
  at: string,
) {
  const items = c.points
    .map((text, i) => {
      const m = marks[i]
      if (!m || !m.verdict) return null
      return { index: i, point: text, verdict: m.verdict, comment: m.comment.trim() }
    })
    .filter(Boolean)
  return {
    schema: 'eval-case-suggestion/v1',
    case_key: c.case_key,
    case_id: c.id,
    content_hash: c.content_hash,
    reviewer_id: reviewer,
    generated_at: at,
    applied_to_file: false,
    total_points: c.points.length,
    marked_points: items.length,
    suggestions: items,
  }
}
