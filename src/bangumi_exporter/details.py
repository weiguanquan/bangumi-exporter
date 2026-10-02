# -*- coding: utf-8 -*-
"""数据补全：简介 / 制作公司 / staff / 声优 / 分集列表 / 播出星期 / 卷数。

数据来源（都已实测可用，api.bgmapi.com 镜像同样支持）：
  /v0/subjects/{id}             -> summary / infobox / eps / volumes / rating
  /v0/subjects/{id}/persons     -> 制作人员（含 relation，如「动画制作」「导演」）
  /v0/subjects/{id}/characters  -> 角色与声优（actors）
  /v0/episodes?subject_id={id}  -> 分集（含 airdate）

这些请求比较贵（每个条目 4 次），所以单独缓存到 .detail_cache.json，
并且支持「只补缺失的条目」，第二次导出几乎零请求。
"""

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import api

CACHE_VERSION = 1

# 「制作公司」的取值优先顺序：这些 relation / infobox 键里第一个非空值即为制作公司
STUDIO_RELATIONS = ["动画制作", "制作", "製作", "开发", "发行", "出品", "工作室"]
STUDIO_INFOBOX = ["动画制作", "制作", "製作", "开发", "发行", "出版社"]

# staff 展示优先级（越靠前越重要）
STAFF_PRIORITY = ["原作", "导演", "监督", "系列构成", "脚本", "编剧", "人物设定",
                  "角色设计", "总作画监督", "作画监督", "音乐", "美术监督",
                  "色彩设计", "摄影监督", "剪辑", "音响监督", "动画制作", "制作"]

SUMMARY_LIMIT = 160          # 表格里「简介」列的最大长度


def _clean(text, limit=None):
    """压掉换行与多余空白，供表格单元格使用。"""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if limit and len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s


def _infobox_map(detail):
    """把 infobox 列表转成 {key: value}（value 可能是列表，取首项）。"""
    out = {}
    for item in (detail.get("infobox") or []):
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        val = item.get("value")
        if isinstance(val, list):
            parts = []
            for v in val:
                if isinstance(v, dict):
                    parts.append(str(v.get("v") or v.get("k") or ""))
                else:
                    parts.append(str(v))
            val = "、".join(p for p in parts if p)
        if key:
            out[str(key)] = _clean(val)
    return out


def _pick_studio(staff, infobox):
    for rel in STUDIO_RELATIONS:
        for p in staff:
            if str(p.get("relation") or "").strip() == rel and p.get("name"):
                return _clean(p["name"])
    for key in STUDIO_INFOBOX:
        if infobox.get(key):
            return infobox[key]
    return ""


def _sort_staff(staff):
    def rank(p):
        rel = str(p.get("relation") or "")
        try:
            return STAFF_PRIORITY.index(rel)
        except ValueError:
            return len(STAFF_PRIORITY)
    return sorted(staff, key=rank)


def parse_subject_detail(detail):
    """把 /v0/subjects/{id} 的响应解析成结构化补充信息。"""
    if not isinstance(detail, dict):
        return None
    ib = _infobox_map(detail)
    return {
        "id": detail.get("id"),
        "summary": _clean(detail.get("summary")),
        "infobox": ib,
        "weekday": ib.get("放送星期", ""),
        "eps": detail.get("eps") or 0,
        "volumes": detail.get("volumes") or 0,
        "platform": detail.get("platform") or ib.get("平台", ""),
        "date": detail.get("date") or "",
        "name": detail.get("name") or "",
        "name_cn": detail.get("name_cn") or ib.get("中文名", ""),
        "aliases": ib.get("别名", ""),
    }


def parse_staff(persons):
    out = []
    for p in (persons or []):
        if not isinstance(p, dict) or not p.get("name"):
            continue
        out.append({
            "id": p.get("id"),
            "name": _clean(p.get("name")),
            "relation": _clean(p.get("relation")),
            "career": p.get("career") or [],
        })
    return _sort_staff(out)


def parse_cast(characters, limit=12):
    out = []
    for c in (characters or []):
        if not isinstance(c, dict):
            continue
        actors = [{"id": a.get("id"), "name": _clean(a.get("name")),
                   "relation": _clean(a.get("relation"))}
                  for a in (c.get("actors") or []) if a.get("name")]
        out.append({
            "id": c.get("id"),
            "name": _clean(c.get("name")),
            "relation": _clean(c.get("relation")),
            "actors": actors,
        })
    # 主角优先
    def rank(c):
        return 0 if c.get("relation") == "主角" else (1 if c.get("relation") == "配角" else 2)
    out.sort(key=rank)
    return out[:limit]


