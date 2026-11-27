# ACCEPTANCE — 逐条 AC 判定（原文 / 判定方式 / 复核命令 / 实际输出原文）

以下输出为 tools/verify.py 在交付包内的真实 stdout，未经修改。

AC1 原文：7 个工具在条形图中都可见（截图）
判定方式：mock 侧：断言恰好 7 个非 low_sample 工具 + 1 个 low_sample 分组，且 low 标记与样本数一致（<20）。浏览器侧：真 Chromium 打开页面后统计 `[data-testid^="bar-"]` 的条数为 8（7 正常 + 1 low），并把条形图截图落盘为 docs/shots/01_board_day.png
复核命令：python tools/verify.py   （看 V01-V03、V27）
实际输出原文：
[PASS] V01 mock 覆盖 7 个正常工具（工单要求至少 7 个） 实测 7 个
[PASS] V02 mock 覆盖 1 个 low_sample 分组 contract_clause（样本 11）
[PASS] V03 low_sample 标记与样本数一致（<20 才算 low） 正常最小 391 ／ low 最大 11
[PASS] V27 条形图中可见的工具条数 ≥7 实测 8 条

AC2 原文：low_sample 分组灰显并显示提示文案（截图与组件测试）
判定方式：组件测试：low_sample 条形的 opacity 必须为 0.45、正常分组为 1，且该分组内必须出现「样本不足 20，不作结论」这句文案（与 charts.tsx 的 LOW_SAMPLE_TEXT 常量逐字比对）。浏览器侧：真 Chromium 在 DOM 里数到 1 处提示文案，截图见 01_board_day.png
复核命令：python tools/verify.py   （看 V02-V03、V28、V31-V32）
实际输出原文：
[PASS] V02 mock 覆盖 1 个 low_sample 分组 contract_clause（样本 11）
[PASS] V03 low_sample 标记与样本数一致（<20 才算 low） 正常最小 391 ／ low 最大 11
[PASS] V28 low_sample 分组显示提示文案（DOM 里读到 1 处） 实测 1 处
[PASS] V31 三张截图都非空白（>8KB） 字节数 {'01_board_day.png': 130312, '02_board_week.png': 129288, '03_drilldown.png': 338448}
[PASS] V32 三张截图内容不同（不是同一张复制三次） [129288, 130312, 338448]

AC3 原文：下钻列表中不出现草稿正文字段（组件测试断言）
判定方式：数据侧：断言下钻接口返回的字段集合恰为 {draft_id, tool_key, scenario, reject_reason, rejected_at}，与正文字段名（body/content/text/draft_body/draft_content）无交集，且响应里写明需跳转并按权限校验。浏览器侧：真 Chromium 读下钻页表头的 data-colkey，断言恰为 4 列且不含正文字段；组件测试另断言每行只渲染 4 个单元格
复核命令：python tools/verify.py   （看 V08-V10、V29-V30）
实际输出原文：
[PASS] V08 下钻接口返回的字段里没有正文（只有 draft_id/场景/原因/时间） 字段 ['draft_id', 'reject_reason', 'rejected_at', 'scenario', 'tool_key']
[PASS] V09 下钻字段集合与设计一致 ['draft_id', 'reject_reason', 'rejected_at', 'scenario', 'tool_key']
[PASS] V10 接口响应里写明「不返回正文、查看正文需跳转并按权限校验」 本接口不返回草稿正文；查看正文请跳转复核队列并按权限校验
[PASS] V29 下钻页表格恰好 4 列，无正文字段 ['draft_id', 'scenario', 'reject_reason', 'rejected_at']
[PASS] V30 下钻页列键里没有正文字段 

AC4 原文：页面加载时没有任何外部域名的网络请求（网络面板截图）
判定方式：真 Chromium 监听 page.on('request')，记录全部请求的域名，断言只在 {127.0.0.1, localhost} 内、external_hosts 为空；另断言 dist/index.html 里不含 http(s) 外链、dependencies 里没有 echarts/chart.js/recharts/highcharts（图表为内联 SVG 自绘，天然不依赖 CDN）。完整请求清单落在 docs/network.json
复核命令：python tools/verify.py   （看 V13、V20、V26）
实际输出原文：
[PASS] V13 未引入图表库依赖（图表为内联 SVG 自绘，天然不依赖 CDN） 
[PASS] V20 dist/index.html 里没有外部链接（不引用 CDN） 
[PASS] V26 页面加载时**没有任何外部域名请求**（AC4 核心） 主机 ['127.0.0.1']；请求 6 个

汇总：SUMMARY 32/32 PASS
