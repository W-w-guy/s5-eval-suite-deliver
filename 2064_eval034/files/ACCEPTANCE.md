# ACCEPTANCE — 逐条 AC 判定（原文 / 判定方式 / 复核命令 / 实际输出原文）

以下输出为 tools/verify.py 在交付包内的真实 stdout，未经修改。

AC1 原文：通过率下降 4 个百分点时判定失败，下降 2 个百分点时通过（pytest 通过）
判定方式：构造两个运行：通过率 88%（比基线 92% 降 4.0000pp）与 90.4%（降 1.6000pp）。断言降幅分别算得恰好 4 与 1.6、前者 verdict=fail、后者 verdict=pass；并断言两个场景的 must 翻转都没到 3 条，说明失败只能归因于通过率降幅、不是被另一条判据顺带触发；再用 compare 命令实测退出码（失败 1 / 通过 0）。另加取整探针：降 3.2000pp 必须判失败
复核命令：python tools/verify.py   （看 V02-V10）
实际输出原文：
[PASS] V02 降 4 个百分点时降幅算得恰好 4 实测 4
[PASS] V03 降 4 个百分点时判定失败 verdict=fail
[PASS] V04 降 2pp 场景的降幅是 1.6（125 分母下的精确值） 实测 1.6
[PASS] V05 降幅低于阈值时判定通过 verdict=pass
[PASS] V06 两场景的 must 翻转都未达 3 条（结论只由通过率降幅决定） 4pp 场景 2 条 / 2pp 场景 1 条
[PASS] V07 取整探针：降幅 3.2000 个百分点按精确值参与判定 实测 3.2
[PASS] V08 降 3.2 个百分点（>3）时判定失败（若四舍五入成 3 会假通过） verdict=fail
[PASS] V09 compare 命令实测退出码 1 且摘要标 FAIL rc=1
[PASS] V10 通过场景的退出码为 0（正向对照） rc=0

AC2 原文：重跑 2 次中有 1 次通过的用例被标为 flaky 而不计入退化（测试断言）
判定方式：构造 3 条翻转用例（都含 must 要点），重跑记录为 [False,True] / [True,False] / [False,False]。断言前两条被标 flaky、只有两次都失败的第三条留在 regression 清单、must 翻转数从 3 降到 1、整体判 pass；再做一次反向对照：把 FLAKY_EXCLUDED_FROM_REGRESSION 关掉后 must 翻转就是 3 条并判 fail，证明剔除动作真的起了作用
复核命令：python tools/verify.py   （看 V11-V18）
实际输出原文：
[PASS] V11 flaky 场景里翻转用例共 3 条 实测 3 条 ['KB-113', 'KB-114', 'KB-115']
[PASS] V12 其中 2 条被标为 flaky（重跑 2 次里各通过过 1 次） flaky=['KB-113', 'KB-114']
[PASS] V13 只有两次都失败的 KB-115 留在 regression 清单 regressions=['KB-115']
[PASS] V14 flaky 剔除后 must 翻转只剩 1 条（未达阈值 3） must_flips=['KB-115']
[PASS] V15 3 条翻转全部含 must 要点，但剔除 flaky 后不判退化 verdict=pass（若不剔除会是 3 条 -> fail）
[PASS] V16 反向对照：若把 flaky 计入，must 翻转 3 条即判失败（证明剔除真的起了作用） must=3 verdict=fail
[PASS] V17 flaky 条目带重跑明细可供复核 [('KB-113', [False, True]), ('KB-114', [True, False])]
[PASS] V18 flaky 场景命令退出码为 0 rc=0

AC3 原文：suite_version 不同时只比较共有用例，结果中写明比较范围
判定方式：构造一份 v2 运行：删掉 12 条、新增 10 条、总 123 条。断言识别出版本不同、只比较共有 113 条、基线独有 12 条与本次独有 10 条被排除、note 里写明范围；并对照版本相同的运行比较全部 125 条。再断言新增的 10 条虽全失败但不进 regression 清单，以及不做共有用例限制时分母会变成 123（与实际 113 不同）
复核命令：python tools/verify.py   （看 V19-V26）
实际输出原文：
[PASS] V19 识别出版本不同（基线 v1 / 本次 v2） same=False
[PASS] V20 只比较共有的 113 条用例 compared=113
[PASS] V21 基线独有 12 条、本次独有 10 条被排除在比较之外 only_base=12 only_cur=10
[PASS] V22 结果里写明比较范围 note=suite_version 不同（基线 v1 / 本次 v2），只比较共有的 113 条用例；基线独有 12 条、本次独
[PASS] V23 版本相同时比较全部 125 条（对照） compared=125
[PASS] V24 不做共有用例限制时分母是 123（含新增 10 条），与实际比较的 113 条不同 naive 分母=123 drop=0.9431 ｜ 实际分母=113 drop=0.8850
[PASS] V25 新增的 10 条全失败，但不计入本次比较（不出现在 regression 清单里） 新增 10 条，regression=['KB-113']
[PASS] V26 版本差异场景命令退出码为 0 rc=0

AC4 原文：选择有执行错误的运行作为基线时命令报错
判定方式：对两个非法运行分别实测 set 命令：status=failed 与 status=completed 但 errors 非空。断言两者退出码都是 2（**命令报错**，不是判定失败 1）且输出含明确拒绝原因；再对合规运行做正向对照（退出码 0）；另断言不填理由、缺 eval.baseline.set 权限同样报错，以及 compare 遇到有执行错误的基线也会抛错
复核命令：python tools/verify.py   （看 V27-V34）
实际输出原文：
[PASS] V27 set 拒绝 status=failed 的运行（命令报错而非判定失败） rc=2
[PASS] V28 set 输出明确的拒绝原因（status=failed） [eval-baseline] 拒绝设置基线：运行 status='failed'，只有 completed 的运行可作基线
[PASS] V29 set 拒绝 errors 非空的运行 rc=2
[PASS] V30 set 输出明确的拒绝原因（errors 非空） [eval-baseline] 拒绝设置基线：运行存在执行错误 ['3 条用例执行异常']，不能作为基线
[PASS] V31 合规运行可以被设为基线（正向对照） rc=0
[PASS] V32 不填理由时 set 报错 rc=2
[PASS] V33 缺少 eval.baseline.set 权限时 set 报错 rc=2
[PASS] V34 compare 遇到有执行错误的基线同样报错 

汇总：SUMMARY 43/43 PASS
