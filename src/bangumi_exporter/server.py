# -*- coding: utf-8 -*-
"""Web 服务：HTTP API + 任务状态管理 + SPA 前端托管。

相比旧版的改进：
  - 结构化进度（阶段/百分比/计数），不再是无限滚动条
  - 支持取消运行中的任务
  - Token 测试连接端点
  - 浏览器内直接下载导出文件
  - 配置持久化（类型/格式/状态过滤/代理/输出/并发）
  - 评分缓存管理
"""

import json
import mimetypes
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import api as api_mod
from .cache import DataCache, RatingCache
from .config import BASE_DIR, DEFAULT_OUTPUT, load_config, save_config, resolve_token
from .constants import APP_VERSION, COLLECTION_TYPE_NAME, FORMATS, SUBJECT_TYPES
from .engine import ExportOptions, Progress, run_export
from .sources import get_manager
from .ui import render_page

# ==================== 全局任务状态 ====================
LOGS = []
LOG_LOCK = threading.Lock()
JOB_LOCK = threading.Lock()
CANCEL_EVENT = threading.Event()

JOB = {
    "running": False, "done": False, "ok": False, "cancelled": False,
    "error": "", "files": [], "row_count": 0, "elapsed": 0.0,
    "user": None, "mirror": "", "skipped": False, "diff": {},
    "selfcheck": {}, "sources": [],
}
PROGRESS = Progress()
RESULT = None          # 最近一次成功导出的 Result
CACHE_PATH = BASE_DIR / "输出" / ".rating_cache.json"
DATA_CACHE_PATH = BASE_DIR / "输出" / ".data_cache.json"
SOURCE_STATE_PATH = BASE_DIR / "输出" / ".sources.json"


def _manager():
    """取全局数据源管理器（首次调用时绑定状态文件与日志）。"""
    return get_manager(state_path=SOURCE_STATE_PATH, log=log)


def _sources_payload(probe=False):
    """数据源健康快照；probe=True 时先并发重新探测。"""
    cfg = load_config()
    try:
        api_mod.set_token(resolve_token(None, cfg))
    except Exception:
        pass
    proxy = cfg.get("proxy", "")
    if proxy:
        api_mod.set_proxy(proxy, log=None)
    mgr = _manager()
    if cfg.get("source"):
        mgr.set_preferred(cfg["source"])
    if probe:
        mgr.probe(token=api_mod.HEADERS.get("Authorization", "").replace(
            "Bearer ", "") or None)
    snap = mgr.snapshot()
    return {
        "sources": snap,
        "best": mgr.best(),
        "preferred": cfg.get("source", ""),
        "elapsed_hint": "探测为并发执行，通常 1-10 秒",
    }


def log(msg):
    line = str(msg)
    with LOG_LOCK:
        LOGS.append(line)
        if len(LOGS) > 3000:
            del LOGS[:1000]


def _files_meta(paths):
    out = []
    for p in paths:
        try:
            pp = Path(p)
            out.append({"name": pp.name, "path": str(pp),
                        "size": pp.stat().st_size if pp.exists() else None})
        except Exception:
            out.append({"name": str(p), "path": str(p), "size": None})
    return out


def _int_list(value, allowed=None, label=""):
    """把请求体里的值安全地转成 int 列表。

    非法输入返回 (None, 错误信息)，而不是抛出异常让连接被重置。
    """
    if value is None:
        return [], ""
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        value = [value]
    out = []
    for c in value:
        try:
            n = int(c)
        except (TypeError, ValueError):
            return None, f"{label}包含无效值：{c!r}"
        if allowed is None or n in allowed:
            out.append(n)
    return out, ""


def _clamp_workers(value, default=6):
    try:
        return max(1, min(16, int(value)))
    except (TypeError, ValueError):
        return default


