# CROSS_PLATFORM — 双平台实跑对照

两个平台都是**从 s5_eval_1998_double_review.zip 解压到全新空目录**后跑同一套命令。

## 1. 环境

| 项 | Windows | Ubuntu |
| --- | --- | --- |
| 主机 | DESKTOP-6BLPI5P | a-VMware |
| 系统 | Windows 11 (win32) | Ubuntu 24.04.5 LTS |
| Python | 3.11.7 | 3.12.3 |
| PostgreSQL | 16.2（pgserver 内嵌） | 16.2（pgserver 内嵌） |
| node / npm | **无** | v18.19.1 / 9.2.0 |
| Chromium | Playwright 内置 | playwright chromium-1255 |

## 2. 结果对照

| 检查项 | Windows | Ubuntu |
| --- | --- | --- |
| `sha256sum -c SHA256SUMS`（解压后） | 43 条 0 不一致 | 0 不一致 |
| AC0 真 PostgreSQL | PASS server_version=16.2 | PASS server_version=16.2 |
| AC0.1 alembic upgrade head | PASS | PASS |
| AC0.2 alembic_version 落库 | PASS 0001_eval_case_review | PASS |
| AC1 双人复核 | 4 passed | 4 passed |
| AC2 hash 变化重置 | 2 passed | 2 passed |
| AC3 页面三操作（真浏览器） | 3 passed（10.98s） | 3 passed（9.05s） |
| AC4 无权限 403 | 4 passed | 4 passed |
| AC5 全量 pytest | 17 passed | 17 passed |
| AC6.0 前端构建产物 | PASS | PASS |
| AC6.1 Vitest | **SKIP（本机无 node，未真跑）** | **10 passed** |
| AC0.3 alembic downgrade -1 | PASS | PASS |
| AC0.4 回滚后评审表已删除 | PASS | PASS |
| **SUMMARY** | **11/11 PASS · SKIP 1** | **12/12 PASS · SKIP 0** |
| 跑完整套后 `sha256sum -c` | 0 不一致 | 0 不一致 |

**两平台唯一的差别是 AC6.1 Vitest**：Windows 这台机器没有 node/npm，如实记 SKIP 并明确标注「未真跑，不计入通过」，没有伪装成通过。Ubuntu 侧真跑 2 个测试文件 10 项全过。

AC3 用的是**真 uvicorn + 真 React 构建产物 + 真 Chromium 点击**，不是静态 HTML 桩；两平台都跑通并重新生成 4 张截图。

## 3. 为什么截图不进 SHA256SUMS

`docs/shots/*.png` 每次跑 AC3 都会重新渲染，字节必然变化。把它列进校验和会导致「买家跑完测试再校验就报 4 条 FAILED」。所以 `SUMS_SKIP_EXT` 里排除 `docs/shots/`，同时上面那条「跑完整套后 0 不一致」就是这条设计的验证：截图被重写后，校验和依然全过。

## 4. 复跑命令

```
unzip s5_eval_1998_double_review.zip && cd s5_eval_1998_double_review
pip install -r requirements.txt
python -m playwright install chromium

cd frontend && npm ci && npm run build && npm test && cd ..

sha256sum -c SHA256SUMS
python verify.py --require-pg --require-node     # 严格模式：缺依赖即 FAIL，不用 SKIP 冒充通过
```

只跑后端（无 node 的机器）：`python verify.py --require-pg`，此时 AC6.1 记 SKIP。
