# -*- coding: utf-8 -*-
"""数据源管理器：并发探测 / 延迟排序 / 能力识别 / 熔断冷却 / 状态持久化。

设计要点
--------
1. **并发探测**：所有候选源同时探测，总耗时 = 最慢的那个源，
   而不是「坏源超时 × 坏源个数」（旧实现串行探测最慢要等约 280 秒）。
2. **能力识别**：区分「网络不通」与「不支持 /v0/me 鉴权」。
   后者（如 anibt 镜像）收藏端点完全正常，绝不能被当成「Token 无效」。
3. **熔断冷却**：某个源连续失败到阈值后进入冷却期，冷却期内不再尝试，
   避免每次导出都被坏源拖慢；指数增长，上限 15 分钟。
4. **持久化**：健康快照写入 输出/.sources.json，下次启动可立即展示；
   用户手动指定的源写入 config.json 的 "source" 字段。
"""

import json
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor  # noqa: F401  (保留给外部调用)
from pathlib import Path

from .constants import (
    API_BASES,
    PROBE_BUDGET,
    PROBE_MIN_BUDGET,
    PROBE_TIMEOUT,
    SOURCE_BY_BASE,
    SOURCE_COOLDOWN_BASE,
    SOURCE_COOLDOWN_MAX,
    SOURCE_FAIL_THRESHOLD,
)

# 探测时用于验证「这个源确实能提供 Bangumi 数据」的公开条目
# （id=2 是 Bangumi 上的固定条目，无需登录即可读取）
PROBE_SUBJECT_ID = 2


def source_meta(base):
    """取源的元数据；未知源（用户自定义）返回一个合理的默认值。"""
    meta = SOURCE_BY_BASE.get(base)
    if meta:
        return meta
    return {"base": base, "name": base, "kind": "custom", "auth": True,
            "note": "自定义数据源"}


