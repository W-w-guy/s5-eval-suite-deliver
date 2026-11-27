/**
 * AC4 的前置：页面加载时不得向任何外部域名发请求。
 * 单测层面先扫源码：不得出现 http(s):// 外链、不得引用 CDN。
 * 真实网络面板证据由 tools/shots.py 在真 Chromium 里抓（记录全部请求域名）。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const SRC = join(process.cwd(), 'src')
const ALLOWED_HOSTS = ['localhost', '127.0.0.1']

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out)
    else out.push(p)
  }
  return out
}

// 排除测试目录自身：测试文件里必然出现 cdn/unpkg 这些关键词（用作黑名单字面量），
// 把它们算进去就成了自证循环 —— 第一版就是这么误报的。
const files = walk(SRC)
  .filter((f) => !f.includes('__tests__'))
  .filter((f) => /\.(tsx?|css|html)$/.test(f))
const URL_RE = /https?:\/\/[^"'\s)]+/g

describe('AC4 不引用任何外部域名', () => {
  it('源码里不存在外部 http(s) 链接', () => {
    const bad: string[] = []
    for (const f of files) {
      const txt = readFileSync(f, 'utf8')
      for (const m of txt.match(URL_RE) ?? []) {
        const host = m.replace(/^https?:\/\//, '').split(/[/:]/)[0]
        if (!ALLOWED_HOSTS.includes(host)) bad.push(`${f}: ${m}`)
      }
    }
    expect(bad).toEqual([])
  })

  it('源码里不出现 cdn / unpkg / jsdelivr 等关键字', () => {
    const bad: string[] = []
    for (const f of files) {
      const txt = readFileSync(f, 'utf8').toLowerCase()
      for (const kw of ['cdn.', 'unpkg', 'jsdelivr', 'cdnjs', 'googleapis']) {
        if (txt.includes(kw)) bad.push(`${f}: ${kw}`)
      }
    }
    expect(bad).toEqual([])
  })

  it('package.json 的 dependencies 不含图表库的 CDN 版本（图表为自绘 SVG）', () => {
    const pkg = JSON.parse(readFileSync(join(process.cwd(), 'package.json'), 'utf8'))
    const deps = Object.keys(pkg.dependencies ?? {})
    for (const banned of ['echarts', 'chart.js', 'recharts', 'highcharts']) {
      expect(deps).not.toContain(banned)
    }
  })
})
