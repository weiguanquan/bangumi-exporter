# -*- coding: utf-8 -*-
"""统计报告生成 + 前端图表数据构建。

v3.1 新增的高级分析：
  - 年度 / 季度 放送分布（看你的口味如何随年份变化）
  - Top 标签（你的口味关键词）
  - 平台分布
  - 「我的评分 vs BGM 评分」差异分析（你是严格还是宽容？）
  - 两者相关系数（你的口味和大众是否一致）
  - 追番完成度（看到第几集 / 总集数）
  - 评分差最大的条目榜（最"意难平"与最"真香"）
"""

from collections import Counter, defaultdict

from .constants import clean_weekday, WEEKDAYS


def _is_number(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return False
        try:
            float(s)
            return True
        except ValueError:
            return False
    return False


def _num(v):
    return float(v) if _is_number(v) else None


def _year_of(row):
    """从「放送日期」取年份，形如 2024-04-01 / 2024-04 / 2024。"""
    d = str(row.get("放送日期") or "").strip()
    if len(d) >= 4 and d[:4].isdigit():
        y = int(d[:4])
        if 1900 <= y <= 2200:
            return y
    return None


def _quarter_of(row):
    """返回 (年, 季度) 或 None。"""
    d = str(row.get("放送日期") or "").strip()
    if len(d) < 7:
        return None
    y = _year_of(row)
    if y is None:
        return None
    try:
        m = int(d[5:7])
    except ValueError:
        return None
    if not 1 <= m <= 12:
        return None
    return y, (m - 1) // 3 + 1


def _pearson(xs, ys):
    """皮尔逊相关系数（无第三方依赖）。"""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def paired_scores(rows):
    """返回同时有「我的评分」和「BGM评分」的 (我的, BGM, 行) 列表。"""
    out = []
    for r in rows:
        mine, bgm = _num(r.get("我的评分")), _num(r.get("BGM评分"))
        if mine is not None and bgm is not None:
            out.append((mine, bgm, r))
    return out


def build_chart_data(rows):
    """为前端仪表盘构建结构化图表数据（纯 JSON 可序列化）。"""
    by_subject = Counter(r.get("条目类型") or "未知" for r in rows)
    by_collection = Counter(r.get("收藏类型") or "未知" for r in rows)

    # BGM 评分分布（0.5 步长）
    bgm_scores = [float(r["BGM评分"]) for r in rows if _is_number(r.get("BGM评分"))]
    bgm_dist = {}
    for s in bgm_scores:
        key = f"{round(s * 2) / 2:.1f}"
        bgm_dist[key] = bgm_dist.get(key, 0) + 1

    # 我的评分分布（整数 1-10）
    my_rates = [int(float(r["我的评分"])) for r in rows if _is_number(r.get("我的评分"))]
    my_dist = {}
    for s in my_rates:
        my_dist[str(s)] = my_dist.get(str(s), 0) + 1

    # 观看进度（覆盖全部五种收藏状态）
    progress = {"finished": 0, "watching": 0, "plan": 0, "on_hold": 0,
                "dropped": 0}
    code = {"看过": "finished", "在看": "watching", "想看": "plan",
            "搁置": "on_hold", "抛弃": "dropped"}
    for r in rows:
        k = code.get(r.get("收藏类型", ""))
        if k:
            progress[k] += 1

    # Top 榜单
    def top_n(key, n=10):
        seq = sorted(rows, key=lambda r: -(float(r.get(key))
                                           if _is_number(r.get(key)) else -1))
        return [{"name": r.get("中文名", ""), "value": r.get(key),
                 "id": r.get("条目ID")} for r in seq[:n]]

    avg_bgm = sum(bgm_scores) / len(bgm_scores) if bgm_scores else 0
    avg_mine = sum(my_rates) / len(my_rates) if my_rates else 0

    # ---- 年度 / 季度分布 ----
    by_year = Counter()
    by_quarter = Counter()
    for r in rows:
        y = _year_of(r)
        if y:
            by_year[y] += 1
        q = _quarter_of(r)
        if q:
            by_quarter[f"{q[0]}-Q{q[1]}"] += 1

    # ---- 标签 / 平台 ----
    # 「我的标签」（你自己标的）通常很少甚至为空；「条目标签」是社区标签，
    # 内容更丰富。两者的条目数分开统计，报告里分别展示。
    my_tag_counter = Counter()
    tag_counter = Counter()
    for r in rows:
        for t in str(r.get("我的标签") or "").split("|"):
            t = t.strip()
            if t:
                my_tag_counter[t] += 1
        for t in str(r.get("条目标签") or "").split("|"):
            t = t.strip()
            if t:
                tag_counter[t] += 1
    by_platform = Counter(r.get("平台") or "未知" for r in rows)

    # ---- 评分差异分析 ----
    pairs = paired_scores(rows)
    diffs = [mine - bgm for mine, bgm, _ in pairs]
    delta_dist = Counter()
    for d in diffs:
        delta_dist[f"{d:+.1f}"] = delta_dist.get(f"{d:+.1f}", 0) + 1
    avg_delta = sum(diffs) / len(diffs) if diffs else 0
    corr = _pearson([p[0] for p in pairs], [p[1] for p in pairs])
    harsher = sum(1 for d in diffs if d < -0.5)
    kinder = sum(1 for d in diffs if d > 0.5)

    def delta_board(sign, n=8):
        sel = [p for p in pairs if (p[0] - p[1]) * sign > 0]
        sel.sort(key=lambda p: -(p[0] - p[1]) * sign)
        return [{"name": p[2].get("中文名", ""), "mine": p[0], "bgm": p[1],
                 "delta": round(p[0] - p[1], 1), "id": p[2].get("条目ID")}
                for p in sel[:n]]

    # ---- 追番完成度 ----
    completed = in_progress = not_started = 0
    for r in rows:
        eps, tot = _num(r.get("看到第几集")), _num(r.get("总集数"))
        if tot is None or tot <= 0:
            continue
        if eps is None or eps <= 0:
            not_started += 1
        elif eps >= tot:
            completed += 1
        else:
            in_progress += 1

    return {
        "total": len(rows),
        "avg_bgm": round(avg_bgm, 2),
        "avg_mine": round(avg_mine, 2),
        "by_subject_type": dict(by_subject.most_common()),
        "by_collection_type": dict(by_collection.most_common()),
        "bgm_score_dist": dict(sorted(bgm_dist.items(), key=lambda x: float(x[0]))),
        "my_rate_dist": dict(sorted(my_dist.items(), key=lambda x: int(x[0]))),
        "progress": progress,
        "top_bgm": top_n("BGM评分"),
        "top_mine": top_n("我的评分"),
        # v3.1 高级分析
        "by_year": dict(sorted(by_year.items())),
        "by_quarter": dict(sorted(by_quarter.items())),
        "top_tags": [{"name": k, "value": v}
                     for k, v in tag_counter.most_common(20)],
        "my_top_tags": [{"name": k, "value": v}
                        for k, v in my_tag_counter.most_common(20)],
        "by_platform": dict(by_platform.most_common()),
        "rating": {
            "paired": len(pairs),
            "avg_delta": round(avg_delta, 2),
            "correlation": round(corr, 3) if corr is not None else None,
            "harsher": harsher,
            "kinder": kinder,
            "same": len(pairs) - harsher - kinder,
            "delta_dist": dict(sorted(delta_dist.items(),
                                      key=lambda x: float(x[0]))),
            "most_harsh": delta_board(-1),
            "most_kind": delta_board(1),
        },
        "completion": {
            "completed": completed,
            "in_progress": in_progress,
            "not_started": not_started,
        },
    }


def render_stats_markdown(rows, uid, nickname):
    """生成 Markdown 格式的统计报告。"""
    total = len(rows)
    lines = [
        "# Bangumi 收藏统计报告",
        "",
        f"- 用户：{nickname} (id={uid})",
        f"- 总条目数：{total}",
        "",
        "## 按条目类型",
        "",
        "| 类型 | 数量 |",
        "|---|---|",
    ]
    by_subject = Counter(r.get("条目类型") or "未知" for r in rows)
    for k, v in by_subject.most_common():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines += ["## 按收藏类型", "", "| 类型 | 数量 |", "|---|---|"]
    by_type = Counter(r.get("收藏类型") or "未知" for r in rows)
    for k, v in by_type.most_common():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    scores = [float(r["BGM评分"]) for r in rows if _is_number(r.get("BGM评分"))]
    my_rates = [float(r["我的评分"]) for r in rows if _is_number(r.get("我的评分"))]

    lines.append("## 评分统计")
    lines.append("")
    if scores:
        lines.append(f"- BGM 平均分：**{sum(scores) / len(scores):.2f}**"
                     f"（{len(scores)} 条有评分）")
    if my_rates:
        lines.append(f"- 我的平均评分：**{sum(my_rates) / len(my_rates):.2f}**"
                     f"（{len(my_rates)} 条已打分）")
    lines.append("")

    if my_rates:
        lines += ["## 我的评分分布", "", "| 评分 | 数量 |", "|---|---|"]
        c = Counter(int(x) for x in my_rates)
        for s in sorted(c, reverse=True):
            lines.append(f"| {s} | {c[s]} {'#' * min(c[s], 40)} |")
        lines.append("")

    def top(key, label, n=10):
        lines.append(f"## {label} Top {n}")
        lines.append("")
        lines.append("| # | 中文名 | 值 |")
        lines.append("|---|---|---|")
        seq = sorted(rows, key=lambda r: -(float(r.get(key))
                                           if _is_number(r.get(key)) else -1))
        for i, r in enumerate(seq[:n], 1):
            lines.append(f"| {i} | {r.get('中文名')} | {r.get(key)} |")
        lines.append("")

    if my_rates:
        top("我的评分", "我的评分")
    if scores:
        top("BGM评分", "BGM 评分")

    # ---- v3.1：年度分布 ----
    by_year = Counter()
    for r in rows:
        y = _year_of(r)
        if y:
            by_year[y] += 1
    if by_year:
        lines += ["## 按放送年份", "", "| 年份 | 数量 |", "|---|---|"]
        for y in sorted(by_year, reverse=True):
            lines.append(f"| {y} | {by_year[y]} "
                         f"{'#' * min(by_year[y], 40)} |")
        lines.append("")

    # ---- v3.1：季度分布 ----
    by_q = Counter()
    for r in rows:
        q = _quarter_of(r)
        if q:
            by_q[q] += 1
    if by_q:
        lines += ["## 按放送季度（最近 12 个）", "",
                  "| 季度 | 数量 |", "|---|---|"]
        for q in sorted(by_q, reverse=True)[:12]:
            lines.append(f"| {q[0]} Q{q[1]} | {by_q[q]} "
                         f"{'#' * min(by_q[q], 40)} |")
        lines.append("")

    # ---- v3.1：Top 标签（我的 + 社区） ----
    my_tag_counter = Counter()
    tag_counter = Counter()
    for r in rows:
        for t in str(r.get("我的标签") or "").split("|"):
            if t.strip():
                my_tag_counter[t.strip()] += 1
        for t in str(r.get("条目标签") or "").split("|"):
            if t.strip():
                tag_counter[t.strip()] += 1
    if my_tag_counter:
        lines += ["## 我的标签 Top 20", "", "| 标签 | 条目数 |", "|---|---|"]
        for t, n in my_tag_counter.most_common(20):
            lines.append(f"| {t} | {n} |")
        lines.append("")
    if tag_counter:
        lines += ["## 社区标签 Top 20（你收藏条目的题材/制作分布）", "",
                  "| 标签 | 条目数 |", "|---|---|"]
        for t, n in tag_counter.most_common(20):
            lines.append(f"| {t} | {n} |")
        lines.append("")

    # ---- v3.1：平台分布 ----
    by_platform = Counter(r.get("平台") or "未知" for r in rows)
    if len(by_platform) > 1:
        lines += ["## 按平台", "", "| 平台 | 数量 |", "|---|---|"]
        for p, n in by_platform.most_common():
            lines.append(f"| {p} | {n} |")
        lines.append("")

    # ---- v3.1：评分差异分析 ----
    pairs = paired_scores(rows)
    if pairs:
        diffs = [m - b for m, b, _ in pairs]
        avg_delta = sum(diffs) / len(diffs)
        corr = _pearson([p[0] for p in pairs], [p[1] for p in pairs])
        harsher = sum(1 for d in diffs if d < -0.5)
        kinder = sum(1 for d in diffs if d > 0.5)
        lines += [
            "## 我的评分 vs BGM 评分",
            "",
            f"- 同时有评分的条目：{len(pairs)}",
            f"- 平均分差（我 - BGM）：**{avg_delta:+.2f}**",
            f"- 我打分更低（< -0.5）：{harsher} 条",
            f"- 我打分更高（> +0.5）：{kinder} 条",
            f"- 基本一致：{len(pairs) - harsher - kinder} 条",
        ]
        if corr is not None:
            lines.append(f"- 相关系数：**{corr:.3f}**"
                         "（越接近 1 越与大众口味一致）")
        lines.append("")

        for sign, label in ((-1, "我最不认同 BGM 的条目（我打得更低）"),
                            (1, "我最欣赏的冷门条目（我打得更高）")):
            sel = [p for p in pairs if (p[0] - p[1]) * sign > 0]
            sel.sort(key=lambda p: -(p[0] - p[1]) * sign)
            if not sel:
                continue
            lines += [f"### {label}", "",
                      "| # | 中文名 | 我的评分 | BGM | 分差 |",
                      "|---|---|---|---|---|"]
            for i, (m, b, r) in enumerate(sel[:8], 1):
                lines.append(f"| {i} | {r.get('中文名')} | {m:g} | {b:g} | "
                             f"{m - b:+.1f} |")
            lines.append("")

    # ---- 观看进度 ----
    finished = watching = 0
    for r in rows:
        eps, total_eps = r.get("看到第几集"), r.get("总集数")
        if _is_number(eps) and _is_number(total_eps) and float(total_eps) > 0:
            if float(eps) >= float(total_eps):
                finished += 1
            elif float(eps) > 0:
                watching += 1
    lines += [
        "## 观看进度",
        "",
        f"- 已看完（看到 == 总集数）：{finished}",
        f"- 看到一半（0 < 看到 < 总集数）：{watching}",
        "",
    ]
    return "\n".join(lines)


# ======================================================================
# 其它类型专门统计（书籍卷数 / 音乐 / 游戏 / 三次元）
# ======================================================================

TYPE_METRICS = {
    "书籍": ["卷数", "总集数"],
    "游戏": ["总集数"],
    "音乐": ["总集数"],
    "三次元": ["总集数"],
    "动画": ["总集数"],
}


def _stats_of(values):
    """给一组数字算 min/max/avg/median。"""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    n = len(vals)
    mid = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return {
        "count": n,
        "min": vals[0],
        "max": vals[-1],
        "avg": round(sum(vals) / n, 2),
        "median": round(mid, 1),
        "total": round(sum(vals), 2),
    }


def build_type_stats(rows):
    """按「条目类型」分组做专门统计（书籍看卷数，游戏看平台……）。"""
    groups = defaultdict(lambda: {
        "count": 0, "collection": Counter(), "scores": [], "my_scores": [],
        "volumes": [], "eps": [], "platforms": Counter(), "years": [],
        "weeks": Counter(), "studios": Counter(), "tags": Counter(),
    })
    for r in rows:
        t = str(r.get("条目类型") or "未知").strip() or "未知"
        g = groups[t]
        g["count"] += 1
        if r.get("收藏类型"):
            g["collection"][r["收藏类型"]] += 1
        s = _num(r.get("BGM评分"))
        if s is not None:
            g["scores"].append(s)
        ms = _num(r.get("我的评分"))
        if ms is not None and ms > 0:
            g["my_scores"].append(ms)
        for key, bucket in (("卷数", "volumes"), ("总集数", "eps")):
            v = _num(r.get(key))
            if v is not None and v > 0:
                g[bucket].append(v)
        if r.get("平台"):
            g["platforms"][str(r["平台"]).strip()] += 1
        wd = clean_weekday(r.get("放送星期"))
        if wd:
            g["weeks"][wd] += 1
        if r.get("制作公司"):
            g["studios"][str(r["制作公司"]).strip()] += 1
        for tag in str(r.get("条目标签") or "").split("|"):
            tag = tag.strip()
            if tag:
                g["tags"][tag] += 1
        y = _year_of(r)
        if y:
            g["years"].append(y)

    out = {}
    for t, g in groups.items():
        out[t] = {
            "count": g["count"],
            "collection": dict(g["collection"]),
            "avg_bgm": round(sum(g["scores"]) / len(g["scores"]), 2) if g["scores"] else None,
            "avg_my": round(sum(g["my_scores"]) / len(g["my_scores"]), 2) if g["my_scores"] else None,
            "volumes": _stats_of(g["volumes"]),
            "eps": _stats_of(g["eps"]),
            "platforms": g["platforms"].most_common(8),
            "weeks": g["weeks"].most_common(7),
            "top_studios": g["studios"].most_common(8),
            "top_tags": g["tags"].most_common(10),
            "year_range": [min(g["years"]), max(g["years"])] if g["years"] else None,
        }
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["count"]))


