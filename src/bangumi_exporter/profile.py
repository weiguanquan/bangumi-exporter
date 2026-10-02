# -*- coding: utf-8 -*-
"""用户画像 + 智能推荐（纯标准库，零依赖）。

思路（尽量做成正经的数据分析，而不是拍脑袋）：
  1. 把「社区标签」当作条目的特征维度，构造用户的兴趣向量；
  2. 用 TF-IDF 给标签加权 —— TF 是出现频次，IDF 用来压制
     「TV」「日本」这类几乎每条都有的无信息标签；
  3. 用香农熵 / 基尼系数衡量口味多样性与集中度；
  4. 用 L2 归一化后的向量做余弦相似度，给候选条目打分；
  5. 若有足够的个人评分样本，用最小二乘（岭回归）拟合一个
     个人评分预测模型；样本不足时如实说明，不硬编造。
"""

import math
import time
from collections import Counter, defaultdict

from . import api
from .constants import COLLECTION_TYPE_NAME, clean_weekday

# 收藏状态对应的兴趣权重：看过权重最高，抛弃最低
COLLECTION_WEIGHT = {1: 0.55, 2: 1.0, 3: 0.9, 4: 0.3, 5: 0.1}
# Bangumi 全站平均分（用于判断用户是否偏好高分作品）
GLOBAL_AVG_SCORE = 6.5


# ---------------------------------------------------------------- 基础数学

def shannon(counts):
    """香农熵（bit）。counts 为频次序列。"""
    vals = [c for c in counts if c > 0]
    total = sum(vals)
    if total <= 0:
        return 0.0
    h = 0.0
    for c in vals:
        p = c / total
        h -= p * math.log(p, 2)
    return h


def normalized_entropy(counts):
    """归一化熵（0~1）。1 表示各种标签均匀分布，0 表示只集中在一个标签。"""
    n = len([c for c in counts if c > 0])
    if n <= 1:
        return 0.0
    return shannon(counts) / math.log(n, 2)


def gini(counts):
    """基尼系数（0~1）。越大表示越集中。"""
    vals = sorted(c for c in counts if c >= 0)
    if not vals or sum(vals) == 0:
        return 0.0
    n = len(vals)
    cum = 0.0
    for i, v in enumerate(vals, 1):
        cum += i * v
    return (2 * cum) / (n * sum(vals)) - (n + 1) / n


