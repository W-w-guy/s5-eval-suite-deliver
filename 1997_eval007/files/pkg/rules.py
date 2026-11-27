# -*- coding: utf-8 -*-
"""检测规则配置：所有可调阈值与级别集中在此，便于改配置与做变异测试。

死开关不写 —— 关掉它断言不变的分支一律不留（会污染变异测试）。
"""

# ---- 8 类检测项（AC1 要求恰好 8 类，每类都要有命中与不命中夹具） ----
CHECK_KINDS = (
    "mobile",          # 手机号
    "landline",        # 固定电话
    "email",           # 邮箱
    "id_card",         # 身份证（含校验位）
    "bank_card",       # 银行卡（Luhn）
    "uscc",            # 统一社会信用代码（校验位通过且不是样例填充号段）
    "address",         # 详细地址（省市区 + 路号）
    "plate",           # 车牌号
)

# ---- 分级：error 阻断 CI 并返回非 0；warn 只进报告 ----
LEVEL = {
    "mobile": "error",
    "landline": "warn",
    "email": "warn",
    "id_card": "error",
    "bank_card": "error",
    "uscc": "error",
    "address": "warn",
    "plate": "warn",
    "org_name": "warn",       # 企业名称未带虚构标记
    "person_name": "warn",    # 中文人名未带（虚构）后缀
}
ERROR_LEVEL = "error"
WARN_LEVEL = "warn"

# ---- 附加两类（工单在 8 类之外点名要求告警的） ----
ORG_MARKERS = ("示例", "（虚构）", "(虚构)")
PERSON_SUFFIX = "（虚构）"

# ---- 阈值 ----
MOBILE_PREFIX = "1[3-9]"        # 手机号：1[3-9] 开头 11 位
BANK_MIN_DIGITS = 16            # 银行卡最短 16 位（Luhn 另外要求 >= 12）
PERSON_NAME_MIN = 2             # 2~4 字的疑似中文人名
PERSON_ROLES = ("记录人", "负责人", "联系人", "参会人", "审批人", "经办人", "审核人", "填表人")
PERSON_STOPWORDS = ("本次", "该单", "已确认", "待定", "未知", "暂无", "其他", "相关")
# 复姓：前两字若是复姓，人名取 3 字（如 欧阳明）；否则默认取 2 字。
# 不做 4 字贪婪匹配 —— 实测会把「张三负责」当成 4 字人名。
COMPOUND_SURNAMES = ("欧阳", "司马", "上官", "诸葛", "东方", "皇甫", "尉迟", "公孙",
                     "慕容", "长孙", "宇文", "司徒", "司空", "端木", "独孤", "南宫",
                     "西门", "夏侯", "令狐", "钟离")
PERSON_NAME_MAX = 4
USCC_DUMMY_RANGE = ("999999", 2, 8)   # 第 3~8 位（0 基 2:8）为 999999 视为样例填充
ADDRESS_MIN_LEN = 8             # 地址串最短长度

# ---- 性能预算（AC4：1000 条 <= 10 秒，留足余量后按毫秒计） ----
PERF_BUDGET_MS_1000 = 10000.0
