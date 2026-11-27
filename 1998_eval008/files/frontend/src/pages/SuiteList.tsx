import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Table, Switch, Tag, Loading } from 'tdesign-react'
import { getSuites, type Suite } from '../api'
import type { Who } from '../App'

export default function SuiteList({ who }: { who: Who }) {
  const [rows, setRows] = useState<Suite[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [onlyPending, setOnlyPending] = useState(false)
  const nav = useNavigate()

  useEffect(() => {
    getSuites()
      .then((d) => setRows(d.items))
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false))
  }, [])

  // 「只看待复核」：待复核 = 用例数 - 已复核数 > 0
  const shown = useMemo(
    () => (onlyPending ? rows.filter((r) => r.case_count - r.reviewed_count > 0) : rows),
    [rows, onlyPending],
  )

  if (loading) return <Loading data-testid="loading" />
  if (err) return <div data-testid="error">加载失败：{err}</div>

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', gap: 12, alignItems: 'center' }}>
        <Switch
          data-testid="pending-filter"
          value={onlyPending}
          onChange={(v) => setOnlyPending(Boolean(v))}
          label={['只看待复核', '全部套件']}
        />
        <span data-testid="suite-count">共 {shown.length} 个套件</span>
      </div>
      <Table
        data-testid="suite-table"
        rowKey="key"
        data={shown}
        columns={[
          { colKey: 'key', title: '套件 key', width: 200 },
          { colKey: 'name', title: '名称', width: 220 },
          { colKey: 'case_count', title: '用例数', width: 100 },
          { colKey: 'reviewed_count', title: '已复核', width: 100 },
          {
            colKey: 'pending',
            title: '待复核',
            width: 100,
            cell: ({ row }: { row: Suite }) => {
              const n = row.case_count - row.reviewed_count
              return n > 0
                ? <Tag data-testid={`pending-${row.key}`} theme="warning">{n}</Tag>
                : <Tag data-testid={`pending-${row.key}`} theme="success">0</Tag>
            },
          },
          {
            colKey: 'latest_pass_rate',
            title: '最近通过率',
            cell: ({ row }: { row: Suite }) =>
              row.latest_pass_rate === null ? '—' : `${(row.latest_pass_rate * 100).toFixed(1)}%`,
          },
          {
            colKey: 'op',
            title: '操作',
            cell: ({ row }: { row: Suite }) => (
              <a
                data-testid={`open-${row.key}`}
                href={`/eval/suites/${row.key}/cases/case-0001`}
                onClick={(e) => {
                  e.preventDefault()
                  nav(`/eval/suites/${row.key}/cases/case-0001`)
                }}
              >
                查看用例
              </a>
            ),
          },
        ]}
      />
      <p style={{ color: '#888', marginTop: 12 }} data-testid="who-hint">
        评审权限：{who.perms.includes('eval.case.review') ? '有' : '无'}
      </p>
    </div>
  )
}
