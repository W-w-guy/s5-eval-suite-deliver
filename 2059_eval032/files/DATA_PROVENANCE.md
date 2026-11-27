# DATA_PROVENANCE — 数据来源与可复核性

本交付包**不含任何真实个人信息或企业信息**。全部示例数据由脚本生成，可完整重放。

| 项 | 值 |
| --- | --- |
| 生成脚本 | `pkg/engine.py`（7 条虚构种子 + 3 档冻结日期场景） |
| 生成脚本 sha256 | `093c2b660c6dc77b549efd1291a10ba9473f6c661bd8bcaaccb1afaffdcbfe4e` |
| 状态机 sha256 | `f7428397233473b94c61f75dbe8f945cedff689eff3b1cad80bfa1075062d9d5` |
| 工作日算法 sha256 | `11bd70daca4a89ccd86c6ffba8a902e62ddd74ac3d024459a9552ba459fe75e2` |
| 掩码规则 sha256 | `1c9c84a4d6ca9bc9bf3dfb004430d3db1755ce097c22f2fd1c7d916102825912` |
| 迁移脚本 sha256 | `2452de7fe4b3032ef5c1230813d18ad40763d817b296eaad889db67a7e90392d` |
| 随机性 | **无随机**。种子数据为手写常量，finding_no 按年递增生成；所有日期为显式常量，工作日算法用整数序数（不读系统时间、不依赖 tzdata） |
| 种子 | 不适用（无随机数生成器） |
| 重跑命令 | `python pkg/engine.py` ／ `python -c "from pkg.db import reset_schema; reset_schema()"` |
| 数据库 | 真 PostgreSQL 16.2；建表由 Alembic 迁移完成（revision=0001），**不在 app 启动时 create_all**，避免买家先 pytest 再 alembic 撞 DuplicateTable |
| 产出规模 | 7 条红队发现 / 3 档冻结日期 / 2 张表 / pytest 77 项 |
| PII 说明 | 种子里的手机号、身份证、银行卡、邮箱与金丝雀**均为虚构**：号码由自选号段构造，金丝雀为三段随机码（3ZZP-9ERG-Y3SZ），不对应任何真实个人或企业。这些敏感串正是 AC3 的测试输入，断言的是它们**入库后已被掩码** |

## 虚构声明

发现编号、标题、复现步骤、工具名、角色名与全部日期均为虚构；文本中不出现客户名称。金丝雀与各类号码是**测试用的假数据**，其作用是验证「入库前掩码」这条规则是否真的生效。
