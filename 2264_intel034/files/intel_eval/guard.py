# -*- coding: utf-8 -*-
"""运行环境保护：测试解析覆盖只允许在测试/开发环境启用。

AC2 要求「生产配置下设置 INTEL_TEST_RESOLVER 时服务拒绝启动（有测试）」。
它防的是真实事故形态：为了让测试能访问虚构域名而加的解析覆盖，
一旦带着它上线，生产抓取就会被导向内部靶场（或反过来被外部域名劫持）。
所以这里做成 **fail-closed**：不确定就拒。
"""
import os

ENV_VAR = "APP_ENV"
RESOLVER_VAR = "INTEL_TEST_RESOLVER"
PROD_ENVS = {"production", "prod", "live", "release"}


class UnsafeConfigError(RuntimeError):
    """生产环境带测试配置 —— 必须拒绝启动，不允许 warning 后继续。"""


def env_name(explicit: str | None = None) -> str:
    return (explicit or os.environ.get(ENV_VAR) or "").strip().lower()


def is_production(explicit: str | None = None) -> bool:
    return env_name(explicit) in PROD_ENVS


def resolver_map(raw: str | None = None) -> dict:
    """解析 'host=ip:port,host2=ip:port'。

    只接受「主机名 -> 本机/内网地址」。域名本身用 .example 保留域名，不解析真实 DNS。
    """
    raw = os.environ.get(RESOLVER_VAR) if raw is None else raw
    if not raw:
        return {}
    out = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise UnsafeConfigError("%s 格式错误：%r（应为 host=ip:port）" % (RESOLVER_VAR, part))
        host, addr = part.split("=", 1)
        host, addr = host.strip().lower(), addr.strip()
        if ":" not in addr:
            raise UnsafeConfigError("%s 缺少端口：%r" % (RESOLVER_VAR, part))
        ip, port = addr.rsplit(":", 1)
        if not port.isdigit():
            raise UnsafeConfigError("%s 端口非法：%r" % (RESOLVER_VAR, part))
        if not (ip.startswith(("127.", "10.", "192.168.", "172.")) or ip == "localhost"):
            raise UnsafeConfigError(
                "%s 只能指向本机或内网地址，拒绝 %s（会变成对外发起请求）" % (RESOLVER_VAR, ip))
        out[host] = (ip, int(port))
    return out


def assert_safe_to_start(explicit_env: str | None = None, raw_resolver: str | None = None) -> dict:
    """启动自检。生产环境 + 测试解析覆盖 = 直接抛异常，绝不降级为 warning。

    返回解析映射（测试/开发环境里允许非空）。
    """
    raw = os.environ.get(RESOLVER_VAR) if raw_resolver is None else raw_resolver
    if is_production(explicit_env) and raw:
        raise UnsafeConfigError(
            "拒绝启动：%s=%s 与 %s=%s 同时存在。测试解析覆盖只允许在 test/dev 使用。"
            % (ENV_VAR, env_name(explicit_env), RESOLVER_VAR, raw))
    return resolver_map(raw)


def require_test_env(explicit_env: str | None = None) -> None:
    """需要解析覆盖的子命令（如连虚构站点）显式要求非生产环境。"""
    if is_production(explicit_env):
        raise UnsafeConfigError("该操作需要测试/开发环境，当前 %s=%s" % (ENV_VAR, env_name(explicit_env)))