class SourceManager:
    """线程安全的数据源管理器。"""

    def __init__(self, state_path=None, log=None):
        self._lock = threading.RLock()
        self._log = log
        self._state_path = Path(state_path) if state_path else None
        # base -> {"ok","ms","status","auth","error","checked_at"}
        self._health = {}
        # base -> 连续失败次数
        self._failures = {}
        # base -> 冷却截止时间戳
        self._cooldown = {}
        # 用户手动指定的源（"" = 自动选择最快）
        self._preferred = ""
        # 写盘节流：record_success 在分页拉取时会被频繁调用
        self._last_save = 0.0
        self._save_interval = 1.5
        self._load()

    # ---------------- 持久化 ----------------
    def _load(self):
        if not (self._state_path and self._state_path.exists()):
            return
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                health = data.get("health") or {}
                if isinstance(health, dict):
                    self._health = {k: v for k, v in health.items()
                                    if isinstance(v, dict)}
                self._preferred = str(data.get("preferred") or "")
                fails = data.get("failures") or {}
                if isinstance(fails, dict):
                    self._failures = {k: int(v) for k, v in fails.items()
                                      if isinstance(v, (int, float))}
                cool = data.get("cooldown") or {}
                if isinstance(cool, dict):
                    now = time.time()
                    # 只恢复「还没到期」的冷却，过期条目直接丢掉
                    self._cooldown = {k: float(v) for k, v in cool.items()
                                      if isinstance(v, (int, float)) and float(v) > now}
        except Exception:
            pass

    def save(self):
        if not self._state_path:
            return
        try:
            with self._lock:
                payload = {"health": self._health,
                           "preferred": self._preferred,
                           "failures": self._failures,
                           "cooldown": self._cooldown,
                           "saved_at": time.time()}
                self._last_save = time.time()
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            tmp.replace(self._state_path)
        except Exception:
            pass

    def _persist(self, force=False):
        """状态变化后落盘（带节流）。

        熔断/冷却这类关键状态必须活过进程重启，否则每次 CLI 导出都会
        重新去撞已知的坏源 —— 所以失败时强制立即写入。
        """
        now = time.time()
        with self._lock:
            if not force and (now - self._last_save) < self._save_interval:
                return
        self.save()

    # ---------------- 偏好与熔断 ----------------
    def set_preferred(self, base):
        with self._lock:
            self._preferred = str(base or "").strip()

    def preferred(self):
        with self._lock:
            return self._preferred

    def _cooldown_seconds(self, base):
        n = self._failures.get(base, 0)
        if n < SOURCE_FAIL_THRESHOLD:
            return 0.0
        over = n - SOURCE_FAIL_THRESHOLD
        return min(SOURCE_COOLDOWN_BASE * (2 ** over), SOURCE_COOLDOWN_MAX)

    def is_cooling(self, base):
        with self._lock:
            return self._cooldown.get(base, 0.0) > time.time()

    def cooldown_remaining(self, base):
        with self._lock:
            return max(0.0, self._cooldown.get(base, 0.0) - time.time())

    def record_success(self, base, ms=None):
        with self._lock:
            self._failures[base] = 0
            self._cooldown.pop(base, None)
            h = self._health.setdefault(base, {})
            h.update(ok=True, error="", checked_at=time.time())
            if ms is not None:
                h["ms"] = int(ms)
        self._persist()

    def record_failure(self, base, error=""):
        with self._lock:
            n = self._failures.get(base, 0) + 1
            self._failures[base] = n
            if n >= SOURCE_FAIL_THRESHOLD:
                self._cooldown[base] = time.time() + self._cooldown_seconds(base)
            h = self._health.setdefault(base, {})
            h.update(ok=False, error=str(error)[:160], checked_at=time.time())
        self._persist(force=True)

    # ---------------- 排序 ----------------
    def candidates(self, bases=None):
        """按「最可能成功」的顺序返回候选源。

        顺序：用户指定的源 > 支持鉴权且健康的源（按延迟）> 其余健康源 >
        未探测过的源 > 冷却中的源（放最后兜底）。
        """
        pool = list(bases or API_BASES)
        with self._lock:
            pref = self._preferred
            health = {b: dict(self._health.get(b) or {}) for b in pool}
            cooling = {b: self._cooldown.get(b, 0.0) > time.time() for b in pool}

        def sort_key(base):
            h = health.get(base) or {}
            known = "ok" in h
            ok = bool(h.get("ok"))
            authed = h.get("auth")
            ms = h.get("ms") or 9_999_999
            # 分组权重：越小越优先
            if base == pref:
                group = 0
            elif ok and authed is not False:
                group = 1
            elif ok:
                group = 2
            elif not known:
                group = 3
            else:
                group = 4
            if cooling.get(base):
                group = 5
            return (group, ms, pool.index(base))

        return sorted(pool, key=sort_key)

    # ---------------- 探测 ----------------
    def probe_one(self, base, token=None, timeout=PROBE_TIMEOUT):
        """探测单个源：能否取到公开数据？是否支持 /v0/me 鉴权？"""
        from . import api  # 延迟导入避免循环依赖

        t0 = time.time()
        rec = {"base": base, "name": source_meta(base)["name"],
               "kind": source_meta(base)["kind"],
               "checked_at": time.time(), "ms": None, "ok": False,
               "status": None, "auth": None, "error": "", "latency_ms": None}

        # 1) 公开端点：证明这个源确实在提供 Bangumi 数据
        try:
            status, data = api.http_get(
                f"{base}/v0/subjects/{PROBE_SUBJECT_ID}",
                retries=1, timeout=timeout)
            rec["status"] = status
            if status == 200 and isinstance(data, dict) and data.get("id"):
                rec["ok"] = True
                rec["ms"] = int((time.time() - t0) * 1000)
            else:
                rec["error"] = f"HTTP {status}"
        except urllib.error.HTTPError as e:
            rec["status"] = e.code
            rec["error"] = f"HTTP {e.code}"
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:120]

        if not rec["ok"]:
            rec["latency_ms"] = int((time.time() - t0) * 1000)
            with self._lock:
                self._health[base] = {k: rec[k] for k in
                                      ("ok", "ms", "status", "auth", "error",
                                       "checked_at")}
            return rec

        # 2) 鉴权能力：只探测，不计入熔断（401 可能是 token 问题而非源问题）
        if token:
            try:
                hdrs = dict(api.HEADERS)
                hdrs["Authorization"] = f"Bearer {token}"
                req = urllib.request.Request(f"{base}/v0/me", headers=hdrs)
                with api._open(req, timeout) as resp:  # noqa: SLF001
                    rec["auth"] = (resp.status == 200)
            except urllib.error.HTTPError as e:
                rec["auth"] = e.code not in (401, 403)
            except Exception:
                rec["auth"] = None

        rec["latency_ms"] = int((time.time() - t0) * 1000)
        with self._lock:
            self._health[base] = {k: rec[k] for k in
                                  ("ok", "ms", "status", "auth", "error",
                                   "checked_at")}
        return rec

    def probe(self, bases=None, token=None, timeout=PROBE_TIMEOUT, workers=8,
              budget=PROBE_BUDGET, min_budget=PROBE_MIN_BUDGET):
        """并发探测所有源，返回按推荐顺序排列的结果列表。

        为了不让启动卡在坏源上，这里用**守护线程 + 早退**：
        一旦拿到了「可用且支持鉴权」的源，最多再等 min_budget 秒就返回；
        仍在探测的源会在后台继续跑完并更新健康状态（守护线程不阻塞进程退出）。
        因此单次探测总耗时通常 ≈ 最快可用源的延迟。
        """
        pool = list(bases or API_BASES)
        if self._log:
            self._log(f"并发探测 {len(pool)} 个数据源...")
        t0 = time.time()
        results = {}
        rlock = threading.Lock()

        def work(base):
            try:
                rec = self.probe_one(base, token, timeout)
            except Exception as e:          # probe_one 自身兜底
                rec = {"base": base, "name": source_meta(base)["name"],
                       "ok": False, "ms": None, "auth": None,
                       "error": f"{type(e).__name__}: {e}"[:120]}
            with rlock:
                results[base] = rec

        threads = [threading.Thread(target=work, args=(b,), daemon=True,
                                    name=f"probe-{i}")
                   for i, b in enumerate(pool)]
        for t in threads:
            t.start()

        deadline = t0 + budget
        while True:
            with rlock:
                n = len(results)
                snapshot = list(results.values())
            if n >= len(pool):
                break
            good = any(r.get("ok") and r.get("auth") is not False
                       for r in snapshot)
            now = time.time()
            if good and now - t0 >= min_budget:
                break
            if now >= deadline:
                break
            time.sleep(0.05)

        elapsed = time.time() - t0
        with rlock:
            finished = dict(results)
        pending = [b for b in pool if b not in finished]
        for b in pending:
            finished[b] = {"base": b, "name": source_meta(b)["name"],
                           "ok": None, "ms": None, "auth": None,
                           "pending": True,
                           "error": "探测中（后台继续）"}

        if self._log:
            good = [r for r in finished.values() if r.get("ok")]
            self._log(f"探测完成，耗时 {elapsed:.1f}s，已确认可用 {len(good)} 个源"
                      + (f"，{len(pending)} 个仍在后台探测" if pending else ""))
            for base in self.candidates(pool):
                r = finished.get(base) or {}
                if r.get("ok"):
                    auth = {True: "支持鉴权", False: "不支持鉴权",
                            None: "未测鉴权"}.get(r.get("auth"), "?")
                    self._log(f"  ✓ {base}  {r.get('ms')}ms  {auth}")
                elif r.get("pending"):
                    self._log(f"  … {base}  探测中")
                else:
                    self._log(f"  ✗ {base}  {r.get('error') or '不可用'}")
        self.save()
        ordered = self.candidates(pool)
        return [finished[b] for b in ordered if b in finished]

    # ---------------- 查询 ----------------
    def health_of(self, base):
        with self._lock:
            return dict(self._health.get(base) or {})

    def is_known(self, base):
        """是否已探测过该源。"""
        with self._lock:
            return (self._health.get(base) or {}).get("ok") is not None

    def snapshot(self, bases=None):
        """给 UI 用的完整状态快照。"""
        pool = list(bases or API_BASES)
        with self._lock:
            health = {b: dict(self._health.get(b) or {}) for b in pool}
            pref = self._preferred
            cooldown = {b: max(0.0, self._cooldown.get(b, 0.0) - time.time())
                        for b in pool}
        out = []
        for base in self.candidates(pool):
            meta = source_meta(base)
            h = health.get(base) or {}
            out.append({
                "base": base,
                "name": meta["name"],
                "kind": meta["kind"],
                "note": meta["note"],
                "declared_auth": meta["auth"],
                "ok": bool(h.get("ok")) if "ok" in h else None,
                "ms": h.get("ms"),
                "status": h.get("status"),
                "auth": h.get("auth"),
                "error": h.get("error", ""),
                "checked_at": h.get("checked_at"),
                "cooling_seconds": round(cooldown.get(base, 0.0), 1),
                "preferred": base == pref,
                "recommended": False,
            })
        for rec in out:
            if rec["ok"]:
                rec["recommended"] = True
                break
        return out

    def best(self, bases=None):
        """当前最优源（用于日志与 UI 提示）。"""
        for base in self.candidates(bases):
            with self._lock:
                h = self._health.get(base) or {}
            if h.get("ok"):
                return base
        cands = self.candidates(bases)
        return cands[0] if cands else (bases or API_BASES)[0]


# 进程级默认实例（Web 端与 CLI 共用）
_default = None
_default_lock = threading.Lock()


def get_manager(state_path=None, log=None):
    global _default
    with _default_lock:
        if _default is None:
            _default = SourceManager(state_path=state_path, log=log)
        elif log is not None and _default._log is None:   # noqa: SLF001
            _default._log = log                            # noqa: SLF001
        return _default