def cosine(a, b):
    """两个「名称->权重」稀疏向量的余弦相似度。"""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    dot = sum(w * b.get(k, 0.0) for k, w in a.items())
    if dot == 0:
        return 0.0
    na = math.sqrt(sum(w * w for w in a.values()))
    nb = math.sqrt(sum(w * w for w in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def l2_normalize(vec):
    n = math.sqrt(sum(v * v for v in vec.values()))
    if n == 0:
        return dict(vec)
    return {k: v / n for k, v in vec.items()}


def _num(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _year_of(row):
    d = str(row.get("放送日期") or "")
    if len(d) >= 4 and d[:4].isdigit():
        return int(d[:4])
    return None


def _collection_code(name):
    for code, cn in COLLECTION_TYPE_NAME.items():
        if cn == name:
            return code
    return None


def tags_of(row):
    """取一行里的社区标签列表（条目标签 优先，回退 我的标签）。"""
    raw = str(row.get("条目标签") or "").strip() or str(row.get("我的标签") or "")
    return [t.strip() for t in raw.split("|") if t.strip()]


# ---------------------------------------------------------------- 画像构建

def build_profile(rows, raw_items=None, top_n=25):
    """构建用户画像。返回可直接 JSON 序列化的字典。"""
    rows = list(rows or [])
    total = len(rows)
    if total == 0:
        return {"total": 0, "empty": True,
                "summary": "没有可用于分析的收藏数据。"}

    # ---- 1. 标签 TF-IDF ----
    tf = Counter()            # 加权词频
    df = Counter()            # 出现在多少个条目里
    for r in rows:
        code = _collection_code(r.get("收藏类型"))
        w = COLLECTION_WEIGHT.get(code, 0.5)
        tags = tags_of(r)
        for t in set(tags):
            df[t] += 1
        for t in tags:
            tf[t] += w

    idf = {t: math.log((1 + total) / (1 + d)) for t, d in df.items()}
    weighted = {t: tf[t] * idf[t] for t in tf}
    vector = l2_normalize(weighted)
    # ⚠ 排序依据用「占比」而不是 TF-IDF：
    # IDF 是「在你自己的收藏里有多罕见」，会把冷门标签顶到前面；
    # 而用户想看的「兴趣核心」是覆盖了最多收藏的题材。
    # TF-IDF 仍然保留（并用于相似度向量），只是不作为排序主轴。
    top_tags = [{"name": t, "tfidf": round(weighted[t], 4), "count": df[t],
                 "share": round(df[t] / total, 4) if total else 0.0,
                 "weight": round(vector.get(t, 0.0), 5)}
                for t in sorted(weighted, key=lambda x: (-df[x], -weighted[x]))[:top_n]]

    # ---- 2. 多样性 / 集中度 ----
    counts = list(df.values())
    entropy_bits = shannon(counts)
    diversity = {
        "distinct_tags": len(df),
        "entropy": round(entropy_bits, 3),
        "entropy_norm": round(normalized_entropy(counts), 3),
        # 困惑度：2^H（香农熵以 bit 为单位，所以底数是 2 不是 e）
        "effective_tags": round(2 ** entropy_bits, 1) if counts else 0.0,
        "gini": round(gini(counts), 3),
        "top5_share": round(
            sum(c for _, c in df.most_common(5)) / max(1, sum(counts)), 3),
    }

    # ---- 3. 年代 / 集数 / 平台 / 评分偏好 ----
    years = Counter()
    for r in rows:
        y = _year_of(r)
        if y:
            years[y] += 1
    decade = Counter()
    for y, n in years.items():
        decade[f"{(y // 10) * 10}s"] += n

    eps_vals = [e for e in (_num(r.get("总集数")) for r in rows) if e and e > 0]
    scores = [s for s in (_num(r.get("BGM评分")) for r in rows) if s is not None]
    platforms = Counter(r.get("平台") or "未知" for r in rows)
    status = Counter(r.get("收藏类型") or "未知" for r in rows)

    rated_pairs = [( _num(r.get("我的评分")), _num(r.get("BGM评分")))
                   for r in rows]
    rated_pairs = [(m, b) for m, b in rated_pairs if m is not None]

    recent = sum(n for y, n in years.items() if y >= 2020)
    years_with = sum(years.values())
    length = {
        "avg": round(sum(eps_vals) / len(eps_vals), 1) if eps_vals else 0.0,
        "median": sorted(eps_vals)[len(eps_vals) // 2] if eps_vals else 0.0,
        "single_cour_ratio": round(
            sum(1 for e in eps_vals if e <= 14) / len(eps_vals), 3) if eps_vals else 0.0,
        "long_ratio": round(
            sum(1 for e in eps_vals if e >= 50) / len(eps_vals), 3) if eps_vals else 0.0,
        "with_value": len(eps_vals),
    }
    taste_score = {
        "avg_bgm": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "global_avg": GLOBAL_AVG_SCORE,
        "high_ratio": round(
            sum(1 for s in scores if s >= 7.5) / len(scores), 3) if scores else 0.0,
        "low_ratio": round(
            sum(1 for s in scores if s < 6.0) / len(scores), 3) if scores else 0.0,
        "with_value": len(scores),
    }

    # ---- 3b. 制作公司偏好（需要数据补全提供「制作公司」列）----
    studios = Counter()
    weekday = Counter()
    for r in rows:
        s = str(r.get("制作公司") or "").strip()
        if s:
            studios[s] += 1
        w = clean_weekday(r.get("放送星期"))
        if w:
            weekday[w] += 1
    studio_list = [{"name": k, "count": v,
                    "share": round(v / total, 4) if total else 0.0}
                   for k, v in studios.most_common(top_n)]

    profile = {
        "total": total,
        "empty": False,
        "generated_at": time.time(),
        "top_tags": top_tags,
        "vector": vector,
        "diversity": diversity,
        "by_year": dict(sorted(years.items())),
        "by_decade": dict(sorted(decade.items())),
        "by_platform": dict(platforms.most_common()),
        "by_status": dict(status.most_common()),
        "by_weekday": dict(weekday.most_common()),
        "studios": studio_list,
        "recent_ratio": round(recent / years_with, 3) if years_with else 0.0,
        "length": length,
        "taste_score": taste_score,
        "rated_count": len(rated_pairs),
        "insights": [],
    }

    # ---- 4. 个人评分模型（样本足够才训练）----
    profile["rating_model"] = fit_rating_model(rows) if len(rated_pairs) >= 8 else {
        "trained": False,
        "reason": (f"个人评分样本只有 {len(rated_pairs)} 条，"
                   f"至少需要 8 条才能拟合可靠模型"),
    }

    profile["insights"] = _insights(profile, rows)
    profile["summary"] = profile["insights"][0] if profile["insights"] else ""
    return profile


def _insights(p, rows):
    out = []
    tt = p["top_tags"]
    if tt:
        names = "、".join(t["name"] for t in tt[:5])
        out.append(f"口味核心：{names} —— 出现最多的「{tt[0]['name']}」覆盖了你 "
                   f"{tt[0]['count']} 条收藏（{tt[0].get('share', 0) * 100:.0f}%）。")
    d = p["diversity"]
    if d["distinct_tags"]:
        if d["entropy_norm"] >= 0.85:
            verdict = "极其发散，属于「什么都看」型"
        elif d["entropy_norm"] >= 0.6:
            verdict = "比较均衡，有明确偏好但不排斥其它题材"
        else:
            verdict = "非常集中，是典型的「专精」型观众"
        out.append(f"多样性：{d['distinct_tags']} 个不同标签，"
                   f"归一化熵 {d['entropy_norm']}（{verdict}），"
                   f"等效标签数约 {d['effective_tags']} 个。")
    if p["recent_ratio"]:
        out.append(f"年代偏好：{p['recent_ratio'] * 100:.0f}% 的收藏是 2020 年之后的作品。")
    studios = p.get("studios") or []
    if studios:
        top = studios[:3]
        out.append("制作公司偏好：" + "、".join(
            f"{s['name']}（{s['count']} 部）" for s in top)
            + f" —— 共 {len(studios)} 家工作室，最集中的一家占 "
              f"{top[0]['share'] * 100:.0f}%。")
    wd = p.get("by_weekday") or {}
    if len(wd) >= 3:
        best = sorted(wd.items(), key=lambda kv: -kv[1])[:3]
        out.append("追番档期：" + "、".join(f"{k} {v} 部" for k, v in best)
                   + "（按条目的放送星期统计）。")
    ln = p["length"]
    if ln["with_value"]:
        out.append(f"篇幅偏好：平均 {ln['avg']} 集，"
                   f"其中 {ln['single_cour_ratio'] * 100:.0f}% 是单季番（≤14 集）。")
    ts = p["taste_score"]
    if ts["with_value"]:
        gap = ts["avg_bgm"] - GLOBAL_AVG_SCORE
        word = "高于" if gap >= 0 else "低于"
        out.append(f"口碑倾向：你收藏作品的平均 BGM 评分 {ts['avg_bgm']}，"
                   f"{word}全站平均 {GLOBAL_AVG_SCORE}（{gap:+.2f}），"
                   f"高分作品（≥7.5）占 {ts['high_ratio'] * 100:.0f}%。")
    if p["by_platform"]:
        top = list(p["by_platform"].items())[:2]
        out.append("平台分布：" + "、".join(f"{k} {v} 条" for k, v in top) + "。")
    rm = p.get("rating_model") or {}
    if rm.get("trained"):
        out.append(f"个人评分模型：已用 {rm['samples']} 条样本拟合"
                   f"（R²={rm['r2']}），可预测你会给新条目打几分。")
    elif rm.get("reason"):
        out.append(f"个人评分模型：暂未训练 —— {rm['reason']}。"
                   f"（去 Bangumi 给一些条目打分后回来重新导出即可启用）")
    return out


# ---------------------------------------------------------------- 评分模型

def _design_matrix(rows):
    """构造特征：[1, bgm_score, year, eps] + top 标签哑变量。"""
    tag_df = Counter()
    for r in rows:
        for t in set(tags_of(r)):
            tag_df[t] += 1
    feats = [t for t, _ in tag_df.most_common(10)]
    X, y = [], []
    for r in rows:
        mine = _num(r.get("我的评分"))
        if mine is None:
            continue
        bgm = _num(r.get("BGM评分")) or GLOBAL_AVG_SCORE
        year = _year_of(r) or 2015
        eps = _num(r.get("总集数")) or 12
        row = [1.0, bgm, (year - 2015) / 5.0, min(eps, 200) / 12.0]
        tags = set(tags_of(r))
        row += [1.0 if t in tags else 0.0 for t in feats]
        X.append(row)
        y.append(mine)
    return X, y, feats


def _solve(X, y, lam=1.0):
    """岭回归正规方程，高斯消元求解。零依赖。"""
    n = len(X[0])
    A = [[0.0] * (n + 1) for _ in range(n)]
    for i in range(n):
        for j in range(n):
            s = sum(row[i] * row[j] for row in X)
            A[i][j] = s + (lam if i == j and i > 0 else 0.0)
        A[i][n] = sum(row[i] * yi for row, yi in zip(X, y))
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(A[r][col]))
        if abs(A[piv][col]) < 1e-12:
            continue
        A[col], A[piv] = A[piv], A[col]
        pv = A[col][col]
        A[col] = [v / pv for v in A[col]]
        for r in range(n):
            if r != col and abs(A[r][col]) > 1e-12:
                f = A[r][col]
                A[r] = [a - f * b for a, b in zip(A[r], A[col])]
    return [A[i][n] for i in range(n)]


def fit_rating_model(rows):
    """拟合个人评分模型，返回系数与拟合优度。"""
    X, y, feats = _design_matrix(rows)
    if len(X) < 8:
        return {"trained": False, "reason": "评分样本不足（<8）"}
    try:
        beta = _solve(X, y)
    except Exception as e:
        return {"trained": False, "reason": f"拟合失败：{e}"}
    mean_y = sum(y) / len(y)
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    ss_res = 0.0
    for row, yi in zip(X, y):
        pred = sum(b * v for b, v in zip(beta, row))
        ss_res += (yi - pred) ** 2
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    names = ["截距", "BGM评分", "年代", "集数"] + [f"标签:{t}" for t in feats]
    coefs = sorted(({"name": n, "coef": round(b, 3)}
                    for n, b in zip(names, beta)),
                   key=lambda d: -abs(d["coef"]))
    return {"trained": True, "samples": len(X), "r2": round(r2, 3),
            "coefficients": coefs[:12],
            "note": "正系数表示该因素会让你打分更高"}


# ---------------------------------------------------------------- 推荐

def recommend(profile, exclude_ids=None, base=None, limit=20, log=None,
              cancel_event=None, per_tag=50, min_score=6.5, min_total=200,
              max_tags=8):
    """基于画像的条目推荐。

    候选来源：用画像权重最高的标签去检索（sort=heat，即热度排序）。

    ⚠ 不要用 sort=rank：Bangumi 把「评分人数不足、rank=0」的冷门条目
    排在前面，结果会全是没人看过的片子。热度排序 + 口碑阈值过滤，
    才能得到「热门且好评」的候选。

    打分 = 0.7 × 画像匹配度 + 0.3 × 口碑分。
    """
    exclude = {int(i) for i in (exclude_ids or []) if str(i).isdigit()}
    tags = [t["name"] for t in (profile.get("top_tags") or [])][:max_tags]
    vector = profile.get("vector") or {}
    if not tags or not vector:
        return []

    pool = {}
    for tg in tags:
        if cancel_event is not None and cancel_event.is_set():
            break
        try:
            found = api.search_subjects(tags=[tg], subject_type=2, sort="heat",
                                        limit=per_tag, base=base, log=None)
        except Exception as e:
            if log:
                log(f"  标签「{tg}」检索失败：{type(e).__name__}")
            continue
        for it in found:
            sid = it.get("id")
            if not sid or int(sid) in exclude:
                continue
            pool.setdefault(int(sid), it)
        if log:
            log(f"  标签「{tg}」-> 累计候选 {len(pool)} 条")

    cands = []
    for sid, it in pool.items():
        rating = it.get("rating") or {}
        score = _num(rating.get("score"))
        total = _num(rating.get("total")) or 0
        if score is None or score < min_score or total < min_total:
            continue
        ctags = api.tag_names(it.get("tags"))
        match = sum(vector.get(t, 0.0) for t in ctags)
        if match <= 0:
            continue
        # 除以 sqrt(标签数)，避免「标签堆得多的条目」白占便宜
        cands.append({
            "sid": sid, "it": it, "score": score,
            "rank": int(_num(rating.get("rank")) or 0),
            "total": int(total), "tags": ctags,
            "match": match / math.sqrt(max(1, len(ctags))),
        })
    if not cands:
        if log:
            log("  没有候选通过口碑阈值（可降低 min_score / min_total）")
        return []

    max_match = max(c["match"] for c in cands) or 1.0
    for c in cands:
        c["similarity"] = c["match"] / max_match
        score_norm = max(0.0, min(1.0, (c["score"] - min_score) / 2.5))
        c["final"] = 0.7 * c["similarity"] + 0.3 * score_norm
    cands.sort(key=lambda c: -c["final"])

    out = []
    for c in cands[:limit]:
        it = c["it"]
        hit = [t for t in tags if t in set(c["tags"])]
        out.append({
            "id": c["sid"],
            "name": it.get("name_cn") or it.get("name") or "",
            "name_original": it.get("name") or "",
            "date": it.get("date") or "",
            "score": c["score"],
            "rank": c["rank"] or "",
            "total": c["total"],
            "platform": it.get("platform") or "",
            "tags": c["tags"][:6],
            "similarity": round(c["similarity"], 4),
            "match_score": round(c["final"], 4),
            "url": f"https://bgm.tv/subject/{c['sid']}",
            "reason": "命中你的口味：" + "、".join(hit) if hit else "综合相似",
        })
    return out


def render_profile_markdown(profile, recommend_list=None):
    """把画像渲染成 Markdown 章节。"""
    if not profile or profile.get("empty"):
        return ""
    L = ["", "## 用户画像（TF-IDF / 熵 / 基尼系数）", ""]
    for s in profile.get("insights") or []:
        L.append(f"- {s}")
    L.append("")
    tt = profile.get("top_tags") or []
    if tt:
        L += ["### 兴趣别名 Top 25（按覆盖条数排序）", "",
              "| 标签 | 条目数 | 占收藏比 | TF-IDF（区分度） |", "|---|---|---|---|"]
        for t in tt:
            L.append(f"| {t['name']} | {t['count']} | "
                     f"{(t.get('share') or 0) * 100:.1f}% | {t['tfidf']} |")
        L.append("")
    st = profile.get("studios") or []
    if st:
        L += ["### 制作公司偏好 Top 15", "",
              "| 制作公司 | 条目数 | 占收藏比 |", "|---|---|---|"]
        for s in st[:15]:
            L.append(f"| {s['name']} | {s['count']} | "
                     f"{(s.get('share') or 0) * 100:.1f}% |")
        L.append("")
    wd = profile.get("by_weekday") or {}
    if wd:
        L += ["### 放送星期分布", "",
              "| 星期 | 条目数 |", "|---|---|"]
        for k, v in sorted(wd.items(), key=lambda kv: -kv[1]):
            L.append(f"| {k} | {v} |")
        L.append("")
    d = profile.get("diversity") or {}
    if d:
        L += ["### 多样性指标", "",
              "| 指标 | 值 | 含义 |", "|---|---|---|",
              f"| 不同标签数 | {d.get('distinct_tags')} | 兴趣覆盖的广度 |",
              f"| 香农熵 | {d.get('entropy')} | 越大越分散 |",
              f"| 归一化熵 | {d.get('entropy_norm')} | 1.0 为完全均匀 |",
              f"| 等效标签数 | {d.get('effective_tags')} | exp(熵) |",
              f"| 基尼系数 | {d.get('gini')} | 越大越集中 |",
              f"| Top5 占比 | {d.get('top5_share')} | 前 5 个标签的集中度 |",
              ""]
    rm = profile.get("rating_model") or {}
    if rm.get("trained"):
        L += ["### 个人评分模型（岭回归）", "",
              f"- 样本数：{rm['samples']}，R² = {rm['r2']}", ""]
        for c in rm.get("coefficients") or []:
            L.append(f"- `{c['name']}`：{c['coef']:+}")
        L.append("")
    elif rm.get("reason"):
        L += ["### 个人评分模型", "", f"- 未训练：{rm['reason']}", ""]

    if recommend_list:
        L += ["## 猜你喜欢（基于画像的相似度推荐）", "",
              "| 相似度 | 中文名 | 评分 | 放送 | 标签 |", "|---|---|---|---|---|"]
        for r in recommend_list:
            L.append(f"| {r['similarity']} | [{r['name']}]({r['url']}) "
                     f"| {r['score']} | {r['date']} | {'、'.join(r['tags'][:4])} |")
        L.append("")
    return "\n".join(L) + "\n"