# ==================== 导出任务 ====================
def start_export(body):
    """在后台线程启动导出任务。"""
    with JOB_LOCK:
        if JOB["running"]:
            return {"error": "已有任务正在运行"}
        JOB.update(running=True, done=False, ok=False, cancelled=False,
                   error="", files=[], row_count=0, elapsed=0.0)
    CANCEL_EVENT.clear()

    def fail(msg):
        with JOB_LOCK:
            JOB.update(running=False, done=True, ok=False, error=msg)
        return {"error": msg}

    token = str(body.get("token") or "").strip()
    if not token:
        token = resolve_token(None)
    if not token:
        return fail("请填写 Token")

    cfg = load_config()
    valid_codes = {v["code"] for v in SUBJECT_TYPES.values()}

    subject_types, err = _int_list(
        body.get("subject_types") if body.get("subject_types") is not None
        else cfg.get("subject_types") or [2],
        allowed=valid_codes, label="条目类型")
    if err:
        return fail(err)

    collection_types, err = _int_list(
        body.get("collection_types") if body.get("collection_types") is not None
        else cfg.get("collection_types") or [],
        allowed=set(COLLECTION_TYPE_NAME), label="收藏状态")
    if err:
        return fail(err)

    raw_formats = body.get("formats") or cfg.get("formats") or ["csv"]
    if isinstance(raw_formats, (str, bytes)) or not hasattr(raw_formats, "__iter__"):
        raw_formats = [raw_formats]
    formats = [f for f in raw_formats if f in FORMATS]

    output = str(body.get("output") or cfg.get("output") or DEFAULT_OUTPUT).strip()
    proxy = str(body.get("proxy") if body.get("proxy") is not None
                else cfg.get("proxy", "")).strip()
    api_base = str(body.get("api_base") if body.get("api_base") is not None
                   else cfg.get("api_base", "")).strip()
    workers = _clamp_workers(body.get("workers") or cfg.get("workers") or 6)

    source = str(body.get("source") if body.get("source") is not None
                 else cfg.get("source", "")).strip()
    username = str(body.get("username") if body.get("username") is not None
                   else cfg.get("username", "")).strip()
    since = str(body.get("since") or "").strip()
    incremental = bool(body.get("incremental"))
    offline = bool(body.get("offline"))
    probe_sources = bool(body.get("probe_sources"))
    enrich_details = body.get("enrich_details")
    if enrich_details is None:
        enrich_details = cfg.get("enrich_details", True)
    enrich_details = bool(enrich_details)
    # ---- v3.2 高级分析开关（未显式给出时读配置，再退回默认值）----
    def _flag(key, default=False):
        v = body.get(key)
        if v is None:
            v = cfg.get(key, default)
        return bool(v)

    profile = _flag("profile", True)
    recommend = _flag("recommend", False)
    report = _flag("report", False)
    archive = _flag("archive", False)
    supplement = _flag("supplement", False)
    try:
        recommend_limit = int(body.get("recommend_limit")
                              or cfg.get("recommend_limit") or 20)
    except (TypeError, ValueError):
        recommend_limit = 20
    recommend_limit = max(1, min(100, recommend_limit))
    try:
        supplement_limit = int(body.get("supplement_limit")
                               or cfg.get("supplement_limit") or 0)
    except (TypeError, ValueError):
        supplement_limit = 0
    supplement_limit = max(0, min(1000, supplement_limit))

    options = ExportOptions(
        token=token,
        subject_types=tuple(subject_types),
        formats=tuple(formats),
        collection_types=tuple(collection_types),
        output=output,
        proxy=proxy,
        api_base=api_base,
        workers=workers,
        source=source,
        username=username,
        since=since,
        incremental=incremental,
        offline=offline,
        probe_sources=probe_sources,
        enrich_details=enrich_details,
        profile=profile,
        recommend=recommend,
        recommend_limit=recommend_limit,
        report=report,
        archive=archive,
        supplement=supplement,
        supplement_limit=supplement_limit,
    )
    if not options.subject_types:
        return fail("没有有效的条目类型")
    if not options.formats:
        return fail("没有有效的导出格式")

    def worker():
        global RESULT
        try:
            res = run_export(options, log=log, progress=PROGRESS,
                             cache_dir=str(CACHE_PATH.parent),
                             cancel_event=CANCEL_EVENT)
            with JOB_LOCK:
                JOB.update(running=False, done=True, ok=res.ok,
                           cancelled=CANCEL_EVENT.is_set(),
                           error=res.error, files=_files_meta(res.files),
                           row_count=len(res.rows), elapsed=res.elapsed,
                           user=res.user, mirror=res.mirror,
                           skipped=res.skipped, diff=res.diff,
                           selfcheck=res.selfcheck,
                           sources=res.source_health,
                           profile=res.profile or {},
                           recommend=res.recommend or [],
                           vs_global=res.vs_global or {},
                           compare=res.compare or {},
                           diagnosis=res.diagnosis or {},
                           supplement_count=len(res.supplement or {}),
                           detail_files=res.detail_files or [])
            if res.ok:
                RESULT = res
        except Exception as e:
            log(f"错误: {e}")
            with JOB_LOCK:
                JOB.update(running=False, done=True, ok=False, error=str(e))

    threading.Thread(target=worker, daemon=True).start()
    return {"ok": True}


