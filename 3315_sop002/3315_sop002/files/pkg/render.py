# -*- coding: utf-8 -*-
"""新会员入会引导 SOP 渲染。"""
import engine as E
from kitlib import sop
from kitlib import tables as T


def md_head():
    L = ["# 新会员入会引导 SOP：欢迎话术、资料清单与检查项（全部虚构）", "",
         "> 企业名称、姓名、编号与条款均为**虚构**，仅用于流程说明与开发对照。",
         "> 话术模板见 `welcome_scripts.csv`；资料清单见 `materials.csv`；",
         "> 能力卡引导问题见 `card_questions.md`；检查项表见 `checklists.md`。", "",
         "## 一、欢迎话术 3 版（企业微信 / 短信 / 邮件）", "",
         "| 编号 | 渠道 | 变量数 | 字数（变量计 0） | 原始长度 | 上限 |",
         "| --- | --- | --- | --- | --- | --- |"]
    L += ["| %s | %s | %d | %d | %d | ≤%d |"
          % (s["id"], s["channel"], len(sop.vars_in(s["body"])),
             sop.char_count(s["body"]), len(s["body"]), E.SMS_LIMIT) for s in E.SCRIPTS]
    L += ["", "> **字数口径说明**：上表「字数（变量计 0）」把 `{企业名称}` 这类占位符整体记为 0 字，",
          "> 是最乐观的口径；「原始长度」是含占位符字面的长度，是最严格的口径。",
          "> 两列都必须 ≤150 才判合规——只看第一列会出现「渲染后粘进短信就超长」的坑。", "",
          "三版的变量占位与正文：", ""]
    for s in E.SCRIPTS:
        L += ["### %s %s" % (s["id"], s["channel"]), "",
              "- 变量：%s" % "、".join("`{%s}`" % v for v in sop.vars_in(s["body"])),
              "", "```", s["body"], "```", ""]
    L += ["## 二、入会资料清单（必填 %d 项 / 可选 %d 项）"
          % (sum(1 for m in E.MATERIALS if m["required"]),
             sum(1 for m in E.MATERIALS if not m["required"])), ""]
    L += T.grid(["编号", "材料", "必填/可选", "用途", "不提供时的处理"],
                [[m["id"], m["name"], "**必填**" if m["required"] else "可选",
                  m["why"], m["fallback"]] for m in E.MATERIALS])
    L += ["", "> 必填项一律给「替代方案」而非「不给就办不了」——先开通、后补交，避免卡在第一步。",
          "> 门禁登记只采集**姓名、所属企业、人数**，证件号一律不收（最少必要信息原则）。", ""]
    L += ["## 三、能力卡共建 10 个引导问题", ""]
    L += ["%d. %s" % (i, q) for i, q in enumerate(E.CARD_QUESTIONS, 1)]
    L += ["", "> 用法：按顺序提问，未答项标注「待补」；能力卡须经会员确认后才入库。",
          "> 开场先说明用途（帮对方做撮合），避免像问卷审问。", "",
          "开场话术：", "", "```", E.CARD_SCRIPT["body"], "```", ""]
    L += ["## 四、步骤与检查项（每步 2~4 条可勾选）", ""]
    L += ["| 步骤 | 名称 | 负责岗位 | 口径 | 时限 | 检查项数 |", "| --- | --- | --- | --- | --- | --- |"]
    L += ["| %s | %s | %s | %s | %s | %d |"
          % (s["id"], s["name"], s["role"], s["tmode"],
             ("%d 天" % (s["hrs"] // 24)) if s["tmode"] == "natural" else ("%d 小时" % s["hrs"]),
             len(s["checklist"])) for s in E.STEPS]
    L += ["", "## 五、责任矩阵", ""]
    L += sop.matrix(E.STEPS, E.ROLES)
    L += ["", "R = 负责；C = 协作。", "",
          "## 六、时限口径", "",
          "- `work`：只在工作日 09:00–18:00 内消耗，跨夜与跨周末顺延（S01~S07）；",
          "- `natural`：自然时间连续累加，用于「入会满 30 天回访」（S08）。",
          "", "> 以「%s（周三）10:00 入会审批通过」为统一起算点，各步推算截止见 `join_expected.csv`。" % E.BASE.strftime("%Y-%m-%d"), ""]
    return L


def md_section(c):
    d = E.due(c["start"], c["hrs"], c["tmode"])
    unit = ("%d 天" % (c["hrs"] // 24)) if c["tmode"] == "natural" else ("%d 小时" % c["hrs"])
    L = ["## %s %s（情形：%s）" % (c["id"], c["name"], "、".join(c["cats"])), "",
         "| 项 | 值 |", "| --- | --- |",
         "| 负责岗位 | %s |" % c["role"],
         "| 协作岗位 | %s |" % ("、".join(c.get("support") or []) or "无"),
         "| 时限 | %s（口径 `%s`） |" % (unit, c["tmode"]),
         "| 时限说明 | %s |" % c["desc"],
         "| 起算点 | %s |" % c["start"].strftime("%Y-%m-%d %H:%M"),
         "| 推算截止 | %s |" % d.strftime("%Y-%m-%d %H:%M"), "",
         "**必填输出**（%d 项）" % len(c["outputs"]), ""]
    L += ["- [ ] %s" % o for o in c["outputs"]]
    L += ["", "**可勾选检查项**（%d 条）" % len(c["checklist"]), ""]
    L += ["- [ ] %s" % k for k in c["checklist"]]
    L += ["", "结果：负责岗位 **%s** / 时限 **%s** / 截止 **%s** / 必填输出 **%d** 项 / 检查项 **%d** 条"
          % (c["role"], unit, d.strftime("%Y-%m-%dT%H:%M"),
             len(c["outputs"]), len(c["checklist"])), ""]
    return L
