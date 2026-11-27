# 数据来源说明

## 一句话

本交付件内的全部业务数据均为**虚构生成**，不含任何真实个人信息、企业信息或第三方数据。
不需要访问任何客户系统、真实账号或外部接口。

## 虚构数据在哪

| 位置 | 内容 | 生成方式 |
|---|---|---|
| `tools/seed_demo.py` | 3 个评测用例 + 6 条复核记录 | 硬编码在本文件 `CASES` 常量里，脚本每次运行结果相同 |
| `tests/conftest.py` | 每个用例的 fixture（套件名/问题/要点） | 运行时用 `uuid4()` 生成 ID，文本为固定虚构串 |
| `docs/shots/fixture_case.json` | 截图所用的用例快照 | 由 `tools/seed_demo.py` 的同一份常量导出 |
| `docs/shots/*.png` | 4 张页面截图 | Playwright 打开真实 uvicorn + React 构建产物后截取（见 `tests/test_ac3_page.py`） |

## 虚构标识的规则

- 组织 ID 固定为 `11111111-1111-1111-1111-111111111111`
- 评审人 ID 固定为 `aaaaaaaa-...-0001` / `bbbbbbbb-...-0002` / `cccccccc-...-0003`
- 套件 key 形如 `suite-<8位随机hex>`，用例 key 形如 `case-<6位随机hex>`
- 业务文本一律以「虚构」开头，例如「虚构会员问：你们的产业对接活动下一次什么时候办？」
- 不含手机号、邮箱、身份证号、银行卡号、真实姓名、真实企业名

## PII 扫描（可复核）

```bash
# 扫描全部文本文件（含 frontend/src 的 .ts/.tsx），四类模式：手机号 / 邮箱 / 身份证 / 银行卡
python - <<'PY'
import os, re
pats = {
 "手机号": re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)'),
 "邮箱":   re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
 "身份证": re.compile(r'(?<!\d)\d{17}[\dXx](?!\d)'),
 "银行卡": re.compile(r'(?<!\d)\d{16,19}(?!\d)'),
}
n = hit = 0
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ('.pgdata', '__pycache__', '.git', 'node_modules')]
    for f in files:
        if not f.endswith(('.py','.md','.json','.html','.txt','.ini','.mako','.csv','.ts','.tsx')): continue
        n += 1
        t = open(os.path.join(root,f), encoding='utf-8', errors='replace').read()
        for k, rx in pats.items():
            for m in rx.finditer(t):
                hit += 1; print("HIT", k, os.path.join(root,f), m.group()[:30])
print("scanned=%d hits=%d" % (n, hit))
PY
```

**实测结果：`scanned=39 hits=0`。**

> 注：`scanned` 会随仓库内文件增减而变化，契约是 `hits=0`，不要拿文件数当契约。

## 截图是真的渲染出来的

截图由 `tests/test_ac3_page.py` 生成：起真实 uvicorn（连真实 PostgreSQL）+ 加载真实 React 构建产物，
用 Playwright 在浏览器里真实点击后截屏。不是手绘、不是拼图、不是静态 HTML 桩。复跑：

```bash
python -m pytest tests/test_ac3_page.py -v
```

## 依赖外部服务情况

**无。** 不调用任何第三方 API、不连客户数据库、不需要网络（装完依赖之后）。
