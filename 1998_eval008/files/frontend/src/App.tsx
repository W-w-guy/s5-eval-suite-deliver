import { useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import SuiteList from './pages/SuiteList'
import CaseDetail from './pages/CaseDetail'
import { canReview, REVIEW_PERM, setIdentity } from './api'

export type Who = { userId: string; perms: string }

export default function App() {
  // 演示用身份切换；真实环境由 S2-IAM 下发，前端只读不改。
  const [who, setWho] = useState<Who>({
    userId: 'aaaaaaaa-0000-0000-0000-000000000001',
    perms: REVIEW_PERM + ',eval.case.read',
  })
  setIdentity(who)   // 渲染前先登记身份，子组件的请求才会带上头
  const allowed = canReview(who.perms)
  return (
    <div style={{ padding: 16 }}>
      <div style={{ marginBottom: 12, display: 'flex', gap: 12, alignItems: 'center' }}>
        <strong>评测用例双人复核</strong>
        <span data-testid="who-badge" style={{ color: '#666' }}>当前身份：{who.userId.slice(0, 8)}</span>
        <button data-testid="toggle-perm" onClick={() => setWho(allowed
          ? { ...who, perms: 'eval.case.read' }
          : { ...who, perms: REVIEW_PERM + ',eval.case.read' })}>
          {allowed ? '去掉评审权限' : '授予评审权限'}
        </button>
        <span data-testid="perm-state">{allowed ? 'has-review' : 'no-review'}</span>
      </div>
      <Routes>
        <Route path="/eval/suites" element={<SuiteList who={who} />} />
        <Route path="/eval/suites/:suiteKey/cases/:caseKey" element={<CaseDetail who={who} />} />
        <Route path="*" element={<Navigate to="/eval/suites" replace />} />
      </Routes>
    </div>
  )
}