def parse_episodes(eps_payload, limit=200):
    data = (eps_payload or {}).get("data") if isinstance(eps_payload, dict) else eps_payload
    out = []
    for e in (data or []):
        if not isinstance(e, dict):
            continue
        out.append({
            "id": e.get("id"),
            "sort": e.get("sort"),
            "type": e.get("type"),
            "name": _clean(e.get("name_cn") or e.get("name")),
            "name_original": _clean(e.get("name")),
            "airdate": e.get("airdate") or "",
            "duration": e.get("duration") or "",
        })
    out.sort(key=lambda x: (str(x.get("sort") or "")))
    return out[:limit]


# ------------------------------------------------------------------ 缓存

class DetailCache:
    """补充信息缓存（纯本地文件，支持增量）。"""

    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data = {}
        self._load()

    def _load(self):
        if self.path.is_file():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and payload.get("version") == CACHE_VERSION:
                    self._data = payload.get("items") or {}
            except (OSError, ValueError):
                self._data = {}

    def get(self, sid):
        with self._lock:
            return self._data.get(str(sid))

    def put(self, sid, value):
        with self._lock:
            self._data[str(sid)] = value

    def has(self, sid):
        with self._lock:
            return str(sid) in self._data

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            payload = {"version": CACHE_VERSION, "items": self._data}
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def count(self):
        with self._lock:
            return len(self._data)

    def snapshot(self):
        """返回当前缓存的浅拷贝（离线补全用）。"""
        with self._lock:
            return dict(self._data)

    def clear(self):
        with self._lock:
            self._data = {}


# ------------------------------------------------------------------ 抓取

def fetch_one(sid, base, log=None):
    """抓取单个条目的完整补充信息（4 个请求）。"""
    detail = api.http_get(f"{base}/v0/subjects/{sid}", log=None, retries=2)
    if isinstance(detail, tuple):
        detail = detail[1]
    out = parse_subject_detail(detail) or {}
    if not out:
        return None

    try:
        persons = api.http_get(f"{base}/v0/subjects/{sid}/persons", log=None, retries=2)
        if isinstance(persons, tuple):
            persons = persons[1]
        out["staff"] = parse_staff(persons)
    except Exception:
        out["staff"] = []

    try:
        chars = api.http_get(f"{base}/v0/subjects/{sid}/characters", log=None, retries=2)
        if isinstance(chars, tuple):
            chars = chars[1]
        out["cast"] = parse_cast(chars)
    except Exception:
        out["cast"] = []

    try:
        eps_payload = api.http_get(
            f"{base}/v0/episodes?subject_id={sid}&limit=200", log=None, retries=2)
        if isinstance(eps_payload, tuple):
            eps_payload = eps_payload[1]
        out["episodes"] = parse_episodes(eps_payload)
    except Exception:
        out["episodes"] = []

    out["studio"] = _pick_studio(out.get("staff") or [], out.get("infobox") or {})
    return out


def supplement(rows, base, cache_path=None, log=None, cancel_event=None,
               workers=6, max_subjects=None):
    """为所有行补全详情。返回 {sid: info}（同时写入缓存）。

    只抓缓存里没有的条目，因此第二次导出基本零请求。
    """
    rows = list(rows or [])
    ids = []
    seen = set()
    for r in rows:
        sid = r.get("条目ID")
        if not sid:
            continue
        key = str(sid)
        if key in seen:
            continue
        seen.add(key)
        ids.append(key)
    if max_subjects:
        ids = ids[:max_subjects]

    cache = DetailCache(cache_path) if cache_path else None
    result = {}
    todo = []
    for sid in ids:
        if cache is not None and cache.has(sid):
            result[sid] = cache.get(sid)
        else:
            todo.append(sid)

    if log:
        log(f"  详情补全：{len(ids)} 个条目，缓存命中 {len(result)}，"
            f"需要抓取 {len(todo)}")
    if not todo:
        return result

    done = 0
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 12))) as ex:
        futs = {ex.submit(fetch_one, sid, base, log): sid for sid in todo}
        for fut in as_completed(futs):
            if cancel_event is not None and cancel_event.is_set():
                break
            sid = futs[fut]
            try:
                info = fut.result()
            except Exception:
                info = None
            if info:
                result[sid] = info
                if cache is not None:
                    cache.put(sid, info)
            done += 1
            if log and (done % 20 == 0 or done == len(todo)):
                log(f"  详情补全进度 {done}/{len(todo)}")

    if cache is not None:
        cache.save()
    return result


