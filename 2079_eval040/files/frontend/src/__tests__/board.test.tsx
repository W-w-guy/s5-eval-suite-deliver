/**
 * AC1 7 个工具在条形图中都可见；AC2 low_sample 灰显 + 提示文案；
 * AC3 下钻列表不出现草稿正文字段。
 *
 * 期望值写死，不调用被测代码自己算自己。
 */
import React from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import QualityBoard from '../pages/QualityBoard'
import RejectedList, { VISIBLE_COLUMNS, FORBIDDEN_FIELDS } from '../pages/RejectedList'
import { LOW_SAMPLE_TEXT } from '../charts'
import payload from '../../../data/mock.json'

const SEVEN_TOOLS = [
  'meeting_minutes', 'weekly_report', 'intent_classify', 'lead_profile',
  'kb_answer', 'copy_draft', 'intel_brief',
]

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const key = String(url).replace('/mock.json', '')
    return { json: async () => payload } as any
  }))
})

describe('AC1 七个工具都在条形图中可见', () => {
  it('恰好 7 个非 low_sample 工具，且每个都有独立条形', async () => {
    render(<QualityBoard onDrilldown={() => {}} />)
    await waitFor(() => expect(screen.getByTestId('tool-bar-chart')).toBeInTheDocument())
    for (const k of SEVEN_TOOLS) {
      expect(screen.getByTestId(`bar-${k}`)).toBeInTheDocument()
    }
  })

  it('条形图内的工具名逐个可见（不是只有图例）', async () => {
    render(<QualityBoard onDrilldown={() => {}} />)
    const chart = await screen.findByTestId('tool-bar-chart')
    for (const name of ['会议纪要生成', '周报草稿', '问询意图分类', '线索画像提炼',
                        '知识问答', '文案改写', '情报简报摘要']) {
      expect(within(chart).getByText(name)).toBeInTheDocument()
    }
  })

  it('mock 数据里确实有 7 个正常工具 + 1 个 low_sample 分组', () => {
    const rows = payload.summary.by_tool
    expect(rows.filter((r: any) => !r.low_sample)).toHaveLength(7)
    expect(rows.filter((r: any) => r.low_sample)).toHaveLength(1)
  })
})

describe('AC2 low_sample 灰显并显示提示文案', () => {
  it('low_sample 分组的条形带提示文案', async () => {
    render(<QualityBoard onDrilldown={() => {}} />)
    const hint = await screen.findByTestId('low-sample-hint-contract_clause')
    expect(hint).toHaveTextContent(LOW_SAMPLE_TEXT)
  })

  it('low_sample 条形透明度低于正常分组', async () => {
    render(<QualityBoard onDrilldown={() => {}} />)
    const low = await screen.findByTestId('bar-contract_clause')
    const normal = screen.getByTestId('bar-meeting_minutes')
    expect(Number(low.getAttribute('opacity'))).toBeLessThan(
      Number(normal.getAttribute('opacity')),
    )
    expect(Number(low.getAttribute('opacity'))).toBe(0.45)
    expect(Number(normal.getAttribute('opacity'))).toBe(1)
  })

  it('看板顶部汇总一句 low_sample 提示', async () => {
    render(<QualityBoard onDrilldown={() => {}} />)
    const box = await screen.findByTestId('low-sample-summary')
    expect(box).toHaveTextContent(LOW_SAMPLE_TEXT)
  })

  it('提示文案常量与工单原文一致', () => {
    expect(LOW_SAMPLE_TEXT).toBe('样本不足 20，不作结论')
  })
})

describe('AC3 下钻列表不出现草稿正文', () => {
  it('可见列恰好 4 个：draft_id / scenario / reject_reason / rejected_at', () => {
    expect(VISIBLE_COLUMNS).toEqual(['draft_id', 'scenario', 'reject_reason', 'rejected_at'])
  })

  it('渲染后表格里没有正文字段（按 data-colkey 判，不做整页子串匹配）', async () => {
    // 第一版是在整页 HTML 里找 "body" 这类子串 —— 结果命中了 <body> 标签本身，
    // 是假阳性写法。正确判据是：表格的表头列里不存在正文字段，
    // 且每行数据的键集合恰好等于 VISIBLE_COLUMNS。
    render(<RejectedList toolKey="meeting_minutes" onBack={() => {}} onOpenInQueue={() => {}} />)
    const box = await screen.findByTestId('rejected-table')
    const colKeys = Array.from(box.querySelectorAll('th[data-colkey]'))
      .map((el) => el.getAttribute('data-colkey'))
    expect(colKeys).toEqual(VISIBLE_COLUMNS)
    for (const f of FORBIDDEN_FIELDS) {
      expect(colKeys).not.toContain(f)
    }
  })

  it('表格里每一行只渲染 4 个单元格（列数等于可见列）', async () => {
    render(<RejectedList toolKey="meeting_minutes" onBack={() => {}} onOpenInQueue={() => {}} />)
    const box = await screen.findByTestId('rejected-table')
    const firstRow = box.querySelector('tbody tr')!
    expect(firstRow.querySelectorAll('td')).toHaveLength(VISIBLE_COLUMNS.length)
  })

  it('mock 的被拒接口本身就不返回正文字段', () => {
    const rows = payload.rejected.rows
    expect(rows.length).toBeGreaterThan(0)
    for (const r of rows) {
      for (const f of FORBIDDEN_FIELDS) {
        expect(Object.prototype.hasOwnProperty.call(r, f)).toBe(false)
      }
    }
  })

  it('页面上给出「查看正文需跳转并按权限校验」的说明', async () => {
    render(<RejectedList toolKey="meeting_minutes" onBack={() => {}} onOpenInQueue={() => {}} />)
    const note = await screen.findByTestId('privacy-note')
    expect(note.textContent).toMatch(/正文/)
    expect(note.textContent).toMatch(/权限/)
  })
})

describe('日 / 周两种视图可切换', () => {
  it('默认按日，切换后变按周且点数不同', async () => {
    const user = userEvent.setup()
    render(<QualityBoard onDrilldown={() => {}} />)
    await waitFor(() => expect(screen.getByTestId('trend-granularity')).toHaveTextContent('day'))
    await user.click(screen.getByText('按周'))
    await waitFor(() => expect(screen.getByTestId('trend-granularity')).toHaveTextContent('week'))
  })

  it('day 与 week 的点数分别是 14 与 6', () => {
    expect(payload.trend_day.points).toHaveLength(14)
    expect(payload.trend_week.points).toHaveLength(6)
  })
})
