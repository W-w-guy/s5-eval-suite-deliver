# ACCEPTANCE — 逐条 AC 判定（原文 / 判定方式 / 复核命令 / 实际输出原文）

以下输出为 tools/verify.py 在交付包内的真实 stdout，未经修改。

AC1 原文：8 种字段类型各有正例与反例测试且全部通过
判定方式：断言字段类型恰 8 种；再逐类型统计「该字段全对」的正例数与「该字段有 wrong/missing/extra」的反例数，两者都必须 ≥1；最后跑 pytest 全量用例，全部通过
复核命令：python tools/verify.py   （看 V01-V02）
实际输出原文：
[PASS] V01 字段类型恰 8 种 类型 ['date', 'enum', 'list', 'money_fen', 'rate_bp', 'string', 'summary', 'uscc']
[PASS] V02 8 种类型各自都有正例与反例用例 缺 []；明细 {'date': (31, 3), 'enum': (31, 3), 'list': (27, 6), 'money_fen': (30, 4), 'rate_bp': (30, 4), 'string': (30, 4), 'summary': (30, 4), 'uscc': (31, 3)}

AC2 原文：付款节点列表多 1 项、少 1 项时分别计入 extra 与 missing
判定方式：构造三个用例：完全一致（3 项全 correct）、多 1 项（必须 extra=1 且 missing=0）、少 1 项（必须 missing=1 且 extra=0）；再单独断言「顺序打乱不影响结论」，证明是按 seq 对齐而非按下标
复核命令：python tools/verify.py   （看 V03-V05）
实际输出原文：
[PASS] V03 付款节点多 1 项 → extra=1 且 missing=0 实测 {'correct': 3, 'wrong': 0, 'missing': 0, 'extra': 1}
[PASS] V04 付款节点少 1 项 → missing=1 且 extra=0 实测 {'correct': 2, 'wrong': 0, 'missing': 1, 'extra': 0}
[PASS] V05 付款节点完全一致时 3 项全 correct 实测 {'correct': 3, 'wrong': 0, 'missing': 0, 'extra': 0}

AC3 原文：金额相差 1 分即判 wrong；critical 字段错误时用例不通过
判定方式：构造金额差 1 分的用例，断言 wrong=1 且 correct=0；构造 5 个 critical 出错的用例（金额差 1 分、金额用浮点、信用代码错一位、金额缺失、信用代码长度不足），断言全部 passed=False 且 critical_hit 非空；再用一个非 critical 单错用例做正向对照（仍应通过）
复核命令：python tools/verify.py   （看 V06-V10）
实际输出原文：
[PASS] V06 金额相差 1 分判 wrong（无容差） 实测 {'correct': 0, 'wrong': 1, 'missing': 0, 'extra': 0}
[PASS] V07 金额完全相等判 correct 
[PASS] V08 critical 字段出错时用例不通过 实测 {'C09': False, 'C10': False, 'C15': False, 'C28': False, 'C29': False}
[PASS] V09 critical_hit 记录了出错的 critical 字段 实测 {'C09': ['total_amount'], 'C10': ['total_amount'], 'C15': ['buyer_uscc'], 'C28': ['total_amount'], 'C29': ['buyer_uscc']}
[PASS] V10 非 critical 字段单错不触发 critical_hit 且仍通过（正向对照） 

AC4 原文：precision、recall、F1 计算结果与手算表一致
判定方式：手算表由 fractions.Fraction 整数运算独立生成（与评分器的浮点实现是两条路径），逐用例逐字段比对到小数点后 12 位；再断言手算表自身自洽（分子分母与计数对得上）
复核命令：python tools/verify.py   （看 V11-V12）
实际输出原文：
[PASS] V11 全部用例的 precision/recall/F1 与手算表逐字符一致 不一致 []
[PASS] V12 手算表内部自洽（分子分母与计数对得上） 异常 []

汇总：SUMMARY 20/20 PASS
