# CROSS_PLATFORM — 双平台实跑与产物一致性

本单含前端工程，**Windows 侧无 node/npm**，因此浏览器与构建相关的断言只在 Ubuntu 侧真跑；
Windows 侧如实记录为「未跑」而不是「通过」。判据以 Ubuntu 侧的真跑结果为准。

## 环境

| 平台 | 版本 | 能否跑前端 |
| --- | --- | --- |
| Windows 11 | Python 3.11.7 / **无 node** | 否 —— 如实记录为未跑 |
| Ubuntu 24.04 | Python 3.12.3 / node 18.19.1 / npm 9.2.0 / Playwright + Chromium | 是 —— 真构建、真 Vitest、真浏览器 |

## Ubuntu 侧实跑结果（全新解压目录）

| 步骤 | 结果 |
| --- | --- |
| `npm ci` | rc=0，安装 151 个包 |
| `npm run build` | rc=0，产出 dist/assets + index.html |
| `npm test` | **Test Files 2 passed / Tests 17 passed** |
| `python tools/verify.py` | **SUMMARY 32/32 PASS** |
| `sha256sum -c SHA256SUMS.txt` | **26 条全 OK、0 条不一致** |

## 浏览器侧硬证据（AC1/AC2/AC3/AC4）

| 项 | 实测 |
| --- | --- |
| 条形图条数 | 8（7 正常工具 + 1 low_sample） |
| low_sample 提示文案 | DOM 中 1 处 |
| 点击「按周」后 | 界面 label 变为 `week` |
| 下钻页表头列 | `[draft_id, scenario, reject_reason, rejected_at]`（无正文字段） |
| **页面加载的请求域名** | **仅 `127.0.0.1`，external_hosts 为空，共 6 个请求** |
| 截图 | 3 张（日视图 130,312 B / 周视图 129,288 B / 下钻页 338,448 B） |

## 产物逐字节比对

| 文件 | Windows sha256 前 16 位 | Ubuntu 前 16 位 | 一致 |
| --- | --- | --- | --- |
| `pkg/mockdata.py` | `44eaf07a2bde6207` | `44eaf07a2bde6207` | 是 |
| `frontend/src/pages/QualityBoard.tsx` | `96ae4aa579c9ab90` | `96ae4aa579c9ab90` | 是 |
| `frontend/src/pages/RejectedList.tsx` | `f038640655ba0431` | `f038640655ba0431` | 是 |
| `frontend/src/charts.tsx` | `830e6b6e89e2ef12` | `830e6b6e89e2ef12` | 是 |
| `frontend/src/api.ts` | `34e49496113cf7f7` | `34e49496113cf7f7` | 是 |
| `data/mock.json` | `b9ef8fcbb2d9d533` | `b9ef8fcbb2d9d533` | 是 |
| `README.md` | `7bae4dd6c7e9bd17` | `7bae4dd6c7e9bd17` | 是 |
| `ACCEPTANCE.md` | `7dee1294f80eed87` | `7dee1294f80eed87` | 是 |
| `DATA_PROVENANCE.md` | `0b556699eeb0e31d` | `0b556699eeb0e31d` | 是 |

这 9 个文件两侧**逐字节相同**。mock.json 由 mockdata.py 确定性生成（无随机数），页面与图表均为手写常量，重跑字节级一致。

## 哪些产物不进 SHA256SUMS

- `frontend/dist/` —— 每次构建都变；
- `docs/shots/` 与 `docs/network.json` —— 每次运行都变；
- `verify_logs/` —— 实跑日志快照。

四者都打进 zip（买家可直接预览页面与截图），但**不参与 `sha256sum -c`** —— 否则买家跑完一遍校验就会 mismatch。这条已实测：Ubuntu 侧全新解压 → npm ci → build → verify 之后，26 条仍全 OK。

## 原始日志

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `UBUNTU_20261127.log` | 3,334 | `8baabc8cfef785b890be682dbb7ff86a797fa14de4d960302f60bd4ef5b68062` |
| `WINDOWS_20261127.log` | 见文件 | 仅记录「无 node，前端断言未跑」 |
