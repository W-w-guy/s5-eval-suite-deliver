# -*- coding: utf-8 -*-
"""mock 数据：7 个工具 + 1 个 low_sample 分组，外加 4 个查询接口的响应。

全部虚构、确定性生成（无随机数）。数据形态对齐 EVAL-039 的 4 个查询接口：
  /api/eval/quality/summary      指标卡 + 按工具对比 + 拒绝原因分布
  /api/eval/quality/trend        趋势折线（day / week 切换）
  /api/eval/quality/tools        工具列表（含 low_sample 标记）
  /api/eval/quality/rejected     下钻：最近被拒草稿（不含正文）
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)

LOW_SAMPLE_THRESHOLD = 20       # 工单：样本不足 20 不作结论

# 7 个工具（工单要求 mock 至少覆盖 7 个工具）
TOOLS = [
    {"key": "meeting_minutes", "name": "会议纪要生成", "samples": 1284},
    {"key": "weekly_report", "name": "周报草稿", "samples": 862},
    {"key": "intent_classify", "name": "问询意图分类", "samples": 2140},
    {"key": "lead_profile", "name": "线索画像提炼", "samples": 615},
    {"key": "kb_answer", "name": "知识问答", "samples": 1733},
    {"key": "copy_draft", "name": "文案改写", "samples": 508},
    {"key": "intel_brief", "name": "情报简报摘要", "samples": 391},
]
# 1 个 low_sample 分组（样本不足 20）
LOW_TOOL = {"key": "contract_clause", "name": "合同条款摘要", "samples": 11}

REJECT_REASONS = [
    {"key": "fact_error", "name": "事实错误"},
    {"key": "missing_field", "name": "字段缺失"},
    {"key": "style_mismatch", "name": "口径不符"},
    {"key": "too_verbose", "name": "篇幅过长"},
    {"key": "unsafe", "name": "合规风险"},
]

PROMPT_VERSIONS = [
    {"version": "v1", "released_on": "2026-09-15"},
    {"version": "v2", "released_on": "2026-10-20"},
    {"version": "v3", "released_on": "2026-11-18"},
]

# 确定性指标：按工具下标给出不同水平（虚构）
_METRIC = {
    "meeting_minutes": (0.812, 0.604, 118, 0.093),
    "weekly_report": (0.744, 0.512, 156, 0.121),
    "intent_classify": (0.917, 0.865, 42, 0.041),
    "lead_profile": (0.688, 0.437, 231, 0.158),
    "kb_answer": (0.856, 0.712, 77, 0.068),
    "copy_draft": (0.731, 0.548, 168, 0.112),
    "intel_brief": (0.795, 0.622, 134, 0.084),
    "contract_clause": (0.545, 0.273, 342, 0.273),      # low_sample
}


def tool_rows():
    """按工具对比的条形图数据（含 low_sample 标记）。"""
    rows = []
    for t in TOOLS + [LOW_TOOL]:
        ad, ex, p50, rej = _METRIC[t["key"]]
        rows.append({"tool_key": t["key"], "tool_name": t["name"],
                     "samples": t["samples"],
                     "adopt_rate": ad, "exact_adopt_rate": ex,
                     "modify_p50_chars": p50, "reject_rate": rej,
                     "low_sample": t["samples"] < LOW_SAMPLE_THRESHOLD})
    return rows


def summary():
    rows = tool_rows()
    total_samples = sum(r["samples"] for r in rows)
    # 指标卡：按样本数加权（low_sample 也计入总量，但单独标注不作结论）
    adopt = sum(r["adopt_rate"] * r["samples"] for r in rows) / total_samples
    exact = sum(r["exact_adopt_rate"] * r["samples"] for r in rows) / total_samples
    rej = sum(r["reject_rate"] * r["samples"] for r in rows) / total_samples
    return {
        "cards": {"adopt_rate": round(adopt, 4),
                  "exact_adopt_rate": round(exact, 4),
                  "modify_p50_chars": 118,
                  "reject_rate": round(rej, 4),
                  "pending_backlog": 47},
        "by_tool": rows,
        "reject_reasons": [
            {"key": "fact_error", "name": "事实错误", "count": 128},
            {"key": "missing_field", "name": "字段缺失", "count": 96},
            {"key": "style_mismatch", "name": "口径不符", "count": 74},
            {"key": "too_verbose", "name": "篇幅过长", "count": 51},
            {"key": "unsafe", "name": "合规风险", "count": 12},
        ],
        "low_sample_threshold": LOW_SAMPLE_THRESHOLD,
    }


def trend(granularity="day"):
    """趋势折线：day 给 14 个点，week 给 6 个点。数值确定性。"""
    if granularity not in ("day", "week"):
        raise ValueError("granularity 只能是 day 或 week")
    pts = []
    if granularity == "day":
        for i in range(14):
            pts.append({"label": "2026-11-%02d" % (14 + i),
                        "adopt_rate": round(0.76 + 0.004 * (i % 5) - 0.002 * (i % 3), 4),
                        "reject_rate": round(0.098 - 0.003 * (i % 4), 4)})
    else:
        for i in range(6):
            pts.append({"label": "W%d" % (43 + i),
                        "adopt_rate": round(0.752 + 0.012 * (i % 3), 4),
                        "reject_rate": round(0.104 - 0.006 * (i % 3), 4)})
    return {"granularity": granularity, "points": pts}


def prompt_compare():
    """提示词版本对比表：同一个工具各版本的采纳率与修改幅度 + 版本发布日期。"""
    out = []
    for t in TOOLS[:3]:
        base = _METRIC[t["key"]][0]
        for i, pv in enumerate(PROMPT_VERSIONS):
            out.append({"tool_key": t["key"], "tool_name": t["name"],
                        "version": pv["version"], "released_on": pv["released_on"],
                        "adopt_rate": round(base - 0.03 * (len(PROMPT_VERSIONS) - 1 - i), 4),
                        "modify_p50_chars": 118 + 22 * (len(PROMPT_VERSIONS) - 1 - i)})
    return {"rows": out}


def rejected(tool_key=None, limit=8):
    """下钻：最近被拒草稿。**只含 draft_id / 场景 / 拒绝原因 / 时间，不含正文。**"""
    rows = []
    pools = [tool_key] if tool_key else [t["key"] for t in TOOLS]
    for idx, tk in enumerate(pools):
        for i in range(min(limit, 8)):
            rows.append({
                "draft_id": "DR-%s-%03d" % (tk.upper()[:6], i + 1),
                "tool_key": tk,
                "scenario": ["入会引导", "续约沟通", "线索回访", "政策解读"][i % 4],
                "reject_reason": REJECT_REASONS[(i + idx) % len(REJECT_REASONS)]["name"],
                "rejected_at": "2026-11-%02dT%02d:15:00Z" % (20 + (i % 7), 9 + i),
            })
    return {"rows": rows[:limit * max(1, len(pools))],
            "note": "本接口不返回草稿正文；查看正文请跳转复核队列并按权限校验"}


def all_payloads():
    return {"summary": summary(), "trend_day": trend("day"), "trend_week": trend("week"),
            "prompt_compare": prompt_compare(), "rejected": rejected(),
            "tools": {"rows": tool_rows(), "low_sample_threshold": LOW_SAMPLE_THRESHOLD}}


def write_all(outdir=None):
    out = outdir or os.path.join(ROOT, "data")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "mock.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(all_payloads(), f, ensure_ascii=False, indent=1, sort_keys=True)
    return len(TOOLS), len(TOOLS) + 1


if __name__ == "__main__":
    a, b = write_all()
    print("WROTE normal_tools=%d all_groups=%d" % (a, b))
