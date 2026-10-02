# -*- coding: utf-8 -*-
"""收藏历史归档与快照对比。

每次导出可选归档一份完整快照（JSON），之后就能回答：
  - 我这两个月新增了哪些番？
  - 我把哪些条目从「在看」改成了「看过」？
  - 哪些条目被我删掉了？
  - 我的评分/BGM 评分发生了什么变化？
"""

import json
import time
from datetime import datetime
from pathlib import Path

VERSION = 1
DEFAULT_KEEP = 60          # 默认只保留最近 60 份快照
ARCHIVE_DIRNAME = "历史归档"


def _sid(path):
    return Path(path).stem


def archive_snapshot(rows, archive_dir, meta=None, keep=DEFAULT_KEEP):
    """把当前行归档为一份快照，返回快照信息。"""
    d = Path(archive_dir)
    d.mkdir(parents=True, exist_ok=True)
    now = time.time()
    sid = datetime.fromtimestamp(now).strftime("%Y%m%d-%H%M%S")
    # 同一秒内重复归档时补后缀，避免互相覆盖
    p = d / f"{sid}.json"
    n = 1
    while p.exists():
        sid = datetime.fromtimestamp(now).strftime("%Y%m%d-%H%M%S") + f"-{n}"
        p = d / f"{sid}.json"
        n += 1

    payload = {
        "version": VERSION,
        "id": sid,
        "saved_at": now,
        "saved_at_str": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(rows),
        "meta": meta or {},
        "rows": list(rows),
    }
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)

    # 只保留最近 keep 份
    snaps = list_snapshots(d)
    for old in snaps[keep:]:
        try:
            (d / f"{old['id']}.json").unlink()
        except OSError:
            pass
    return {"id": sid, "path": str(p), "count": len(rows),
            "saved_at": now, "total_snapshots": min(len(snaps), keep)}


def list_snapshots(archive_dir):
    """列出所有快照（新的在前）。只读头部元信息，避免加载大文件。"""
    d = Path(archive_dir)
    if not d.is_dir():
        return []
    out = []
    for f in d.glob("*.json"):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({
            "id": payload.get("id") or _sid(f),
            "path": str(f),
            "saved_at": payload.get("saved_at") or 0,
            "saved_at_str": payload.get("saved_at_str") or "",
            "count": payload.get("count") or len(payload.get("rows") or []),
            "meta": payload.get("meta") or {},
        })
    out.sort(key=lambda x: x["saved_at"], reverse=True)
    return out


def load_snapshot(archive_dir, snapshot_id):
    p = Path(archive_dir) / f"{snapshot_id}.json"
    payload = json.loads(p.read_text(encoding="utf-8"))
    return payload.get("rows") or []


def _by_id(rows):
    out = {}
    for r in rows:
        sid = str(r.get("条目ID") or "").strip()
        if sid:
            out[sid] = r
    return out


# 对比时关注的字段（顺序即展示顺序）
COMPARE_FIELDS = ["收藏类型", "我的评分", "看到第几集", "我的短评",
                  "我的标签", "BGM评分", "排名", "评分人数", "更新时间"]


def _key(r):
    """用于展平的签名：只看我们关心的字段。"""
    return {f: str(r.get(f, "") or "") for f in COMPARE_FIELDS}


def diff_snapshots(old_rows, new_rows):
    """对比两次快照。old_rows 为较早的一份。"""
    a, b = _by_id(old_rows), _by_id(new_rows)
    added = [b[k] for k in b if k not in a]
    removed = [a[k] for k in a if k not in b]
    changed = []
    for k in b:
        if k not in a:
            continue
        ka, kb = _key(a[k]), _key(b[k])
        if ka == kb:
            continue
        fields = []
        for f in COMPARE_FIELDS:
            if ka[f] != kb[f]:
                fields.append({"field": f, "from": ka[f], "to": kb[f]})
        changed.append({
            "id": k,
            "name": b[k].get("中文名") or b[k].get("原名") or "",
            "fields": fields,
        })
    unchanged = len(b) - len(added) - len(changed)
    return {
        "old_count": len(old_rows),
        "new_count": len(new_rows),
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": max(0, unchanged),
        "has_changes": bool(added or removed or changed),
    }


def _fmt_change(c):
    return "；".join(f"{f['field']} {f['from'] or '空'} → {f['to'] or '空'}"
                     for f in c["fields"])


def diff_latest(archive_dir):
    """对比最近两份快照。不足两份时返回 None。"""
    snaps = list_snapshots(archive_dir)
    if len(snaps) < 2:
        return None
    new, old = snaps[0], snaps[1]
    d = diff_snapshots(load_snapshot(archive_dir, old["id"]),
                       load_snapshot(archive_dir, new["id"]))
    d["old"] = old
    d["new"] = new
    return d


def compare_snapshots(archive_dir, id_old, id_new):
    """对比指定的两份快照。"""
    d = diff_snapshots(load_snapshot(archive_dir, id_old),
                       load_snapshot(archive_dir, id_new))
    snaps = {s["id"]: s for s in list_snapshots(archive_dir)}
    d["old"] = snaps.get(id_old) or {"id": id_old}
    d["new"] = snaps.get(id_new) or {"id": id_new}
    return d


def render_diff_markdown(diff, limit=40):
    """把快照差异渲染成 Markdown。"""
    if not diff:
        return ""
    old, new = diff.get("old") or {}, diff.get("new") or {}
    L = ["", "## 收藏变化（快照对比）", "",
         f"- 对比：`{old.get('saved_at_str') or old.get('id')}` "
         f"({diff['old_count']} 条) → `{new.get('saved_at_str') or new.get('id')}` "
         f"({diff['new_count']} 条)",
         f"- 新增 {len(diff['added'])}，删除 {len(diff['removed'])}，"
         f"修改 {len(diff['changed'])}，未变 {diff['unchanged']}"]
    if not diff["has_changes"]:
        L.append("\n> 两次快照之间没有任何变化。\n")
        return "\n".join(L) + "\n"
    if diff["added"]:
        L += ["", f"### 新增 {len(diff['added'])} 条", ""]
        for r in diff["added"][:limit]:
            L.append(f"- [{r.get('中文名') or r.get('原名')}]"
                     f"(https://bgm.tv/subject/{r.get('条目ID')}) "
                     f"（{r.get('收藏类型')}）")
    if diff["removed"]:
        L += ["", f"### 删除 {len(diff['removed'])} 条", ""]
        for r in diff["removed"][:limit]:
            L.append(f"- {r.get('中文名') or r.get('原名')}（{r.get('收藏类型')}）")
    if diff["changed"]:
        L += ["", f"### 修改 {len(diff['changed'])} 条", "",
              "| 条目 | 变化 |", "|---|---|"]
        for c in diff["changed"][:limit]:
            L.append(f"| {c['name']} | {_fmt_change(c)} |")
    return "\n".join(L) + "\n"
