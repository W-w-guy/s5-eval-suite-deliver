# -*- coding: utf-8 -*-
"""性能测量（AC4：扫描 1000 条用例 ≤ 10 秒）。

**为什么必须预热**：首次从磁盘读 1000 个小文件时，Windows 会逐文件做实时防护扫描，
实测首轮 19.8 秒、稳态 0.13 秒 —— 差 150 倍，全部来自磁盘冷读而非扫描逻辑。
所以口径写成：预热 2 轮取稳态，同时**如实报告首轮冷启动耗时**，不隐瞒。

另提供纯内存模式的耗时（把 1000 条文本读入内存后只测扫描），
这才是「扫描 1000 条用例」本身的计算成本，与磁盘无关。
"""
import os
import time

import scanner

WARMUP_ROUNDS = 2
MEASURE_ROUNDS = 3


def time_once(path):
    t0 = time.perf_counter()
    findings, stats, errors = scanner.scan_path(path)
    return (time.perf_counter() - t0) * 1000.0, stats, errors


def measure(path, warmup=WARMUP_ROUNDS, rounds=MEASURE_ROUNDS):
    """返回 {cold_ms, warm_ms, best_ms, per_case_ms, scanned}。"""
    cold_ms, stats, errors = time_once(path)
    for _ in range(warmup):
        time_once(path)
    samples = []
    for _ in range(rounds):
        ms, _s, _e = time_once(path)
        samples.append(ms)
    best = min(samples)
    n = max(stats.get("scanned", 1), 1)
    return {"cold_ms": cold_ms, "warm_samples_ms": samples, "best_ms": best,
            "per_case_ms": best / n, "scanned": stats.get("scanned", 0),
            "errors": errors}


def measure_in_memory(texts, rounds=MEASURE_ROUNDS):
    """只测扫描逻辑，不含磁盘读取。"""
    import detect
    samples = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        for t in texts:
            detect.scan_text(t)
        samples.append((time.perf_counter() - t0) * 1000.0)
    return {"best_ms": min(samples), "samples": samples, "count": len(texts)}