def fill_rows(rows, supp):
    """把补充信息写回导出行。"""
    filled = 0
    for r in rows:
        info = supp.get(str(r.get("条目ID") or ""))
        if not info:
            continue
        r["制作公司"] = info.get("studio") or r.get("制作公司") or ""
        r["放送星期"] = info.get("weekday") or r.get("放送星期") or ""
        if info.get("volumes"):
            r["卷数"] = info["volumes"]
        r["简介"] = _clean(info.get("summary"), SUMMARY_LIMIT)
        if info.get("platform") and not r.get("平台"):
            r["平台"] = info["platform"]
        filled += 1
    return filled


# ------------------------------------------------------------------ 渲染

def render_supplement_markdown(rows, supp, staff_limit=6, cast_limit=6,
                               ep_limit=30, top=40):
    """生成「详情」Markdown：staff / 声优 / 分集。"""
    if not supp:
        return ""
    L = ["", "## 条目详情（简介 / 制作 / staff / 声优 / 分集）", ""]
    shown = 0
    for r in rows:
        sid = str(r.get("条目ID") or "")
        info = supp.get(sid)
        if not info:
            continue
        shown += 1
        if shown > top:
            break
        name = r.get("中文名") or info.get("name_cn") or info.get("name") or sid
        L.append(f"### [{name}](https://bgm.tv/subject/{sid})")
        meta = []
        if info.get("platform"):
            meta.append(f"平台 {info['platform']}")
        if info.get("weekday"):
            meta.append(f"放送星期 {info['weekday']}")
        if info.get("eps"):
            meta.append(f"话数 {info['eps']}")
        if info.get("volumes"):
            meta.append(f"卷数 {info['volumes']}")
        if info.get("studio"):
            meta.append(f"制作 {info['studio']}")
        if meta:
            L.append("")
            L.append("- " + " ｜ ".join(meta))
        if info.get("summary"):
            L.append("")
            L.append(f"> {info['summary']}")
        staff = info.get("staff") or []
        if staff:
            L.append("")
            L.append("**制作人员**：" + "；".join(
                f"{p['relation'] or '其他'}：{p['name']}"
                for p in staff[:staff_limit]))
        cast = info.get("cast") or []
        if cast:
            parts = []
            for c in cast[:cast_limit]:
                cvs = "、".join(a["name"] for a in (c.get("actors") or []))
                parts.append(f"{c['name']}（{cvs or '未标注'}）")
            L.append("")
            L.append("**主要角色 / 声优**：" + "；".join(parts))
        eps = info.get("episodes") or []
        if eps:
            L.append("")
            L.append(f"**分集（{len(eps)}）**")
            L.append("")
            L.append("| # | 标题 | 播出日期 |")
            L.append("|---|---|---|")
            for e in eps[:ep_limit]:
                L.append(f"| {e.get('sort')} | {e.get('name') or e.get('name_original') or ''} "
                         f"| {e.get('airdate') or '-'} |")
            if len(eps) > ep_limit:
                L.append(f"| … | 其余 {len(eps) - ep_limit} 集见 JSON | |")
        L.append("")
    if shown:
        L.append(f"> 仅展示前 {min(shown - 1, top)} 条；完整数据见「_详情.json」。")
    return "\n".join(L) + "\n"


def supplement_json(supp, rows=None):
    """详情导出成 JSON 用的精简结构。"""
    order = []
    if rows:
        for r in rows:
            sid = str(r.get("条目ID") or "")
            if sid and sid not in order:
                order.append(sid)
    else:
        order = list(supp.keys())
    out = []
    for sid in order:
        info = supp.get(sid)
        if not info:
            continue
        out.append({
            "条目ID": int(sid) if str(sid).isdigit() else sid,
            "中文名": info.get("name_cn") or "",
            "原名": info.get("name") or "",
            "简介": info.get("summary") or "",
            "放送星期": info.get("weekday") or "",
            "话数": info.get("eps") or 0,
            "卷数": info.get("volumes") or 0,
            "平台": info.get("platform") or "",
            "制作公司": info.get("studio") or "",
            "制作人员": [{"职务": p.get("relation"), "姓名": p.get("name")}
                         for p in (info.get("staff") or [])],
            "角色声优": [{"角色": c.get("name"), "定位": c.get("relation"),
                          "声优": [a.get("name") for a in (c.get("actors") or [])]}
                         for c in (info.get("cast") or [])],
            "分集": [{"集数": e.get("sort"), "标题": e.get("name"),
                      "播出日期": e.get("airdate")} for e in (info.get("episodes") or [])],
        })
    return out
