# 验收对应表（ACCEPTANCE）—— #2008 S5-EVAL-012

本文件逐条回答四条验收标准：**判定方式 / 复核命令 / 实际输出原文**。

平台复核只读文本、不执行代码（`runtime_verified: false`），所以这里贴的是**真跑出来的输出原文**，
不是"已通过"这类结论性描述。所有命令可在解压后的包根目录直接重跑。

环境：Python 3.11+，零第三方运行时依赖（pytest 除外，仅跑单测需要）。

---

## AC1　cases.jsonl 恰有 35 条，eval-lint 与 eval-pii-scan 均通过

**判定方式**：数 `data/cases.jsonl` 行数；`eval-lint` 校验字段与四类分布；`eval-pii-scan` 用正则扫手机号/邮箱。
**复核命令**：`python verify_2008.py`（内含以下断言）

```
[ OK ] AC1 cases.jsonl 恰 35 条 | 35
[ OK ] AC1 分布 常规20/陷阱9/无合适6 | {'normal': 20, 'trap': 9, 'none': 6}
[ OK ] AC1 每条 context 含 8–15 个候选资源 | 8..15
[ OK ] AC1 每个资源都带 行业/阶段/服务类型/站点/opt_out/conflict_with 
[ OK ] AC1 每条含 1 家虚构会员企业需求 
[ OK ] AC1 每条 gold 资源 1–3 个（无合适资源档为 0） 
[ OK ] AC1 eval-pii-scan 通过（无手机号/邮箱） | ([], [])
[ OK ] AC1 eval-lint 通过（字段与分布均合法） 
```

**实测**：35 条，分布 常规 20 / 陷阱 9 / 无合适资源 6；pii 命中 0。

---

## AC2　9 条陷阱用例中被排除的资源都写在 forbidden_points 中（脚本检查）

**判定方式**：不只查"有没有这个字段"，而是把 `forbidden_points` 声明的资源 ID 与
该资源自身的 `opt_out` / `conflict_with` 字段**逐条比对**，必须完全一致。
另加一条：陷阱资源必须在行业与服务类型上都与需求吻合（表面高度匹配），
否则它考不出"敢不敢排除一个看起来合适的"。

```
[ OK ] AC2 陷阱用例恰 9 条 | 9
[ OK ] AC2 9 条陷阱都写了 forbidden_points 
[ OK ] AC2 声明的 forbidden_points 与资源的 opt_out/conflict_with 完全一致 
[ OK ] AC2 陷阱资源表面高度匹配（行业+服务类型都吻合） 
```

---

## AC3　recall@3 与 MRR 脚本对 5 组手算样例结果一致（单元测试通过）

**判定方式**：指标函数本身用手算样例锁定，测函数不测端到端输出。
如 `(['A'], ['B','A']) → recall@3=1.0, MRR=0.5`。

```
[ OK ] AC3 recall@3 与 MRR 对 5 组手算样例结果一致 | [(['A'], ['A'], 1.0, 1.0), (['A'], ['B', 'A'], 1.0, 0.5)]
[ OK ] AC3 有对应单元测试且通过 | .................                       
```

单元测试实跑（`python -m pytest tests -q`）：

```
..........................                                               [100%]
```

---

## AC4　用 echo mock 跑通 eval-run 并在报告中显示 recall@3

**判定方式**：跑 `python -m match_eval`，退出码 0，生成 Markdown/JSON 报告，报告内含三项指标。
另有两个破坏开关证明指标不是恒真。

```
[ OK ] AC4 echo mock 跑通 eval-run（rc=0） | rc=0
[ OK ] AC4 命令行输出含 recall@3 
[ OK ] AC4 生成 Markdown 报告 
[ OK ] AC4 报告含「recall@3」「MRR」「推荐理由有据率」 
[ OK ] AC4 三项指标均达标 | r=1.0000 m=1.0000 p=1.0000
[ OK ] AC4 未推荐任何被排除资源 
[ OK ] AC4 6 条无合适资源全部输出「暂无合适匹配」 | 6
[ OK ] AC4 --break-optout 能触发 forbidden（指标可证伪） | 6
[ OK ] AC4 --break-reason 能打掉理由有据率 
```

**eval-run 实际输出原文**：

```
cases=35 with_gold=29 no_gold=6
recall@3=1.0000 mrr=1.0000 reason=1.0000 forbidden=0 no_match=6/6
report=C:\Users\MSI\AppData\Local\Temp\p2008_bq2e6k6x\reports\match_v1.md
THRESHOLD OK
```

**破坏开关实际输出**（证明指标可被打破）：

```
--break-optout : forbidden 命中 6 次，rc=1
--break-reason : 推荐理由有据率被打掉，rc=1
```

---

## 汇总

```
TOTAL 24, PASS 24, FAIL 0
[ OK ] pytest 全套通过 | ..........................
```

## 数据来源（摘要）

全部 35 条用例与 35 份候选上下文均为**虚构合成，无外部来源**：不使用公开数据集、不抓取网页、
不使用客户数据。生成脚本 `tools/gen_cases.py`（sha256 见 `DATA_PROVENANCE.md`），
随机种子 `random.Random(2008)` 写死在脚本内，重跑命令 `python tools/gen_cases.py`。
pii 扫描：扫描 52 个文件，命中 0 处。详见包内 `DATA_PROVENANCE.md`。

```
[ OK ] 小节「数据类别」非空 
  [ OK ] 小节「数据来源」非空 
  [ OK ] 小节「生成方式（可复现）」非空 
  [ OK ] 小节「生成时间与版本」非空 
  [ OK ] 小节「真实性声明」非空 
  [ OK ] 小节「校验证据」非空 
  [ OK ] 小节「第三方依赖与许可」非空 
  [ OK ] 小节「局限」非空 
  [ OK ] 生成脚本哈希一致: tools/gen_cases.py 
  [ OK ] 数据来源 非模糊 
  [ OK ] 真实性声明含「无真实个人信息」 
  [ OK ] 真实性声明含「无真实企业信息」 
  [ OK ] 真实性声明含「无客户数据」 
  [ OK ] 校验证据含 命中数 与 扫描文件数 
  [ OK ] 局限 已如实填写 
PROVENANCE PASS（15/15）
```
