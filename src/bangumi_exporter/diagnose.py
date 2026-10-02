# -*- coding: utf-8 -*-
"""空列诊断：解释每一列为什么是空的，并给出可执行的补救建议。

用户看到「我的评分 / 我的短评 / 我的标签」全是空白时，
第一反应往往是「程序有 bug」。实际上这些字段来自 Bangumi 的
个人收藏数据，用户没填就是空的。

本模块不猜：如果调用方能提供原始接口数据（raw_items），
就统计接口真实返回值作为证据（例如 rate>0 的条目数）。
"""

from .constants import FIELD_NAMES

# 每一列的来源与含义（给人看的解释）
COLUMN_SOURCE = {
    "序号": ("本程序生成", "按导出顺序自动编号"),
    "条目类型": ("subject.type", "动画 / 书籍 / 游戏 / 音乐 / 三次元"),
    "收藏类型": ("collection.type", "想看 / 看过 / 在看 / 搁置 / 抛弃"),
    "中文名": ("subject.name_cn", "极少数条目官方没有中文名，会回退显示原名"),
    "原名": ("subject.name", "条目原始名称（通常为日文）"),
    "我的评分": ("collection.rate", "**只有你打过分的条目才有值**"),
    "BGM评分": ("subject.score", "全站平均分"),
    "评分人数": ("subject.rating.total", "打分人数（注意：不是收藏人数）"),
    "排名": ("subject.rank", "评分人数不足的条目官方不给排名"),
    "看到第几集": ("collection.ep_status", "**只有你手动标记过进度才有值**"),
    "总集数": ("subject.eps", "官方未公布集数的条目为空"),
    "放送日期": ("subject.date", "官方未填日期的条目为空"),
    "平台": ("subject.platform", "TV / OVA / 剧场版 / WEB 等，取自详情接口"),
    "条目标签": ("subject.tags", "社区给该条目打的标签（含制作公司/年份/题材）"),
    "我的短评": ("collection.comment", "**只有你写过短评才有值**"),
    "我的标签": ("collection.tags", "**只有你给条目标过标签才有值**"),
    "条目ID": ("subject.id", "Bangumi 条目编号"),
    "条目链接": ("由 条目ID 拼接", "https://bgm.tv/subject/{id}"),
    "更新时间": ("collection.updated_at", "你最后一次改动该收藏的时间"),
    "封面": ("subject.images", "各尺寸封面图片地址"),
    "条目链接": ("由 条目ID 拼接", "https://bgm.tv/subject/{id}"),
}

# 属于「用户自己没填」的列 —— 空是正常的，不是 bug
USER_OWNED = {"我的评分", "我的短评", "我的标签", "看到第几集"}

# 官方的历史遗留问题（旧条目或冷门条目缺字段）
OFFICIAL_GAP = {"排名", "总集数", "放送日期", "平台", "中文名"}

# 原始接口字段 -> 导出列，用于生成证据
_RAW_PROBE = {
    "我的评分": lambda it: (it.get("rate") or 0) > 0,
    "我的短评": lambda it: bool(str(it.get("comment") or "").strip()),
    "我的标签": lambda it: bool(it.get("tags")),
    "看到第几集": lambda it: (it.get("ep_status") or 0) > 0,
}


def _verdict(col, filled, total, evidence):
    if filled == total and total:
        return "该列已全部填充，无问题。"
    if col in USER_OWNED:
        if filled == 0:
            ev = ""
            if evidence:
                ev = f"（接口真实返回：{evidence}）"
            return (f"**这不是程序的 bug**：该列来自你自己的 Bangumi 收藏数据，"
                    f"接口返回的原始值就是空的{ev}。"
                    f"去 Bangumi 网页或 App 补上对应内容，再重新导出即可填充。")
        return (f"你有 {filled}/{total} 条填了这项，其余条目你本来就没填，属正常。")
    if col in OFFICIAL_GAP:
        if filled == 0:
            return "Bangumi 官方对这批条目没有提供该字段（常见于冷门或未定档条目）。"
        return (f"Bangumi 官方只对其中 {filled}/{total} 条提供了该字段，"
                f"其余条目官方数据里就是空的，程序无法凭空补出。")
    return "该列部分为空，属正常的数据缺失。"


def _all_zero(rows, col):
    """该列虽然有值，但全是 0 —— 对用户来说和「空」没区别。"""
    vals = [str(r.get(col, "")).strip() for r in rows]
    vals = [v for v in vals if v]
    if not vals:
        return False
    return all(v in ("0", "0.0", "0.00") for v in vals)


