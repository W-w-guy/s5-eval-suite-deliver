# AI 采纳率与修改幅度看板（S5-EVAL-040）

工作台页面 `/eval/quality`（React 18 + TypeScript + TDesign）：筛选、5 张指标卡、趋势折线（日/周切换）、按工具对比条形图、拒绝原因分布、提示词版本对比表，以及下钻到最近被拒草稿列表（不显示正文）。图表为**内联 SVG 自绘**，不引用任何 CDN。

## 一条命令复跑

```
python pkg/mockdata.py                  # 重算 data/mock.json
cd frontend && npm ci && npm run build  # 装依赖并构建 dist
npm test                                # Vitest（17 项）
cd .. && python tools/verify.py         # 逐条断言 AC（32 条），非零退出可接 CI
python tools/build_docs.py              # 由实跑结果重生成文档
python tools/make_zip.py                # 打包 + SHA256SUMS
```

依赖：Python 3.11+（工具链）、Node 18+ 与 npm（前端构建与测试）、Playwright + Chromium（真浏览器截图与网络记录，`python -m playwright install chromium`）。

## 4 个查询接口（按 EVAL-039 的结构，先用 mock）

| 接口 | 返回 |
| --- | --- |
| `/api/eval/quality/summary` | 指标卡 + 按工具对比 + 拒绝原因分布 |
| `/api/eval/quality/trend?granularity=day\|week` | 趋势折线点 |
| `/api/eval/quality/tools` | 工具列表（含 low_sample 标记） |
| `/api/eval/quality/rejected?tool=<key>` | 最近被拒草稿（**不含正文**） |

默认走 `data/mock.json`；把 `VITE_USE_MOCK=0` 后重新构建即改走真实接口。

## 四条容易写错的实现细节

**① low_sample 必须灰显 + 带提示文案，两件事都要做。**
只降透明度不给文案，看的人会以为图表坏了；只给文案不灰显，容易把小样本和大样本混在一起读。本包用 `opacity=0.45` 与「样本不足 20，不作结论」两句同时约束，组件测试对这两个信号分别断言（含正常分组 `opacity=1` 的正向对照）。

**② 「不显示正文」要断言字段集合，不能靠整页子串匹配。**
第一版写的是 `document.body.innerHTML.toLowerCase()` 里不含 `body` —— 结果命中了 `<body>` 标签本身，是假阳性写法。正确判据是读表头的 `data-colkey` 与每行 `<td>` 数量，并断言字段集合恰为 `{draft_id, scenario, reject_reason, rejected_at}`。

**③ 外部域名检查不能拿源码扫描代替网络记录。**
源码里没有外链，不等于运行时没有请求（依赖库可能在运行时注入）。本包用 Playwright 监听 `page.on('request')`，把每个请求的域名都记进 `docs/network.json`，断言 `external_hosts` 为空 —— 这是网络面板级别的证据。

**④ 图表用内联 SVG 而不是图表库。**
工单要求「图表库本地打包，不引用外部 CDN」。最省事的做法是自绘 SVG：既能满足所有视觉要求，也从根上不存在 CDN 依赖，且不增加 700KB 级别的依赖体积。

## 目录

| 路径 | 内容 |
| --- | --- |
| `pkg/mockdata.py` | 7 个工具 + 1 个 low_sample 分组 + 4 个接口响应（确定性） |
| `data/mock.json` | 全部 mock 数据 |
| `frontend/src/pages/QualityBoard.tsx` | 看板页：筛选 / 指标卡 / 趋势 / 条形图 / 原因分布 / 版本表 |
| `frontend/src/pages/RejectedList.tsx` | 下钻页：被拒草稿列表（4 列，无正文） |
| `frontend/src/charts.tsx` | 内联 SVG 条形图与折线图（含 LOW_SAMPLE_TEXT 常量） |
| `frontend/src/api.ts` | 4 个查询接口的客户端封装（mock / 真实可切） |
| `frontend/src/__tests__/` | Vitest 17 项（含 AC1/AC2/AC3 与无外链扫描） |
| `tools/shots.py` | 真 Chromium 抓图 + 记录全部请求域名 |
| `tools/verify.py` | 32 条 AC 断言 |
| `docs/shots/` | 日视图 / 周视图 / 下钻页三张截图 |
| `docs/network.json` | 页面加载的完整请求清单（AC4 证据） |

## 设计取舍

- **下钻页只给 4 个字段，正文另走权限校验**：草稿正文可能含未脱敏内容，在列表里直接铺开等于绕过复核队列的权限边界。
- **mock 里就带上 low_sample 分组**：只有大样本会让看板「看起来很稳」，把样本不足的分组显式标出来，才能让人在看到漂亮数字时先问分母。
- **截图与构建产物不进 SHA256SUMS**：它们随每次构建/运行变化，纳入校验和会让买家跑完一遍就 mismatch。