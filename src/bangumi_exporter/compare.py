# -*- coding: utf-8 -*-
"""全站对比：我的评分 vs 大众分布。

数据来源是条目详情里的 `rating.count`（1~10 分各有多少人打分），
这份直方图会被一并缓存进 .rating_cache.json，所以完全离线可用。

即使用户自己没打过分（很常见），也能回答有价值的两个问题：
  1. 我收藏的这批作品，在全站口碑里处于什么位置？
  2. 全站的分数分布长什么样，我的口味偏好哪一段？
"""

from .profile import GLOBAL_AVG_SCORE

BUCKETS = [str(i) for i in range(1, 11)]


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def _hist_from_counts(count):
    """把 API 的 {"1":4,"2":0,...} 转成 {int: n}。"""
    out = {}
    if not isinstance(count, dict):
        return out
    for k, v in count.items():
        try:
            out[int(float(k))] = int(v or 0)
        except (TypeError, ValueError):
            continue
    return out


def _percentile(hist, score):
    """score 在该直方图里的百分位（0~100，越大越靠前）。

    hist 的键可能是字符串（来自 JSON），这里统一转成 int 再比较，
    否则 str < int 会直接抛 TypeError。
    """
    total = sum(hist.values())
    if not total or score is None:
        return None
    try:
        buckets = {int(float(k)): v for k, v in hist.items()}
    except (TypeError, ValueError):
        return None
    below = sum(n for s, n in buckets.items() if s < score)
    equal = buckets.get(int(round(score)), 0)
    return round((below + equal / 2.0) / total * 100, 1)


def _weighted_mean(hist):
    total = sum(hist.values())
    if not total:
        return None
    return round(sum(s * n for s, n in hist.items()) / total, 3)


def build_compare(rows, rating_get=None, global_avg=GLOBAL_AVG_SCORE):
    """构建全站对比数据。

    rows       : 导出行
    rating_get : 可调用对象，rating_get(subject_id) -> {"rating": {...}} 或 None
    """
    rows = list(rows or [])
    agg = {i: 0 for i in range(1, 11)}       # 全站打分人数合计
    items = []                               # 每条目的全站口径
    my_hist = {i: 0 for i in range(1, 11)}   # 我的评分分布
    rated = []
    my_sum = 0.0
    my_n = 0

    for r in rows:
        sid = r.get("条目ID")
        my = _num(r.get("我的评分"))
        bgm = _num(r.get("BGM评分"))
        rank = r.get("排名")
        total = _num(r.get("评分人数")) or 0

        if my and my > 0:
            my_hist[int(my)] = my_hist.get(int(my), 0) + 1
            my_sum += my
            my_n += 1

        hist = {}
        if rating_get is not None and sid:
            try:
                cached = rating_get(sid) or {}
                hist = _hist_from_counts((cached.get("rating") or {}).get("count"))
            except Exception:
                hist = {}
        for s, n in hist.items():
            agg[s] = agg.get(s, 0) + n

        gmean = _weighted_mean(hist) if hist else bgm
        entry = {
            "id": sid,
            "name": r.get("中文名") or r.get("原名") or "",
            "my": my or "",
            "global": gmean if gmean is not None else "",
            "total": int(total),
            "rank": rank or "",
            "percentile": _percentile(hist, my) if my else None,
            "delta": round(my - gmean, 2) if (my and gmean) else "",
            "has_hist": bool(hist),
        }
        items.append(entry)
        if my and gmean:
            rated.append(entry)

    agg_total = sum(agg.values())
    global_mean = _weighted_mean(agg) if agg_total else None
    per_item_global = [i["global"] for i in items if isinstance(i["global"], (int, float))]
    coll_avg_global = round(sum(per_item_global) / len(per_item_global), 3) if per_item_global else None

    rated.sort(key=lambda x: -abs(x["delta"]) if isinstance(x["delta"], (int, float)) else 0)

    above = sum(1 for x in rated if isinstance(x["delta"], (int, float)) and x["delta"] > 0)
    below = sum(1 for x in rated if isinstance(x["delta"], (int, float)) and x["delta"] < 0)
    equal = sum(1 for x in rated if isinstance(x["delta"], (int, float)) and x["delta"] == 0)

    my_mean = round(my_sum / my_n, 3) if my_n else None
    delta = round(my_mean - global_mean, 3) if (my_mean and global_mean) else None

    # 我的平均分在「全站平均分」群体里的位置
    my_mean_pct = None
    if my_mean and per_item_global:
        my_mean_pct = round(
            sum(1 for g in per_item_global if g < my_mean) / len(per_item_global) * 100, 1)

    # 我收藏的作品在全站的分位：有多少条属于「公认高分」
    high = sum(1 for g in per_item_global if g >= 7.5)
    low = sum(1 for g in per_item_global if g < 6.0)

    insights = []
    if coll_avg_global:
        diff = coll_avg_global - global_avg
        who = "高于" if diff > 0 else ("低于" if diff < 0 else "等于")
        insights.append(
            f"你收藏的 {len(per_item_global)} 部动画，等权全站平均分 {coll_avg_global}，"
            f"{who}全站基准 {global_avg}（{diff:+.2f}）——说明你的口味整体偏好评")
    if global_mean:
        insights.append(
            f"按打分人数加权后全站平均 {global_mean}，"
            f"（更热门的作品分更高，会把加权值拉高，与上一条口径不同）")
    if per_item_global:
        insights.append(
            f"其中 {high} 部是全站公认高分（≥7.5），{low} 部低于 6.0")
    if my_mean and global_mean:
        who = "更宽容" if my_mean > global_mean else "更严格"
        insights.append(
            f"你的平均分 {my_mean} 比大众平均 {global_mean} 高 {delta:+.2f}，"
            f"你的打分{who}")
        insights.append(
            f"在 {len(rated)} 部你打过分的作品里，"
            f"{above} 部高于大众、{below} 部低于大众、{equal} 部持平")
    else:
        insights.append(
            "你还没有给任何条目打分，所以无法做「我的评分 vs 大众」的直接对比；"
            "下面是全站口径的分布，可用来判断你的口味偏好哪一段。")

    return {
        "total": len(rows),
        "with_hist": sum(1 for i in items if i["has_hist"]),
        "global_hist": {str(k): v for k, v in sorted(agg.items())},
        "global_hist_total": agg_total,
        "global_mean": global_mean,
        "global_avg_baseline": global_avg,
        "collection_avg_global": coll_avg_global,
        "my_hist": {str(k): v for k, v in sorted(my_hist.items())},
        "my_mean": my_mean,
        "my_rated_count": my_n,
        "delta": delta,
        "above": above, "below": below, "equal": equal,
        "my_mean_percentile": my_mean_pct,
        "high_count": high, "low_count": low,
        "items": items,
        "rated": rated,
        "insights": insights,
        "summary": "；".join(insights[:3]),
    }


