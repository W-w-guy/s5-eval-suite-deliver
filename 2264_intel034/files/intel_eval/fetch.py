# -*- coding: utf-8 -*-
"""抓取层：robots.txt 先读、禁止路径默认不抓、每笔请求留痕。

为什么 robots 要真的解析而不是「跳过一下」：
AC 要求「robots 禁止路径被抓取数 = 0」，这既要**不抓**，也要能**证明没抓**。
所以每笔请求都写进 `attempts`，字段 `robots_violation` 明确标出该请求是否违反了 robots。
默认 `ignore_robots=False` 时违规数恒为 0；
测试里用 `ignore_robots=True` 故意抓一次禁止路径，指标会数出 1，CI 因此退出码非 0 —— 
这样「指标真的能抓到缺陷」才有证据，而不是永远显示 0。
"""
import urllib.error
import urllib.parse
import urllib.request

from . import guard

UA = "intel-eval/1.0 (+fictional test harness)"


class Robots:
    """极简 robots.txt 解析：只处理 User-agent: * 段下的 Disallow / Allow。"""

    def __init__(self, text: str):
        self.disallow, self.allow = [], []
        cur = None
        for line in (text or "").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), v.strip()
            if k == "user-agent":
                cur = v.strip().lower()
            elif cur in ("*", UA.lower()) and k in ("disallow", "allow") and v:
                (self.disallow if k == "disallow" else self.allow).append(v)

    def allowed(self, path: str) -> bool:
        """Allow 优先于 Disallow（简化的 RFC 9309 最长匹配）。"""
        path = path or "/"
        for a in self.allow:
            if a != "/" and path.startswith(a):
                return True
        for d in self.disallow:
            if d != "/" and path.startswith(d):
                return False
        return True


class Fetcher:
    def __init__(self, resolver: dict | None = None, timeout=5, ignore_robots=False):
        self.resolver = resolver or {}
        self.timeout = timeout
        self.ignore_robots = ignore_robots
        self.attempts = []
        self.robots_cache = {}
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _real(self, url: str) -> tuple:
        p = urllib.parse.urlparse(url)
        host = (p.hostname or "").lower()
        if host in self.resolver:
            ip, port = self.resolver[host]
            return "%s://%s:%d%s" % (p.scheme, ip, port, p.path or "/"), host
        return url, host

    def _get(self, url: str) -> tuple:
        real, _ = self._real(url)
        req = urllib.request.Request(real, method="GET")
        req.add_header("User-Agent", UA)
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except Exception as e:
            return 0, "%s: %s" % (type(e).__name__, e)

    def robots(self, base: str) -> Robots:
        if base not in self.robots_cache:
            st, txt = self._get(base.rstrip("/") + "/robots.txt")
            self.robots_cache[base] = Robots(txt if st == 200 else "")
        return self.robots_cache[base]

    def fetch(self, url: str) -> dict:
        p = urllib.parse.urlparse(url)
        base = "%s://%s" % (p.scheme, p.netloc)
        path = p.path or "/"
        allowed = self.robots(base).allowed(path)
        if not allowed and not self.ignore_robots:
            self.attempts.append({"url": url, "path": path, "status": None,
                                  "skipped_by_robots": True, "robots_violation": False})
            return {"url": url, "status": 0, "html": "", "skipped_by_robots": True,
                    "robots_violation": False}
        st, body = self._get(url)
        viol = (not allowed) and self.ignore_robots      # 真发出去了才可能违规
        self.attempts.append({"url": url, "path": path, "status": st,
                              "skipped_by_robots": False, "robots_violation": viol})
        return {"url": url, "status": st, "html": body if st == 200 else "",
                "skipped_by_robots": False, "robots_violation": viol}

    # ---- 供指标使用 ----
    def robots_violations(self) -> int:
        return sum(1 for a in self.attempts if a["robots_violation"])

    def fetched_count(self) -> int:
        return sum(1 for a in self.attempts if a["status"] == 200)


def build(env: str | None = None, ignore_robots=False) -> Fetcher:
    rm = guard.assert_safe_to_start(env)
    return Fetcher(rm, ignore_robots=ignore_robots)
