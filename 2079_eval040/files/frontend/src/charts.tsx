// 图表全部用内联 SVG 自绘：不引入任何外部 CDN，也不依赖图表库的 CDN 版本。
// AC1 要求「7 个工具在条形图中都可见」，所以每个条形都带 data-testid 与可读文本。
import React from 'react'
import type { TrendPoint, ToolRow } from './types'

export const LOW_SAMPLE_TEXT = '样本不足 20，不作结论'

export function ToolBarChart({ rows }: { rows: ToolRow[] }) {
  const W = 520
  const rowH = 34
  const H = rows.length * rowH + 10
  return (
    <svg width={W} height={H} role="img" aria-label="按工具对比的采纳率条形图"
         data-testid="tool-bar-chart">
      {rows.map((r, i) => {
        const y = i * rowH + 4
        const w = Math.max(2, Math.round(r.adopt_rate * (W - 190)))
        return (
          <g key={r.tool_key} data-testid={`bar-${r.tool_key}`}
             opacity={r.low_sample ? 0.45 : 1}>
            <text x={0} y={y + 14} fontSize={12}>{r.tool_name}</text>
            <rect x={96} y={y + 3} width={w} height={16}
                  fill={r.low_sample ? '#c5c8ce' : '#0052d9'} />
            <text x={96 + w + 6} y={y + 15} fontSize={11}>
              {(r.adopt_rate * 100).toFixed(1)}%
            </text>
            {r.low_sample && (
              <text x={96} y={y + 31} fontSize={10} fill="#e37318"
                    data-testid={`low-sample-hint-${r.tool_key}`}>
                {LOW_SAMPLE_TEXT}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

export function TrendChart({ points }: { points: TrendPoint[] }) {
  const W = 560
  const H = 160
  const maxX = Math.max(points.length - 1, 1)
  const y = (v: number) => H - 20 - v * (H - 50)
  const path = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${(i / maxX) * (W - 40) + 30} ${y(p.adopt_rate)}`)
    .join(' ')
  return (
    <svg width={W} height={H} role="img" aria-label="采纳率趋势折线"
         data-testid="trend-chart">
      <path d={path} fill="none" stroke="#0052d9" strokeWidth={2} />
      {points.map((p, i) => (
        <circle key={p.label} cx={(i / maxX) * (W - 40) + 30} cy={y(p.adopt_rate)} r={3}
                fill="#0052d9" />
      ))}
      {points.map((p, i) => (
        i % 2 === 0 ? (
          <text key={`t-${p.label}`} x={(i / maxX) * (W - 40) + 24} y={H - 4} fontSize={9}>
            {p.label}
          </text>
        ) : null
      ))}
    </svg>
  )
}
