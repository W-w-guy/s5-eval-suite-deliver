import React, { useEffect, useState } from 'react'
import { Card, Table, Button, Space, Tag } from 'tdesign-react'
import { api } from '../api'
import type { RejectedRow } from '../types'

// 下钻页：只显示 draft_id / 场景 / 拒绝原因 / 时间。
// **不显示正文** —— 正文需跳转复核队列并按权限校验。
export const VISIBLE_COLUMNS = ['draft_id', 'scenario', 'reject_reason', 'rejected_at']
export const FORBIDDEN_FIELDS = ['body', 'content', 'text', 'draft_body', 'draft_content']

export default function RejectedList({
  toolKey,
  onOpenInQueue,
  onBack,
}: {
  toolKey: string
  onOpenInQueue: (draftId: string) => void
  onBack: () => void
}) {
  const [rows, setRows] = useState<RejectedRow[]>([])
  const [note, setNote] = useState('')

  useEffect(() => {
    api.rejected(toolKey).then((r) => {
      setRows(r.rows)
      setNote(r.note)
    })
  }, [toolKey])

  return (
    <div data-testid="rejected-list" style={{ padding: 16 }}>
      <Space style={{ marginBottom: 12 }}>
        <Button data-testid="back" onClick={onBack}>返回看板</Button>
        <h3 style={{ margin: 0 }}>最近被拒草稿 · {toolKey}</h3>
      </Space>
      <Card>
        <div data-testid="privacy-note" style={{ color: '#0052d9', marginBottom: 8 }}>
          {note || '本列表不显示草稿正文；查看正文需跳转复核队列并按权限校验。'}
        </div>
        <div data-testid="rejected-table">
        <Table
          rowKey="draft_id"
          data={rows}
          columns={[
            { colKey: 'draft_id', title: '草稿 ID' },
            { colKey: 'scenario', title: '场景' },
            {
              colKey: 'reject_reason',
              title: '拒绝原因',
              cell: ({ row }) => <Tag theme="warning">{row.reject_reason}</Tag>,
            },
            { colKey: 'rejected_at', title: '时间' },
          ]}
        />
        </div>
        <Space breakLine style={{ marginTop: 12 }}>
          {rows.slice(0, 4).map((r) => (
            <Button
              key={r.draft_id}
              data-testid={`open-in-queue-${r.draft_id}`}
              variant="text"
              onClick={() => onOpenInQueue(r.draft_id)}
            >
              在复核队列中查看正文 · {r.draft_id}
            </Button>
          ))}
        </Space>
      </Card>
    </div>
  )
}
