import React, { useEffect, useMemo, useState } from 'react'
import { Card, DateRangePicker, Select, Radio, Table, Button, Tag, Space } from 'tdesign-react'
import { api } from '../api'
import { ToolBarChart, TrendChart, LOW_SAMPLE_TEXT } from '../charts'
import type { Summary, Trend, PromptRow } from '../types'

const GRANULARITY = [
  { label: '按日', value: 'day' },
  { label: '按周', value: 'week' },
]

export default function QualityBoard({
  onDrilldown,
}: {
  onDrilldown: (toolKey: string) => void
}) {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [granularity, setGranularity] = useState<'day' | 'week'>('day')
  const [trend, setTrend] = useState<Trend | null>(null)
  const [promptRows, setPromptRows] = useState<PromptRow[]>([])
  const [site, setSite] = useState('all')
  const [tool, setTool] = useState('all')

  useEffect(() => {
    api.summary().then(setSummary)
    api.promptCompare().then((r) => setPromptRows(r.rows))
  }, [])

  useEffect(() => {
    api.trend(granularity).then(setTrend)
  }, [granularity])

  const cards = summary?.cards
  const lowGroups = useMemo(
    () => (summary?.by_tool ?? []).filter((r) => r.low_sample),
    [summary],
  )

  return (
    <div data-testid="quality-board" style={{ padding: 16 }}>
      <h2>评测质量看板 · AI 采纳率与修改幅度</h2>

      {/* 筛选区 */}
      <Space breakLine style={{ marginBottom: 12 }}>
        <DateRangePicker data-testid="filter-date" />
        <Select
          data-testid="filter-site"
          value={site}
          onChange={(v) => setSite(v as string)}
          options={[{ label: '全部站点', value: 'all' }, { label: '上海站', value: 'sh' }]}
        />
        <Select
          data-testid="filter-tool"
          value={tool}
          onChange={(v) => setTool(v as string)}
          options={[{ label: '全部工具', value: 'all' }].concat(
            (summary?.by_tool ?? []).map((r) => ({ label: r.tool_name, value: r.tool_key })),
          )}
        />
        <Select
          data-testid="filter-scenario"
          value="all"
          options={[{ label: '全部场景', value: 'all' }]}
        />
        <Select
          data-testid="filter-prompt"
          value="all"
          options={[{ label: '全部提示词版本', value: 'all' }]}
        />
      </Space>

      {/* 指标卡 */}
      <Space breakLine style={{ marginBottom: 16 }}>
        <Card title="采纳率" data-testid="card-adopt">
          <div data-testid="val-adopt">
            {cards ? (cards.adopt_rate * 100).toFixed(1) + '%' : '-'}
          </div>
        </Card>
        <Card title="原样采纳率" data-testid="card-exact">
          <div data-testid="val-exact">
            {cards ? (cards.exact_adopt_rate * 100).toFixed(1) + '%' : '-'}
          </div>
        </Card>
        <Card title="修改幅度 P50" data-testid="card-p50">
          <div data-testid="val-p50">{cards ? cards.modify_p50_chars + ' 字' : '-'}</div>
        </Card>
        <Card title="拒绝率" data-testid="card-reject">
          <div data-testid="val-reject">
            {cards ? (cards.reject_rate * 100).toFixed(1) + '%' : '-'}
          </div>
        </Card>
        <Card title="待复核积压" data-testid="card-backlog">
          <div data-testid="val-backlog">{cards ? cards.pending_backlog : '-'}</div>
        </Card>
      </Space>

      {/* 趋势折线 + 日/周切换 */}
      <Card title="采纳率趋势" data-testid="card-trend">
        <Radio.Group
          data-testid="granularity"
          value={granularity}
          onChange={(v) => setGranularity(v as 'day' | 'week')}
          options={GRANULARITY}
        />
        {trend && <TrendChart points={trend.points} />}
        <div data-testid="trend-granularity">{granularity}</div>
      </Card>

      {/* 按工具对比的条形图 */}
      <Card title="按工具对比" data-testid="card-by-tool">
        {summary && <ToolBarChart rows={summary.by_tool} />}
        {lowGroups.length > 0 && (
          <div data-testid="low-sample-summary" style={{ color: '#e37318', marginTop: 8 }}>
            含 {lowGroups.length} 个分组：{LOW_SAMPLE_TEXT}
          </div>
        )}
      </Card>

      {/* 拒绝原因分布 */}
      <Card title="拒绝原因分布" data-testid="card-reasons">
        {(summary?.reject_reasons ?? []).map((r) => (
          <div key={r.key} data-testid={`reason-${r.key}`}>
            {r.name}：{r.count}
          </div>
        ))}
      </Card>

      {/* 提示词版本对比表 */}
      <Card title="提示词版本对比" data-testid="card-prompt">
        <div data-testid="prompt-table">
        <Table
          rowKey="version"
          data={promptRows}
          columns={[
            { colKey: 'tool_name', title: '工具' },
            { colKey: 'version', title: '版本' },
            { colKey: 'released_on', title: '发布日期' },
            {
              colKey: 'adopt_rate',
              title: '采纳率',
              cell: ({ row }) => (row.adopt_rate * 100).toFixed(1) + '%',
            },
            { colKey: 'modify_p50_chars', title: '修改幅度 P50（字）' },
          ]}
        />
        </div>
      </Card>

      {/* 下钻入口 */}
      <Card title="下钻" data-testid="card-drilldown">
        <Space breakLine>
          {(summary?.by_tool ?? []).slice(0, 7).map((r) => (
            <Button
              key={r.tool_key}
              data-testid={`drill-${r.tool_key}`}
              theme="primary"
              variant="outline"
              onClick={() => onDrilldown(r.tool_key)}
            >
              查看被拒草稿 · {r.tool_name}
            </Button>
          ))}
        </Space>
      </Card>
    </div>
  )
}
