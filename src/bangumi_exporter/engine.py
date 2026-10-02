# -*- coding: utf-8 -*-
"""导出引擎：编排「认证 → 拉取 → 补全 → 排序 → 展平 → 导出 → 统计」全流程。

相比旧版的关键改进：
  - 结构化进度回调（阶段 / 计数 / 百分比），供 Web UI 绘制真实进度条
  - 可按收藏状态过滤（只导出看过 / 在看 / 想看...）
  - 评分缓存持久化，二次导出更快
  - 返回结构化 Result（文件列表 + 行数据 + 图表数据），前端可直接渲染
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import api
from .cache import DataCache, RatingCache
from .config import load_config, resolve_token, DEFAULT_OUTPUT
from .constants import (
    API_BASES,
    COLLECTION_TYPE_NAME,
    COLLECTION_TYPE_ORDER,
    EXPORT_EXT,
    SUBJECT_CODE_TO_NAME,
    SUBJECT_TYPES,
    SUBJECT_TYPE_ORDER,
    FORMATS,
    TAG_LIMIT,
)
from .exporters import EXPORTERS
from .sources import get_manager
from .stats import build_chart_data, render_stats_markdown, render_type_stats_markdown
from .diagnose import diagnose_columns, render_diagnosis_markdown
from .compare import build_compare, render_compare_markdown
from .profile import build_profile, recommend, render_profile_markdown
from .history import archive_snapshot, diff_latest, ARCHIVE_DIRNAME
from .report import build_html_report
from . import details


@dataclass
class Result:
    """一次导出的结构化结果。"""
    ok: bool = False
    error: str = ""
    files: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    charts: dict = field(default_factory=dict)
    user: dict = field(default_factory=dict)
    elapsed: float = 0.0
    mirror: str = ""
    skipped: bool = False                    # 增量导出且无变化时为 True
    selfcheck: dict = field(default_factory=dict)   # 导出自检清单
    diff: dict = field(default_factory=dict)        # 与缓存的差异摘要
    source_health: list = field(default_factory=list)  # 数据源健康快照
    diagnosis: dict = field(default_factory=dict)      # 空列体检结果
    profile: dict = field(default_factory=dict)        # 用户画像
    recommend: list = field(default_factory=list)      # 智能推荐
    compare: dict = field(default_factory=dict)        # 快照对比（收藏变化）
    vs_global: dict = field(default_factory=dict)      # 全站对比（我的评分 vs 大众）
    report_html: str = ""                              # 可视化报告路径
    supplement: dict = field(default_factory=dict)     # 数据补全（详情缓存）
    detail_files: list = field(default_factory=list)   # 详情导出文件

    def to_dict(self, with_rows=True):
        d = {
            "ok": self.ok,
            "error": self.error,
            "files": self.files,
            "charts": self.charts,
            "user": self.user,
            "elapsed": round(self.elapsed, 2),
            "mirror": self.mirror,
            "row_count": len(self.rows),
            "skipped": self.skipped,
            "selfcheck": self.selfcheck,
            "diff": self.diff,
            "source_health": self.source_health,
            "diagnosis": self.diagnosis,
            "profile": self.profile,
            "recommend": self.recommend,
            "compare": self.compare,
            "vs_global": self.vs_global,
            "report_html": self.report_html,
            "supplement_count": len(self.supplement),
            "detail_files": self.detail_files,
        }
        if with_rows:
            d["rows"] = self.rows
        return d


@dataclass
class ExportOptions:
    """导出选项（由 CLI 参数或 Web 请求构建）。"""
    token: str = ""
    subject_types: tuple = (2,)          # 条目类型代码
    formats: tuple = ("csv",)            # 导出格式
    collection_types: tuple = ()         # 收藏状态过滤，空 = 全部
    output: str = ""                     # 输出文件基础名（不含扩展名）
    proxy: str = ""
    api_base: str = ""
    workers: int = 6
    no_stats: bool = False
    save_token: bool = False
    use_cache: bool = True
    source: str = ""                     # 指定数据源（"" = 自动选最快）
    username: str = ""                   # 直接指定用户名，跳过 /v0/me
    since: str = ""                      # 只导出该时间之后有更新的条目
    incremental: bool = False            # 只导出与上次缓存相比有变化的条目
    offline: bool = False                # 离线模式：只用缓存数据
    probe_sources: bool = False          # 强制重新探测数据源
    enrich_details: bool = True          # 补取条目详情（平台等，collections 不返回）
    # ---- v3.2 高级分析 ----
    profile: bool = True                 # 生成用户画像（本地计算，免费）
    recommend: bool = False              # 生成智能推荐（需要联网检索）
    recommend_limit: int = 20
    report: bool = False                 # 额外生成单文件可视化 HTML 报告
    archive: bool = False                # 归档本次快照（供历史对比）
    supplement: bool = False             # 补全简介/制作公司/staff/声优/分集/播出星期/卷数
    supplement_limit: int = 0            # 只补前 N 个条目（0 = 全部，调试用）

    @property
    def output_dir(self):
        return str(Path(self.output).parent) if self.output else DEFAULT_OUTPUT


class Progress:
    """进度报告器：把结构化进度推送给回调（Web UI 轮询该对象）。"""

    def __init__(self, callback=None):
        self._cb = callback
        self.stage = "idle"          # idle/auth/fetch/enrich/sort/export/stats/done/error
        self.stage_label = ""
        self.total_types = 0
        self.done_types = 0
        self.current_type = ""
        self.items_fetched = 0
        self.percent = 0.0
        self.message = ""

    def update(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        if self._cb:
            try:
                self._cb(self)
            except Exception:
                pass

    def snapshot(self):
        return {
            "stage": self.stage,
            "stage_label": self.stage_label,
            "total_types": self.total_types,
            "done_types": self.done_types,
            "current_type": self.current_type,
            "items_fetched": self.items_fetched,
            "percent": round(self.percent, 1),
            "message": self.message,
        }


def build_cli_namespace(token=None, output=None, subject_type="anime",
                        formats="csv", workers=6, no_stats=False,
                        save_token=False, gui=False, proxy="", api_base=None,
                        collection_types="", source="", username="", since="",
                        incremental=False, offline=False, probe_sources=False,
                        enrich_details=True, profile=True, recommend=False,
                        recommend_limit=20, report=False, archive=False,
                        supplement=False, supplement_limit=0):
    """兼容旧版 CLI 的参数命名空间构建。"""
    import argparse
    return argparse.Namespace(
        token=token, output=output or DEFAULT_OUTPUT,
        subject_type=subject_type, formats=formats, workers=workers,
        no_stats=no_stats, save_token=save_token, gui=gui,
        proxy=proxy, api_base=api_base, collection_types=collection_types,
        source=source, username=username, since=since,
        incremental=incremental, offline=offline,
        probe_sources=probe_sources, enrich_details=enrich_details,
        profile=profile, recommend=recommend, recommend_limit=recommend_limit,
        report=report, archive=archive,
        supplement=supplement, supplement_limit=supplement_limit,
    )


def parse_subject_types(spec):
    """解析条目类型参数：all / anime,game / 2,4 ..."""
    spec = str(spec or "").strip()
    if not spec or spec.lower() == "all":
        return [v["code"] for v in SUBJECT_TYPES.values()]
    codes = []
    for part in spec.split(","):
        part = part.strip().lower()
        if part in SUBJECT_TYPES:
            codes.append(SUBJECT_TYPES[part]["code"])
        elif part.isdigit() and int(part) in SUBJECT_CODE_TO_NAME:
            codes.append(int(part))
    seen, out = set(), []
    for c in codes:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def parse_formats(spec):
    """解析导出格式参数：all / csv,excel ..."""
    spec = str(spec or "").strip()
    if not spec or spec.lower() == "all":
        return list(FORMATS)
    alias = {"xlsx": "excel", "md": "markdown", "htm": "html"}
    out = []
    for part in spec.split(","):
        part = alias.get(part.strip().lower(), part.strip().lower())
        if part in FORMATS and part not in out:
            out.append(part)
    return out


def parse_collection_types(spec):
    """解析收藏状态过滤：'' = 全部；'1,2' 或 '看过,在看'。"""
    spec = str(spec or "").strip()
    if not spec or spec.lower() == "all":
        return []
    name_to_code = {v: k for k, v in COLLECTION_TYPE_NAME.items()}
    codes = []
    for part in spec.split(","):
        part = part.strip()
        if part.isdigit():
            codes.append(int(part))
        elif part in name_to_code:
            codes.append(name_to_code[part])
    return codes


# ---------- 排序与展平 ----------
def _bgm_score(x):
    return ((x.get("subject") or {}).get("rating") or {}).get("score") or 0


def _my_rate(x):
    return x.get("rate") or 0


def _subject_type_code(x):
    return (x.get("subject") or {}).get("type") or 0


def sort_items(items):
    items = sorted(items, key=lambda x: x.get("updated_at") or "", reverse=True)
    items = sorted(items, key=lambda x: -_bgm_score(x))
    items = sorted(items, key=lambda x: -_my_rate(x))
    items = sorted(items, key=lambda x: COLLECTION_TYPE_ORDER.get(x.get("type"), 99))
    items = sorted(items, key=lambda x: SUBJECT_TYPE_ORDER.get(_subject_type_code(x), 99))
    return items


def flatten_item(item, idx):
    subject = item.get("subject") or {}
    rating = subject.get("rating") or {}
    sid = subject.get("id") or item.get("subject_id")
    return {
        "序号": idx,
        "条目类型": SUBJECT_CODE_TO_NAME.get(subject.get("type"), ""),
        "收藏类型": COLLECTION_TYPE_NAME.get(item.get("type"), ""),
        "中文名": subject.get("name_cn") or subject.get("name") or "",
        "原名": subject.get("name", ""),
        "我的评分": item.get("rate") or "",
        "BGM评分": rating.get("score") or "",
        "评分人数": rating.get("total") or "",
        "排名": rating.get("rank") or "",
        "看到第几集": item.get("ep_status") or 0,
        "总集数": subject.get("eps") or "",
        "卷数": subject.get("volumes") or "",
        "放送日期": subject.get("date") or "",
        "放送星期": "",
        "平台": subject.get("platform") or "",
        "制作公司": "",
        # 社区标签（来自 subject.tags，含制作公司/年份/题材），
        # 与「我的标签」（collection.tags，你自己的标注）是两回事。
        "条目标签": "|".join(api.tag_names(subject.get("tags"), TAG_LIMIT)),
        "简介": "",
        "我的短评": item.get("comment") or "",
        "我的标签": "|".join(api.tag_names(item.get("tags"))),
        "条目ID": sid,
        "条目链接": f"https://bgm.tv/subject/{sid}",
        "更新时间": item.get("updated_at") or "",
        "封面": (subject.get("images") or {}).get("medium") or "",
    }


def split_cached(value):
    """解析评分缓存条目，兼容旧格式。

    新格式：{"rating": {...}, "platform": "TV"}
    旧格式（v3.0）：直接就是 rating 字典 {...}
    """
    if isinstance(value, dict) and "rating" in value:
        return (value.get("rating") or {}), (value.get("platform") or "")
    if isinstance(value, dict):
        return value, ""
    return {}, ""


def strip_known_ext(base):
    p = Path(base)
    if p.suffix.lower() in {".csv", ".json", ".xlsx", ".md", ".html", ".htm", ".txt"}:
        return str(p.with_suffix(""))
    return base


def options_from_args(args, cfg=None):
    """从 CLI Namespace 构建 ExportOptions。"""
    cfg = cfg if cfg is not None else load_config()
    token = resolve_token(getattr(args, "token", None), cfg)
    return ExportOptions(
        token=token,
        subject_types=tuple(parse_subject_types(getattr(args, "subject_type", "anime"))),
        formats=tuple(parse_formats(getattr(args, "formats", "csv"))),
        collection_types=tuple(parse_collection_types(getattr(args, "collection_types", ""))),
        output=getattr(args, "output", "") or cfg.get("output") or DEFAULT_OUTPUT,
        proxy=getattr(args, "proxy", "") or cfg.get("proxy", "") or "",
        api_base=getattr(args, "api_base", "") or "",
        workers=getattr(args, "workers", 6),
        no_stats=getattr(args, "no_stats", False),
        save_token=getattr(args, "save_token", False),
        source=getattr(args, "source", "") or "",
        username=getattr(args, "username", "") or "",
        since=getattr(args, "since", "") or "",
        incremental=bool(getattr(args, "incremental", False)),
        offline=bool(getattr(args, "offline", False)),
        probe_sources=bool(getattr(args, "probe_sources", False)),
        profile=bool(getattr(args, "profile", True)),
        recommend=bool(getattr(args, "recommend", False)),
        recommend_limit=int(getattr(args, "recommend_limit", 20) or 20),
        report=bool(getattr(args, "report", False)),
        archive=bool(getattr(args, "archive", False)),
        supplement=bool(getattr(args, "supplement", False)),
        supplement_limit=int(getattr(args, "supplement_limit", 0) or 0),
        enrich_details=bool(getattr(args, "enrich_details", True)),
    )


def run_export(options, log=print, progress=None, cache_dir=None, cancel_event=None):
    """执行完整导出流程，返回 Result。

    options: ExportOptions 或旧版 argparse.Namespace（自动转换）
    log:     日志回调（默认 print）
    progress: Progress 实例（可选，Web UI 用）
    cancel_event: threading.Event，置位后尽快中止（可选）
    """
    def cancelled():
        return cancel_event is not None and cancel_event.is_set()
    t0 = time.time()
    if not isinstance(options, ExportOptions):
        options = options_from_args(options)

    prog = progress or Progress()
    result = Result()

    def stage(name, label, percent, message=""):
        prog.update(stage=name, stage_label=label, percent=percent, message=message)
        if message:
            log(message)

    # ---- Token ----
    if not options.token:
        result.error = "未找到 Access Token（--token / 环境变量 BANGUMI_TOKEN / config.json）"
        stage("error", "失败", 0, "错误：" + result.error)
        return result

    api.set_token(options.token)
    if options.proxy:
        api.set_proxy(options.proxy, log=log)

    # ---- 数据源：并发探测 + 熔断 + 自动选最快 ----
    state_dir = Path(cache_dir) if cache_dir else Path(options.output_dir)
    manager = get_manager(state_path=state_dir / ".sources.json", log=log)
    explicit = [options.api_base] if options.api_base else []
    if options.source:
        explicit.insert(0, options.source)
    pool = explicit + [b for b in API_BASES if b not in explicit]
    if options.source:
        manager.set_preferred(options.source)

    known = all(manager.is_known(b) for b in pool)
    if options.offline:
        bases = manager.candidates(pool)
    elif options.probe_sources or not known:
        manager.probe(pool, token=options.token)
        bases = manager.candidates(pool)
    else:
        bases = manager.candidates(pool)
        log("使用已缓存的数据源健康状态（重新探测请加 --probe-sources）")
    log("数据源优先级: " + " > ".join(bases[:3])
        + (f" 等共 {len(bases)} 个" if len(bases) > 3 else ""))

    stage("auth", "验证身份", 5, "开始获取当前用户...")

    # ---- 身份识别（--username 直连 / 离线用缓存 / 否则走 /v0/me）----
    data_cache = DataCache(state_dir / ".data_cache.json")
    cached_meta = data_cache.meta()
    me = None
    auth_base = bases[0] if bases else ""

    if options.username:
        uid = options.username
        me = {"id": uid, "username": uid, "nickname": uid}
        log(f"已用 --username 指定用户：{uid}（跳过 /v0/me 身份识别）")
    elif not options.offline:
        try:
            me, auth_base = api.get_me(bases, log=log, manager=manager)
        except Exception as e:
            # 降级：缓存里有上次的身份信息就继续，别让一次网络抖动废掉整个导出
            if cached_meta.get("uid"):
                uid = cached_meta["uid"]
                me = {"id": uid, "username": cached_meta.get("username", uid),
                      "nickname": cached_meta.get("nickname", str(uid))}
                log(f"⚠ 身份识别失败（{e}），改用缓存中的用户信息继续")
            else:
                result.error = str(e)
                stage("error", "认证失败", 5, f"错误：{e}")
                return result

    if me is None:
        if not cached_meta.get("uid"):
            result.error = ("离线模式下没有可用缓存，"
                            "请先联网成功导出一次以建立数据缓存")
            stage("error", "无法离线导出", 5, "错误：" + result.error)
            return result
        uid = cached_meta["uid"]
        me = {"id": uid, "username": cached_meta.get("username", uid),
              "nickname": cached_meta.get("nickname", str(uid))}
        log("离线模式：使用缓存中的用户信息与数据")

    uid = me.get("id") or me.get("username")
    nickname = me.get("nickname") or str(uid)
    result.user = {"id": uid, "nickname": nickname,
                   "avatar": (me.get("avatar") or {}).get("medium", ""),
                   "username": me.get("username", "")}
    result.mirror = auth_base
    log(f"当前用户: {nickname}  id={uid}")
    if not options.offline:
        log(f"使用数据源: {auth_base}")

    if not options.subject_types:
        result.error = "没有有效的条目类型"
        stage("error", "失败", 5, "错误：" + result.error)
        return result
    if not options.formats:
        result.error = "没有有效的导出格式"
        stage("error", "失败", 5, "错误：" + result.error)
        return result

    # ---- 拉取收藏（离线模式直接读缓存） ----
    items = []
    n_types = len(options.subject_types)
    prog.update(total_types=n_types, done_types=0, stage="fetch",
                stage_label="拉取收藏", percent=10)
    if options.offline:
        cached_rows = list(data_cache.items())
        if options.subject_types:
            wanted = {SUBJECT_CODE_TO_NAME.get(c) for c in options.subject_types}
            cached_rows = [r for r in cached_rows if r.get("条目类型") in wanted]
        if options.collection_types:
            cnames = {COLLECTION_TYPE_NAME.get(c) for c in options.collection_types}
            cached_rows = [r for r in cached_rows if r.get("收藏类型") in cnames]
        log(f"离线模式：从缓存读取 {len(cached_rows)} 条记录")
        rows_from_cache = cached_rows
        items = []
    else:
        rows_from_cache = None
        for ti, scode in enumerate(options.subject_types):
            if cancelled():
                result.error = "已取消"
                stage("error", "已取消", 0, "用户取消了导出")
                return result
            name = SUBJECT_CODE_TO_NAME.get(scode, str(scode))
            prog.update(current_type=name, done_types=ti,
                        percent=10 + 55 * ti / n_types,
                        message=f"正在拉取「{name}」收藏...")
            log(f"\n=== 获取「{name}」收藏 ===")
            got = None
            for base in bases:
                if manager.is_cooling(base):
                    continue
                try:
                    got = api.fetch_collections(uid, base, scode, log=log)
                    if got:
                        manager.record_success(base)
                        auth_base = base
                        break
                except Exception as e:
                    manager.record_failure(base, e)
                    log(f"  {base} 获取失败: {e}")
            if got:
                items.extend(got)
            else:
                log(f"  「{name}」没有获取到数据")
            prog.update(items_fetched=len(items),
                        percent=10 + 55 * (ti + 1) / n_types)
            time.sleep(0.3)

    prog.update(done_types=n_types)

    # ---- 收藏状态过滤 ----
    if options.collection_types and items:
        before = len(items)
        items = [x for x in items if x.get("type") in options.collection_types]
        names = "、".join(COLLECTION_TYPE_NAME.get(c, str(c))
                          for c in options.collection_types)
        log(f"按收藏状态过滤（{names}）：{before} -> {len(items)}")

    if not items and rows_from_cache is None:
        result.error = "未获取到任何数据"
        stage("error", "无数据", 65, "未获取到任何数据")
        return result
    if rows_from_cache is not None and not rows_from_cache:
        result.error = "缓存中没有符合条件的数据"
        stage("error", "无数据", 65, "缓存中没有符合条件的数据")
        return result

    # ---- 补取评分 / 详情（带缓存） ----
    stage("enrich", "补全数据", 68, "检查数据完整性...")
    cache = None
    # 缓存对象始终建立（纯本地读文件，不联网）：
    # 离线模式下虽然不补取数据，但「全站对比」仍需要缓存里的评分直方图。
    if options.use_cache and cache_dir:
        cache = RatingCache(Path(cache_dir) / ".rating_cache.json")
    if options.offline:
        log("离线模式：跳过数据补取")
    else:
        # 1) 先榨干 collections 响应里已经带的数据（零请求）
        n_embedded = api.normalize_embedded(items)
        if n_embedded:
            log(f"从收藏响应直接获得 {n_embedded} 条评分（无需额外请求）")

        want_details = tuple(api.DETAIL_FIELDS) if options.enrich_details else ()
        if cache is not None:
            cached_hit = 0
            still_missing = []
            for item in items:
                subj = item.get("subject") or {}
                sid = subj.get("id") or item.get("subject_id")
                hit = cache.get(sid) if sid else None
                rating, platform = split_cached(hit)
                used = False
                if rating and not (subj.get("rating") or {}).get("total"):
                    subj["rating"] = rating
                    used = True
                if platform and not subj.get("platform"):
                    subj["platform"] = platform
                    used = True
                if used:
                    item["subject"] = subj
                    cached_hit += 1
                if api.needs_detail(item, want_details):
                    still_missing.append(item)
            if cached_hit:
                log(f"缓存命中 {cached_hit} 条数据，跳过网络请求")
            if still_missing:
                api.enrich_details(still_missing, auth_base,
                                   workers=options.workers, log=log,
                                   want=want_details,
                                   cancel_event=cancel_event)
                for item in still_missing:
                    subj = item.get("subject") or {}
                    sid = subj.get("id") or item.get("subject_id")
                    if sid and subj.get("rating"):
                        cache.put(sid, {"rating": subj["rating"],
                                        "platform": subj.get("platform") or ""})
                cache.save()
            else:
                log("所有条目信息已完整，无需补取")
        else:
            api.enrich_details(items, auth_base, workers=options.workers,
                               log=log, want=want_details,
                               cancel_event=cancel_event)

    # ---- 排序 + 展平 ----
    stage("sort", "整理数据", 80, "排序与展平...")
    raw_items = None
    if rows_from_cache is not None:
        rows = sorted(rows_from_cache, key=lambda r: (
            SUBJECT_TYPE_ORDER.get(
                next((v["code"] for v in SUBJECT_TYPES.values()
                      if v["name"] == r.get("条目类型")), 99), 99),
            COLLECTION_TYPE_ORDER.get(
                next((k for k, v in COLLECTION_TYPE_NAME.items()
                      if v == r.get("收藏类型")), 99), 99),
            str(r.get("更新时间") or "")))
        all_rows = rows
        # 离线模式下数据本来就来自缓存，与自身对比必然是「全部未变」。
        # 仍然算出 diff，好让 --incremental 语义保持一致（无变化 -> 跳过）。
        diff = data_cache.diff(all_rows) if data_cache else None
    else:
        items = sort_items(items)
        all_rows = [flatten_item(x, i + 1) for i, x in enumerate(items)]
        raw_items = items          # 保留原始接口数据，供空列诊断取证
        diff = data_cache.diff(all_rows) if data_cache else None
        rows = all_rows

    # ---- 增量 / 时间过滤 ----
    if diff:
        result.diff = {
            "added": len(diff["added"]),
            "changed": len(diff["changed"]),
            "unchanged": diff["unchanged"],
            "removed": len(diff["removed"]),
            "total": diff["total"],
            "added_names": [r.get("中文名", "") for r in diff["added"][:20]],
            "changed_names": [r.get("中文名", "") for r in diff["changed"][:20]],
            "removed_names": [r.get("中文名", "") for r in diff["removed"][:20]],
            "first_run": diff["unchanged"] == 0 and not diff["changed"],
        }
        log(f"与上次缓存对比：新增 {len(diff['added'])}，"
            f"变化 {len(diff['changed'])}，未变 {diff['unchanged']}，"
            f"删除 {len(diff['removed'])}")

    if options.since:
        before = len(rows)
        rows = DataCache.filter_since(rows, options.since)
        log(f"按时间过滤（更新时间 >= {options.since}）：{before} -> {len(rows)}")

    if options.incremental:
        if not diff:
            log("⚠ 增量导出需要先有完整缓存，本次按全量导出")
        else:
            rows = diff["added"] + diff["changed"]
            log(f"增量导出：只输出 新增+变化 共 {len(rows)} 条")

    if not rows:
        result.skipped = True
        result.ok = True
        result.elapsed = time.time() - t0
        result.charts = build_chart_data(all_rows)
        stage("done", "无变化", 100,
              "增量导出完成：与上次相比没有任何变化，未生成文件")
        log("\n增量导出完成：没有任何变化，未生成文件。")
        return result

    # 重新编号，保证「序号」连续
    for i, r in enumerate(rows, 1):
        r["序号"] = i
    log(f"\n共 {len(rows)} 条记录，开始导出...")
    result.rows = rows

    # ---- 数据补全（简介 / 制作公司 / staff / 声优 / 分集 / 播出星期 / 卷数）----
    base_out = strip_known_ext(options.output or DEFAULT_OUTPUT)
    supp = {}
    # 与 .data_cache.json / .rating_cache.json 放在同一个状态目录，
    # 这样换 --output 也能复用已抓取的详情。
    detail_cache = str(state_dir / ".detail_cache.json")
    if options.supplement and not options.offline:
        stage("supplement", "数据补全", 82,
              "正在补全简介 / 制作公司 / 声优 / 分集...")
        try:
            supp = details.supplement(
                rows, auth_base, cache_path=detail_cache, log=log,
                cancel_event=cancel_event, workers=options.workers,
                max_subjects=options.supplement_limit or None)
            filled = details.fill_rows(rows, supp)
            result.supplement = supp
            log(f"  补全完成：{filled} 条（缓存 {len(supp)} 条详情）")
        except Exception as e:
            log(f"  ⚠ 数据补全失败，跳过：{e}")
    elif options.supplement:
        # 离线模式：只读已有缓存，不联网
        try:
            cached = details.DetailCache(detail_cache)
            if cached.count():
                supp = cached.snapshot()
                details.fill_rows(rows, supp)
                result.supplement = supp
                log(f"  离线补全：从缓存读取 {len(supp)} 条详情")
        except Exception as e:
            log(f"  ⚠ 离线补全跳过：{e}")

    # ---- 导出文件 ----
    stage("export", "写入文件", 85, "正在生成导出文件...")
    Path(base_out).parent.mkdir(parents=True, exist_ok=True)
    out_files = []
    n_fmt = len(options.formats)
    for fi, fmt in enumerate(options.formats):
        path = base_out + EXPORT_EXT[fmt]
        try:
            EXPORTERS[fmt](rows, path)
            out_files.append(path)
            log(f"  已导出 {path}（{len(rows)} 条）")
        except Exception as e:
            log(f"  导出 {fmt} 失败: {e}")
        prog.update(percent=85 + 10 * (fi + 1) / n_fmt)

    # ---- 统计报告 ----
    stage("stats", "生成统计", 96, "生成统计报告...")
    charts = build_chart_data(rows)
    result.charts = charts
    # ---- v3.2 全站对比（我的评分 vs 大众分布）----
    stage("compare", "全站对比", 96, "正在汇总全站评分分布...")
    try:
        rating_get = cache.get if cache is not None else None
        result.vs_global = build_compare(rows, rating_get=rating_get)
        log(f"  全站对比：{result.vs_global['with_hist']}/{len(rows)} 条含全站分布，"
            f"收藏平均全站分 {result.vs_global['collection_avg_global']}")
    except Exception as e:
        log(f"  全站对比失败: {e}")

    # 空列诊断：解释每一列为什么为空（含原始接口证据）
    try:
        result.diagnosis = diagnose_columns(rows, raw_items=raw_items)
    except Exception as e:
        log(f"  数据体检失败: {e}")

    # ---- v3.2 用户画像 / 智能推荐 ----
    if options.profile:
        stage("profile", "用户画像", 97, "正在计算用户画像...")
        try:
            result.profile = build_profile(rows)
            log(f"  画像完成：{result.profile['diversity']['distinct_tags']} 个标签，"
                f"归一化熵 {result.profile['diversity']['entropy_norm']}")
        except Exception as e:
            log(f"  画像计算失败: {e}")

    if options.recommend and result.profile:
        stage("recommend", "智能推荐", 98, "正在检索并排序候选条目...")
        try:
            result.recommend = recommend(
                result.profile,
                exclude_ids=[r.get("条目ID") for r in rows],
                base=auth_base or (manager.best(options.subject_types) if manager else None),
                limit=options.recommend_limit,
                log=log, cancel_event=cancel_event)
            log(f"  推荐完成：{len(result.recommend)} 条候选")
        except Exception as e:
            log(f"  推荐失败: {e}")

    # ---- v3.2 历史归档 ----
    if options.archive:
        try:
            snap = archive_snapshot(
                rows, str(Path(base_out).parent / ARCHIVE_DIRNAME), meta={
                    "uid": uid, "nickname": nickname, "source": auth_base})
            log(f"  已归档快照 {snap['id']}（共 {len(rows)} 条，"
                f"现有 {snap['total_snapshots']} 份）")
            # 有了两份以上快照就能自动对比出「这段时间的变化」
            try:
                cmp = diff_latest(str(Path(base_out).parent / ARCHIVE_DIRNAME))
                if cmp:
                    result.compare = cmp
                    log(f"  与上次快照对比：新增 {len(cmp['added'])}，"
                        f"删除 {len(cmp['removed'])}，修改 {len(cmp['changed'])}")
            except Exception:
                pass
        except Exception as e:
            log(f"  归档失败: {e}")

    if not options.no_stats:
        stats_path = base_out + "_stats.md"
        try:
            report_md = render_stats_markdown(rows, uid, nickname)
            report_md += render_diagnosis_markdown(result.diagnosis)
            report_md += render_compare_markdown(result.vs_global)
            report_md += render_profile_markdown(result.profile, result.recommend)
            report_md += render_type_stats_markdown(rows)
            if result.supplement:
                # 统计报告里只放前 10 条摘要，完整详情见「_详情.md / _详情.json」
                report_md += details.render_supplement_markdown(
                    rows, result.supplement, top=10)
                report_md += ("\n> 上面只展示前 10 条。\n"
                              "> 完整详情（全部条目的 staff / 声优 / 分集）"
                              "见同目录的 `_详情.md` 与 `_详情.json`。\n")
            Path(stats_path).write_text(report_md, encoding="utf-8")
            out_files.append(stats_path)
            log(f"  已导出统计报告 {stats_path}")
        except Exception as e:
            log(f"  统计报告生成失败: {e}")

    # ---- 数据补全的完整详情文件 ----
    if result.supplement:
        try:
            md_path = base_out + "_详情.md"
            js_path = base_out + "_详情.json"
            Path(md_path).write_text(
                "# 条目详情\n" + details.render_supplement_markdown(
                    rows, result.supplement, staff_limit=20, cast_limit=20,
                    ep_limit=200, top=10 ** 6),
                encoding="utf-8")
            Path(js_path).write_text(
                json.dumps(details.supplement_json(result.supplement, rows),
                           ensure_ascii=False, indent=2), encoding="utf-8")
            out_files += [md_path, js_path]
            result.detail_files = [md_path, js_path]
            log(f"  已导出详情 {md_path}")
            log(f"  已导出详情 {js_path}")
        except Exception as e:
            log(f"  详情文件生成失败: {e}")

    # ---- v3.2 可视化 HTML 报告 ----
    if options.report:
        stage("report", "可视化报告", 99, "正在生成可视化 HTML 报告...")
        try:
            html_path = base_out + "_报告.html"
            Path(html_path).write_text(
                build_html_report(rows, result.charts, result.profile,
                                  result.recommend, result.diagnosis,
                                  user={**result.user, "nickname": nickname},
                                  compare=result.compare,
                                  vs_global=result.vs_global),
                encoding="utf-8")
            out_files.append(html_path)
            result.report_html = html_path
            log(f"  已导出可视化报告 {html_path}")
        except Exception as e:
            log(f"  可视化报告生成失败: {e}")

    result.files = out_files
    result.ok = bool(out_files)
    result.elapsed = time.time() - t0

    # ---- 导出自检：确认每个文件真的可读、条数正确 ----
    if out_files:
        result.selfcheck = self_check(out_files, expected_rows=len(rows))
        bad = [k for k, v in result.selfcheck.items() if not v.get("ok")]
        if bad:
            log("  ⚠ 自检发现问题：" + "、".join(bad))
        else:
            log(f"  自检通过：{len(result.selfcheck)} 个文件均可正常解析，"
                f"条数一致（{len(rows)}）")

    # ---- 写入完整数据缓存（供下次增量导出 / 离线重导出） ----
    if diff is not None and data_cache is not None and not options.offline:
        data_cache.merge(all_rows)
        data_cache.set_meta(uid=uid, username=result.user.get("username", ""),
                            nickname=nickname, source=auth_base,
                            row_count=len(all_rows))
        data_cache.save()
        log(f"  已更新数据缓存（{len(all_rows)} 条），"
            f"下次可用 --incremental 只导出变化部分")

    if result.ok:
        extra = ""
        if options.incremental and diff:
            extra = (f"（增量：新增 {len(diff['added'])} / "
                     f"变化 {len(diff['changed'])}）")
        stage("done", "完成", 100,
              f"导出完成！共 {len(rows)} 条{extra}，{len(out_files)} 个文件，"
              f"耗时 {result.elapsed:.1f}s")
        log("\n导出完成！生成文件：")
        for f in out_files:
            log(f"  {f}")
    else:
        result.error = "所有格式导出均失败"
        stage("error", "失败", 100, "错误：" + result.error)

    return result


def self_check(files, expected_rows=None):
    """导出自检：逐个文件确认存在、非空、可解析，并核对条数。

    - csv : 行数
    - json: 可解析 + 元素个数
    - xlsx: zip 完整 + 含 sheet1.xml
    - md/html: 体积与关键标题
    """
    import json as _json
    import zipfile

    report = {}
    for path in files:
        item = {"ok": False, "size": 0, "detail": ""}
        # 自检本身绝不能抛异常：路径非法也要如实报告为「不通过」
        try:
            p = Path(path)
        except (TypeError, ValueError):
            report[f"<非法路径 {path!r}>"] = {
                "ok": False, "size": 0, "detail": "无效的文件路径"}
            continue
        report[p.name] = item
        try:
            if not p.exists():
                item["detail"] = "文件不存在"
                continue
            size = p.stat().st_size
            item["size"] = size
            if size == 0:
                item["detail"] = "文件为空"
                continue
            ext = p.suffix.lower()
            if ext == ".csv":
                text = p.read_text(encoding="utf-8-sig")
                lines = [ln for ln in text.splitlines() if ln.strip()]
                n = max(0, len(lines) - 1)
                item["rows"] = n
                item["detail"] = f"{n} 行数据"
                item["ok"] = (expected_rows is None or n == expected_rows)
                if not item["ok"]:
                    item["detail"] += f"（期望 {expected_rows}）"
            elif ext == ".json":
                data = _json.loads(p.read_text(encoding="utf-8"))
                n = len(data) if isinstance(data, list) else 1
                item["rows"] = n
                item["detail"] = f"{n} 条记录"
                item["ok"] = (expected_rows is None or n == expected_rows)
                if not item["ok"]:
                    item["detail"] += f"（期望 {expected_rows}）"
            elif ext == ".xlsx":
                with zipfile.ZipFile(p) as z:
                    names = z.namelist()
                    bad = z.testzip()
                has_sheet = any("worksheets/sheet1.xml" in nm for nm in names)
                item["detail"] = (f"{len(names)} 个部件"
                                  + ("" if has_sheet else "，缺少 sheet1.xml"))
                item["ok"] = bad is None and has_sheet
            else:                                  # markdown / html
                text = p.read_text(encoding="utf-8", errors="replace")
                item["ok"] = len(text) > 0
                item["detail"] = f"{len(text)} 字符"
        except Exception as e:
            item["ok"] = False
            item["detail"] = f"{type(e).__name__}: {e}"[:120]
    return report