# ==================== HTTP Handler ====================
class Handler(BaseHTTPRequestHandler):
    server_version = f"BangumiExporter/{APP_VERSION}"

    # ---------- 基础响应 ----------
    def _send(self, code, ctype, data, extra_headers=None, as_bytes=False):
        body = data if as_bytes else (data.encode("utf-8") if isinstance(data, str) else data)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False, default=str))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    # ---------- GET ----------
    def do_GET(self):
        u = urlparse(self.path)
        path, qs = u.path, parse_qs(u.query)

        if path == "/":
            return self._send(200, "text/html; charset=utf-8", render_page())

        if path == "/api/settings":
            cfg = load_config()
            cache = RatingCache(CACHE_PATH)
            data_cache = DataCache(DATA_CACHE_PATH)
            return self._json({
                "token": cfg.get("token", ""),
                "proxy": cfg.get("proxy", ""),
                "output": cfg.get("output") or DEFAULT_OUTPUT,
                "api_base": cfg.get("api_base", ""),
                "workers": cfg.get("workers", 6),
                "subject_types": cfg.get("subject_types") or [2],
                "formats": cfg.get("formats") or ["csv"],
                "collection_types": cfg.get("collection_types") or [],
                "source": cfg.get("source", ""),
                "username": cfg.get("username", ""),
                "enrich_details": cfg.get("enrich_details", True),
                "cache_count": cache.count(),
                "data_cache_count": data_cache.count(),
                "data_cache_at": data_cache.loaded_at(),
                "data_cache_meta": data_cache.meta(),
                "output_dir": str(Path(cfg.get("output") or DEFAULT_OUTPUT).parent),
                "version": APP_VERSION,
            })

        if path == "/api/sources":
            force = qs.get("probe", ["0"])[0] in ("1", "true", "yes")
            return self._json(_sources_payload(probe=force))

        if path == "/api/logs":
            try:
                after = int(qs.get("after", ["0"])[0])
            except ValueError:
                after = 0
            with LOG_LOCK:
                logs = LOGS[after:]
                nxt = len(LOGS)
            return self._json({"logs": logs, "next": nxt})

        if path == "/api/status":
            with JOB_LOCK:
                snap = dict(JOB)
            snap["progress"] = PROGRESS.snapshot()
            return self._json(snap)

        if path == "/api/snapshots":
            from .history import list_snapshots, diff_latest, render_diff_markdown
            from .history import ARCHIVE_DIRNAME
            d = CACHE_PATH.parent / ARCHIVE_DIRNAME
            try:
                snaps = list_snapshots(d)
            except Exception as e:
                return self._json({"error": str(e), "snapshots": []})
            return self._json({"snapshots": snaps,
                               "count": len(snaps),
                               "diff": diff_latest(d) or {},
                               "dir": str(d)})

        if path == "/api/compare":
            from .history import compare_snapshots, render_diff_markdown
            from .history import ARCHIVE_DIRNAME
            a = (qs.get("a") or [""])[0]
            b = (qs.get("b") or [""])[0]
            if not a or not b:
                return self._json({"error": "缺少 a / b 参数"}, 400)
            d = CACHE_PATH.parent / ARCHIVE_DIRNAME
            try:
                diff = compare_snapshots(d, a, b)
            except Exception as e:
                return self._json({"error": f"对比失败: {e}"}, 400)
            return self._json({"diff": diff,
                               "markdown": render_diff_markdown(diff)})

        if path == "/api/result":
            if RESULT is None:
                return self._json({"error": "no result"})
            return self._json(RESULT.to_dict(with_rows=True))

        if path == "/api/download":
            try:
                i = int(qs.get("i", ["-1"])[0])
            except ValueError:
                i = -1
            with JOB_LOCK:
                files = list(JOB.get("files") or [])
            if 0 <= i < len(files):
                fp = Path(files[i]["path"])
                if fp.exists():
                    ctype = mimetypes.guess_type(fp.name)[0] or "application/octet-stream"
                    data = fp.read_bytes()
                    from urllib.parse import quote
                    disp = f"attachment; filename*=UTF-8''{quote(fp.name)}"
                    return self._send(200, ctype, data,
                                      {"Content-Disposition": disp}, as_bytes=True)
            return self._json({"error": "file not found"}, 404)

        return self._json({"error": "not found"}, 404)

    # ---------- POST ----------
    def do_POST(self):
        path = urlparse(self.path).path
        body = self._body()

        if path == "/api/export":
            return self._json(start_export(body))

        if path == "/api/cancel":
            CANCEL_EVENT.set()
            log("已请求取消任务...")
            return self._json({"ok": True})

        if path == "/api/test":
            token = str(body.get("token") or "").strip() or resolve_token(None)
            if not token:
                return self._json({"ok": False, "error": "Token 为空"})
            proxy = str(body.get("proxy") or "").strip()

            def tester():
                # 完整快照全局 HTTP 状态，测试结束后无条件还原，
                # 避免把测试用的 Token / 代理泄漏到后续真实导出中。
                old_auth = api_mod.HEADERS.get("Authorization")
                old_proxy = api_mod._proxy_url
                try:
                    api_mod.set_token(token)
                    if proxy:
                        api_mod.set_proxy(proxy)
                    me, base = api_mod.get_me(log=log)
                    uid = me.get("id") or me.get("username")
                    nickname = me.get("nickname") or str(uid)
                    user = {"id": uid, "nickname": nickname,
                            "avatar": (me.get("avatar") or {}).get("medium", ""),
                            "username": me.get("username", "")}
                    with JOB_LOCK:
                        JOB.update(user=user, mirror=base)
                    RESULT_USER[0] = user
                except Exception as e:
                    RESULT_USER[1] = str(e)
                finally:
                    if old_auth:
                        api_mod.HEADERS["Authorization"] = old_auth
                    else:
                        api_mod.HEADERS.pop("Authorization", None)
                    api_mod.set_proxy(old_proxy)

            RESULT_USER = [None, ""]
            t = threading.Thread(target=tester, daemon=True)
            t.start()
            t.join(timeout=40)
            if t.is_alive():
                return self._json({"ok": False, "error": "测试超时（40s）"})
            if RESULT_USER[0]:
                return self._json({"ok": True, "user": RESULT_USER[0],
                                   "nickname": RESULT_USER[0]["nickname"]})
            return self._json({"ok": False, "error": RESULT_USER[1] or "连接失败"})

        if path == "/api/config":
            cfg = load_config()
            for k in ("token", "proxy", "output", "api_base", "workers",
                      "subject_types", "formats", "collection_types",
                      "source", "username", "enrich_details"):
                if k in body:
                    v = body[k]
                    if isinstance(v, str):
                        v = v.strip()
                    cfg[k] = v
            save_config(cfg)
            if "source" in body:
                _manager().set_preferred(str(body.get("source") or ""))
                _manager().save()
            log("设置已保存到 config.json")
            return self._json({"ok": True})

        if path == "/api/sources/probe":
            log("正在并发探测所有数据源...")
            return self._json(_sources_payload(probe=True))

        if path == "/api/cache/clear":
            what = str(body.get("what") or "rating")
            n = 0
            if what in ("rating", "all"):
                cache = RatingCache(CACHE_PATH)
                n = cache.count()
                cache.clear()
            m = 0
            if what in ("data", "all"):
                dc = DataCache(DATA_CACHE_PATH)
                m = dc.count()
                dc.clear()
            log(f"已清空缓存：评分 {n} 条，完整数据 {m} 条")
            return self._json({"ok": True, "cleared": n, "cleared_data": m})

        if path == "/api/open-dir":
            cfg = load_config()
            out = Path(cfg.get("output") or DEFAULT_OUTPUT).parent
            try:
                out.mkdir(parents=True, exist_ok=True)
                if sys.platform == "win32":
                    os.startfile(str(out))  # noqa: S606
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(out)])
                else:
                    subprocess.Popen(["xdg-open", str(out)])
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})

        if path == "/api/quit":
            self._json({"ok": True})
            log("正在退出...")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        return self._json({"error": "not found"}, 404)

    def log_message(self, *args):
        pass  # 静默 HTTP 访问日志


# ==================== 启动入口 ====================
def pick_port(start=8921, end=8941):
    for port in range(start, end):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            return srv, port
        except OSError:
            continue
    return None, None


def serve(open_browser=True):
    srv, port = pick_port()
    if srv is None:
        print("错误：8921-8940 端口均被占用，无法启动服务")
        return 1
    url = f"http://127.0.0.1:{port}"
    log(f"Bangumi 收藏导出工具 v{APP_VERSION} 启动成功")
    log(f"访问地址: {url}")
    # 使用 ASCII 安全字符，避免 Windows GBK 控制台编码错误
    print(f"[Bangumi 收藏导出工具 v{APP_VERSION}]")
    print(f"  访问地址：{url}")
    print("  关闭此窗口即退出程序")
    if open_browser and not os.environ.get("BANGUMI_NO_BROWSER"):
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