def diagnose_columns(rows, raw_items=None, field_names=None):
    """逐列体检。

    rows      : 导出的展平行列表
    raw_items : 可选，原始收藏接口返回的条目列表（用于生成硬证据）
    返回 {total, columns:[...], empty:[...], user_owned_empty:[...]}
    """
    cols = list(field_names or FIELD_NAMES)
    rows = list(rows or [])
    total = len(rows)

    evidence_map = {}
    if raw_items:
        for col, probe in _RAW_PROBE.items():
            try:
                n = sum(1 for it in raw_items if probe(it))
            except Exception:
                continue
            evidence_map[col] = f"{n}/{len(raw_items)} 条满足条件"
            if col == "我的评分":
                evidence_map[col] = f"{n}/{len(raw_items)} 条 rate>0"
            elif col == "看到第几集":
                evidence_map[col] = f"{n}/{len(raw_items)} 条 ep_status>0"

    out = []
    for col in cols:
        filled = sum(1 for r in rows if str(r.get(col, "")).strip())
        ratio = (filled / total) if total else 0.0
        if total == 0:
            status = "empty"
        elif filled == total:
            status = "ok"
        elif filled == 0:
            status = "empty"
        else:
            status = "partial"
        source, explain = COLUMN_SOURCE.get(col, ("未知", ""))
        zero_only = status == "ok" and _all_zero(rows, col)
        if zero_only:
            status = "all_zero"
        verdict = _verdict(col, filled, total, evidence_map.get(col, ""))
        if zero_only:
            verdict = (f"该列 {total} 条全部是 0 —— 值本身是真的（接口返回就是 0），"
                       f"但等同于「你没有记录过」。这不是程序丢数据。")
            if col in USER_OWNED:
                verdict += "去 Bangumi 标记进度后重新导出即可。"
        out.append({
            "column": col,
            "source": source,
            "explain": explain,
            "filled": filled,
            "total": total,
            "ratio": round(ratio, 4),
            "status": status,
            "evidence": evidence_map.get(col, ""),
            "verdict": verdict,
        })

    empty = [c["column"] for c in out if c["status"] == "empty"]
    user_owned_empty = [c for c in empty if c in USER_OWNED]
    return {
        "total": total,
        "columns": out,
        "empty": empty,
        "user_owned_empty": user_owned_empty,
        "summary": _summary(total, out, user_owned_empty),
    }


def _summary(total, cols, user_owned_empty):
    if total == 0:
        return "没有数据，无法体检。"
    empty = [c["column"] for c in cols if c["status"] == "empty"]
    zeros = [c["column"] for c in cols if c["status"] == "all_zero"]
    if not empty and not zeros:
        return f"体检通过：{len(cols)} 列在 {total} 条数据上都有值。"
    parts = []
    if empty:
        parts.append(f"共 {len(cols)} 列，其中 {len(empty)} 列完全为空：{'、'.join(empty)}。")
    else:
        parts.append(f"共 {len(cols)} 列，没有全空的列。")
    if user_owned_empty:
        parts.append(f"其中 {'、'.join(user_owned_empty)} 属于「你自己还没填」"
                     f"（Bangumi 接口返回的就是空值），不是程序的问题。")
    others = [c for c in empty if c not in USER_OWNED]
    if others:
        parts.append(f"另外 {'、'.join(others)} 为空是 Bangumi 官方数据缺失。")
    if zeros:
        parts.append(f"还有 {'、'.join(zeros)} 的值全部是 0（真实值，但等同未记录）。")
    return "".join(parts)


def render_diagnosis_markdown(diag):
    """把体检结果渲染成 Markdown 片段，附在统计报告后面。"""
    if not diag or not diag.get("columns"):
        return ""
    lines = ["", "## 数据体检（每一列为什么有值/没值）", "",
             diag.get("summary", ""), "",
             "| 列 | 填充 | 来源 | 说明 |", "|---|---|---|---|"]
    icon = {"ok": "✅", "partial": "◐", "empty": "⬜", "all_zero": "0️⃣"}
    for c in diag["columns"]:
        lines.append(
            f"| {icon.get(c['status'], '')} {c['column']} "
            f"| {c['filled']}/{c['total']} | `{c['source']}` | {c['explain']} |")
    empties = [c for c in diag["columns"] if c["status"] != "ok"]
    if empties:
        lines += ["", "### 空列的具体原因", ""]
        for c in empties:
            lines.append(f"- **{c['column']}**（{c['filled']}/{c['total']}）：{c['verdict']}")
    return "\n".join(lines) + "\n"
