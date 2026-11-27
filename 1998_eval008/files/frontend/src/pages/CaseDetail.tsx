import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Button, Input, Tag, Textarea, Loading, MessagePlugin } from 'tdesign-react'
import {
  getCase, postReview, buildSuggestionJSON, canReview,
  type CaseDetail as C, type Mark, type Verdict,
} from '../api'
import type { Who } from '../App'

const STATUS_TEXT: Record<string, string> = {
  pending: '待复核', reviewed: '已通过', needs_change: '需修改',
}

export default function CaseDetail({ who }: { who: Who }) {
  const { caseKey } = useParams()
  const [c, setC] = useState<C | null>(null)
  const [marks, setMarks] = useState<Record<number, Mark>>({})
  const [overall, setOverall] = useState('')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    if (!caseKey) return
    setLoading(true)
    getCase(caseKey)
      .then((d) => setC(d))
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false))
  }, [caseKey])

  useEffect(load, [load])

  const setMark = (i: number, verdict: Verdict) =>
    setMarks((m) => ({ ...m, [i]: { verdict, comment: m[i]?.comment ?? '' } }))
  const setComment = (i: number, comment: string) =>
    setMarks((m) => ({ ...m, [i]: { verdict: m[i]?.verdict ?? null, comment } }))

  const allowed = canReview(who.perms)
  const markedCount = Object.values(marks).filter((m) => m.verdict).length

  const submit = async () => {
    if (!c) return
    const pc: Record<string, string> = {}
    Object.entries(marks).forEach(([i, m]) => { if (m.comment.trim()) pc[i] = m.comment.trim() })
    try {
      const r = await postReview(c.id, {
        verdict: 'approve', point_comments: pc, comment: overall || undefined,
      }, who)
      MessagePlugin.success(`已提交，状态：${STATUS_TEXT[r.review_status] ?? r.review_status}`)
      load()
    } catch (e) {
      MessagePlugin.error(String(e))
    }
  }

  const exportJSON = () => {
    if (!c) return
    const payload = buildSuggestionJSON(c, marks, who.userId, new Date().toISOString())
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `suggestion-${c.case_key}.json`
    a.setAttribute('data-testid', 'suggestion-link')
    document.body.appendChild(a)
    a.click()
    a.remove()
    return payload
  }

  if (loading) return <Loading data-testid="loading" />
  if (err) return <div data-testid="error">加载失败：{err}</div>
  if (!c) return null

  return (
    <div data-testid="case-detail">
      <h3 data-testid="case-title">{c.case_key} · {c.input}</h3>
      <div style={{ marginBottom: 8 }}>
        状态：<Tag data-testid="status-badge" theme={
          c.review_status === 'reviewed' ? 'success'
            : c.review_status === 'needs_change' ? 'danger' : 'warning'
        }>{STATUS_TEXT[c.review_status] ?? c.review_status}</Tag>
        <span style={{ marginLeft: 12, color: '#888' }} data-testid="hash">hash {c.content_hash.slice(0, 12)}</span>
      </div>

      <ol style={{ paddingLeft: 20 }}>
        {c.points.map((p, i) => (
          <li key={i} data-testid={`point-${i}`} style={{ marginBottom: 10 }}>
            <div data-testid={`point-${i}-text`}>{p}</div>
            <Button data-testid={`point-${i}-approve`} size="small" disabled={!allowed}
              theme={marks[i]?.verdict === 'approve' ? 'primary' : 'default'}
              onClick={() => setMark(i, 'approve')}>同意</Button>
            <Button data-testid={`point-${i}-revise`} size="small" disabled={!allowed}
              theme={marks[i]?.verdict === 'revise' ? 'warning' : 'default'}
              onClick={() => setMark(i, 'revise')}>需修改</Button>
            <Button data-testid={`point-${i}-remove`} size="small" disabled={!allowed}
              theme={marks[i]?.verdict === 'remove' ? 'danger' : 'default'}
              onClick={() => setMark(i, 'remove')}>删除</Button>
            <Textarea data-testid={`point-${i}-comment`} placeholder="对该要点的意见"
              value={marks[i]?.comment ?? ''}
              onChange={(v) => setComment(i, String(v))} />
          </li>
        ))}
      </ol>

      <Textarea data-testid="overall-comment" placeholder="整体意见"
        value={overall} onChange={(v) => setOverall(String(v))} />

      <div style={{ marginTop: 12, display: 'flex', gap: 12, alignItems: 'center' }}>
        <Button data-testid="submit-review" theme="primary" disabled={!allowed} onClick={submit}>
          提交复核
        </Button>
        <Button data-testid="export-suggestion" disabled={!allowed} onClick={exportJSON}>
          导出修改建议 JSON
        </Button>
        <span data-testid="marked-count">已标记 {markedCount} / {c.points.length} 条要点</span>
        {!allowed && <span data-testid="no-perm-hint" style={{ color: '#c00' }}>无 eval.case.review 权限</span>}
      </div>
      <p style={{ color: '#888', marginTop: 8 }} data-testid="export-note">
        页面不改用例文件，只导出建议 JSON，由维护者改文件后提 PR。
      </p>
    </div>
  )
}