def render_type_stats_markdown(rows):
    """把「其它类型专门统计」渲染成 Markdown 章节。"""
    stats = build_type_stats(rows)
    if not stats:
        return ""
    L = ["", "## 各类型专门统计", ""]
    multi = len(stats) > 1
    for t, s in stats.items():
        L.append(f"### {t}（{s['count']} 条）")
        L.append("")
        bits = []
        if s["avg_bgm"] is not None:
            bits.append(f"全站均分 **{s['avg_bgm']}**")
        if s["avg_my"] is not None:
            bits.append(f"我的均分 **{s['avg_my']}**")
        if s["collection"]:
            bits.append("收藏状态 " + "、".join(
                f"{k} {v}" for k, v in sorted(s["collection"].items(), key=lambda x: -x[1])))
        if s["year_range"]:
            bits.append(f"年代跨度 {s['year_range'][0]}–{s['year_range'][1]}")
        if bits:
            L.append("- " + " ｜ ".join(bits))
        # 卷数（书籍的核心指标）
        vol = s["volumes"]
        if vol:
            L.append(f"- **卷数**：共 {vol['total']:g} 卷，"
                     f"平均 {vol['avg']} 卷 / 部，最多 {vol['max']:g} 卷，"
                     f"中位数 {vol['median']}（{vol['count']} 条有卷数）")
        ep = s["eps"]
        if ep:
            label = "话数" if t in ("动画", "三次元") else "集数 / 曲目数"
            L.append(f"- **{label}**：共 {ep['total']:g}，平均 {ep['avg']}，"
                     f"最多 {ep['max']:g}，中位数 {ep['median']}")
        if s["platforms"]:
            L.append("- **平台**：" + "、".join(f"{k} {v}" for k, v in s["platforms"]))
        if s["weeks"]:
            L.append("- **播出星期**：" + "、".join(f"{k} {v}" for k, v in s["weeks"]))
        if s["top_studios"]:
            L.append("- **制作公司 Top**：" + "、".join(
                f"{k}（{v}）" for k, v in s["top_studios"]))
        if s["top_tags"]:
            L.append("- **高频标签**：" + "、".join(
                f"{k}（{v}）" for k, v in s["top_tags"]))
        L.append("")
    if multi:
        L.append("> 上面按条目类型分别统计：书籍看**卷数**，"
                 "游戏看**平台**，音乐看**曲目数**，动画 / 三次元看**话数**。")
        L.append("")
    return "\n".join(L)