def render_compare_markdown(compare, top=15):
    """把全站对比渲染成 Markdown。"""
    if not compare or not compare.get("total"):
        return ""
    L = ["", "## 全站对比（我的口味 vs 大众）", ""]
    for s in compare.get("insights") or []:
        L.append(f"- {s}")

    gh = compare.get("global_hist") or {}
    total = compare.get("global_hist_total") or 0
    if total:
        L += ["", "### 你收藏条目的全站评分分布", "",
              "| 分数 | 打分人数 | 占比 |", "|---|---|---|"]
        for k in BUCKETS:
            n = gh.get(k, 0)
            bar = "█" * int(round(n / max(1, max(gh.values())) * 20)) if n else ""
            L.append(f"| {k} 分 | {n} | {n / total * 100:.1f}% {bar} |")

    rated = compare.get("rated") or []
    if rated:
        L += ["", f"### 我 vs 大众 差异最大的 Top {min(top, len(rated))}", "",
              "| 条目 | 我的评分 | 全站平均 | 差值 | 我的分位 |", "|---|---|---|---|---|"]
        for x in rated[:top]:
            pct = f"{x['percentile']}%" if x.get("percentile") is not None else "-"
            L.append(f"| {x['name']} | {x['my']} | {x['global']} | "
                     f"{x['delta']:+} | {pct} |")
    else:
        hi = sorted([i for i in (compare.get("items") or [])
                     if isinstance(i.get("global"), (int, float))],
                    key=lambda x: -x["global"])[:top]
        if hi:
            L += ["", f"### 你收藏里全站口碑最高的 {len(hi)} 部", "",
                  "| 条目 | 全站平均 | 排名 | 评分人数 |", "|---|---|---|---|"]
            for x in hi:
                L.append(f"| {x['name']} | {x['global']} | {x['rank'] or '-'} | {x['total']} |")
    return "\n".join(L) + "\n"
