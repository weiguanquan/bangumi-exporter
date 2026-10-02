# -*- coding: utf-8 -*-
"""单文件可视化 HTML 报告。

全部图表都是手写内联 SVG，样式内联在 <style> 里，
不依赖任何外部库 / CDN —— 断网也能正常打开、可以直接发给别人。
"""

import html
import time

# 配色（与 Web UI 保持同一套视觉语言）
PALETTE = ["#4f8cff", "#38d39f", "#ffb454", "#ff6b81", "#a78bfa",
           "#22d3ee", "#f472b6", "#facc15", "#34d399", "#60a5fa"]

E = html.escape


def _fmt(v, digits=2):
    if v is None or v == "":
        return "-"
    if isinstance(v, float):
        return f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return str(v)


# ------------------------------------------------------------------ SVG 组件

def bar_chart(pairs, width=680, height=220, color="#4f8cff", unit="条"):
    """竖向柱状图。pairs 为 [(label, value), ...]。"""
    if not pairs:
        return "<p class='muted'>暂无数据</p>"
    pad_l, pad_b, pad_t = 44, 34, 14
    n = len(pairs)
    maxv = max(v for _, v in pairs) or 1
    plot_w = width - pad_l - 12
    plot_h = height - pad_b - pad_t
    bw = max(3.0, plot_w / n * 0.68)
    step = plot_w / n
    parts = [f"<svg viewBox='0 0 {width} {height}' class='chart' role='img'>"]
    # 网格与刻度
    for i in range(5):
        y = pad_t + plot_h * i / 4
        val = maxv * (1 - i / 4)
        parts.append(f"<line x1='{pad_l}' y1='{y:.1f}' x2='{width - 8}' y2='{y:.1f}'"
                     f" stroke='#2a3350' stroke-width='1'/>")
        parts.append(f"<text x='{pad_l - 6}' y='{y + 4:.1f}' class='axis'"
                     f" text-anchor='end'>{_fmt(round(val))}</text>")
    for i, (label, val) in enumerate(pairs):
        x = pad_l + step * i + (step - bw) / 2
        h = plot_h * (val / maxv)
        y = pad_t + plot_h - h
        parts.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{bw:.1f}' height='{max(h, 1):.1f}'"
                     f" rx='2' fill='{color}'><title>{E(str(label))}: {val} {unit}</title></rect>")
        if n <= 26:
            parts.append(f"<text x='{x + bw / 2:.1f}' y='{height - pad_b + 15}'"
                         f" class='axis' text-anchor='middle'>{E(str(label))}</text>")
        else:
            if i % 3 == 0:
                parts.append(f"<text x='{x + bw / 2:.1f}' y='{height - pad_b + 15}'"
                             f" class='axis' text-anchor='middle'>{E(str(label))}</text>")
    parts.append("</svg>")
    return "".join(parts)


def hbar_chart(pairs, width=680, row_h=24, color="#38d39f", unit="条"):
    """横向条形图，适合标签这类长文本。"""
    if not pairs:
        return "<p class='muted'>暂无数据</p>"
    maxv = max(v for _, v in pairs) or 1
    label_w = 150
    bar_w = width - label_w - 60
    height = row_h * len(pairs) + 10
    parts = [f"<svg viewBox='0 0 {width} {height}' class='chart' role='img'>"]
    for i, (label, val) in enumerate(pairs):
        y = i * row_h + 6
        w = max(2.0, bar_w * (val / maxv))
        parts.append(f"<text x='{label_w - 8}' y='{y + 13}' class='axis'"
                     f" text-anchor='end'>{E(str(label))}</text>")
        parts.append(f"<rect x='{label_w}' y='{y + 2}' width='{w:.1f}' height='{row_h - 9}'"
                     f" rx='3' fill='{color}'><title>{E(str(label))}: {val} {unit}</title></rect>")
        parts.append(f"<text x='{label_w + w + 6:.1f}' y='{y + 13}' class='axis'>{val}</text>")
    parts.append("</svg>")
    return "".join(parts)


def donut(pairs, size=200, thickness=30, unit="条"):
    """环形图，中心显示总数。"""
    if not pairs:
        return "<p class='muted'>暂无数据</p>"
    total = sum(v for _, v in pairs) or 1
    r = (size - thickness) / 2
    cx = cy = size / 2
    circ = 2 * 3.141592653589793 * r
    parts = [f"<svg viewBox='0 0 {size} {size}' class='chart donut' role='img'>",
             f"<circle cx='{cx}' cy='{cy}' r='{r:.1f}' fill='none' stroke='#222b45'"
             f" stroke-width='{thickness}'/>"]
    offset = 0.0
    for i, (label, val) in enumerate(pairs):
        frac = val / total
        seg = circ * frac
        color = PALETTE[i % len(PALETTE)]
        parts.append(
            f"<circle cx='{cx}' cy='{cy}' r='{r:.1f}' fill='none' stroke='{color}'"
            f" stroke-width='{thickness}' stroke-dasharray='{seg:.2f} {circ - seg:.2f}'"
            f" stroke-dashoffset='{-offset:.2f}'"
            f" transform='rotate(-90 {cx} {cy})'>"
            f"<title>{E(str(label))}: {val} {unit} ({frac * 100:.1f}%)</title></circle>")
        offset += seg
    parts.append(f"<text x='{cx}' y='{cy - 2}' text-anchor='middle'"
                 f" class='donut-num'>{total}</text>")
    parts.append(f"<text x='{cx}' y='{cy + 18}' text-anchor='middle'"
                 f" class='donut-lbl'>总计</text></svg>")
    legend = ["<ul class='legend'>"]
    for i, (label, val) in enumerate(pairs):
        color = PALETTE[i % len(PALETTE)]
        pct = val / total * 100
        legend.append(f"<li><span class='dot' style='background:{color}'></span>"
                      f"{E(str(label))} <b>{val}</b> <span class='muted'>{pct:.1f}%</span></li>")
    legend.append("</ul>")
    return f"<div class='donut-wrap'>{''.join(parts)}{''.join(legend)}</div>"


# ------------------------------------------------------------------ 主入口

def _studio_html(profile):
    """制作公司偏好 + 放送星期分布（来自数据补全）。"""
    st = (profile or {}).get("studios") or []
    wd = (profile or {}).get("by_weekday") or {}
    if not st and not wd:
        return ""
    out = []
    if st:
        out.append("<h3>制作公司偏好 Top 12</h3>")
        out.append(hbar_chart([(s["name"], s["count"]) for s in st[:12]],
                              color='#f7768e'))
    if wd:
        out.append("<h3>放送星期分布</h3>")
        order = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        pairs = [(k, wd[k]) for k in order if k in wd]
        pairs += [(k, v) for k, v in wd.items() if k not in order]
        out.append(bar_chart(pairs, color='#9ece6a'))
    return "".join(out)


def build_html_report(rows, charts=None, profile=None, recommend=None,                     diagnosis=None, user=None, compare=None, vs_global=None,
                     title=None):
    """生成完整报告 HTML 字符串。"""
    rows = list(rows or [])
    charts = charts or {}
    profile = profile or {}
    recommend = recommend or []
    user = user or {}
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    nick = user.get("nickname") or user.get("username") or "未知用户"
    uid = user.get("id") or ""

    # ---- 各类型专门统计（书籍卷数 / 游戏平台 / 音乐曲目数）----
    type_html = ""
    try:
        from .stats import build_type_stats
        tstats = build_type_stats(rows)
        if tstats:
            cards = []
            for tname, s in tstats.items():
                bits = [f"<b>{s['count']}</b> 条"]
                if s.get("avg_bgm") is not None:
                    bits.append(f"全站均分 <b>{s['avg_bgm']}</b>")
                if s.get("avg_my") is not None:
                    bits.append(f"我的均分 <b>{s['avg_my']}</b>")
                vol = s.get("volumes")
                if vol:
                    bits.append(f"共 <b>{vol['total']:g}</b> 卷，"
                                f"平均 {vol['avg']} 卷/部")
                ep = s.get("eps")
                if ep:
                    label = "话数" if tname in ("动画", "三次元") else "集数/曲目"
                    bits.append(f"共 <b>{ep['total']:g}</b> {label}，平均 {ep['avg']}")
                if s.get("platforms"):
                    bits.append("平台：" + "、".join(
                        f"{html.escape(str(k))} {v}" for k, v in s["platforms"][:5]))
                if s.get("weeks"):
                    bits.append("播出：" + "、".join(
                        f"{html.escape(str(k))} {v}" for k, v in s["weeks"][:4]))
                if s.get("top_studios"):
                    bits.append("制作：" + "、".join(
                        f"{html.escape(str(k))} {v}" for k, v in s["top_studios"][:5]))
                cards.append(
                    f"<div class='tcard'><h3>{html.escape(str(tname))}</h3>"
                    f"<div class='tmeta'>{' ｜ '.join(bits)}</div></div>")
            type_html = ("<section><h2>📚 各类型专门统计</h2>"
                         "<div class='tgrid'>" + "".join(cards) + "</div>"
                         "<p class='muted'>书籍看卷数，游戏看平台，"
                         "音乐看曲目数，动画 / 三次元看话数。</p></section>")
    except Exception:
        type_html = ""

    # ---- KPI ----
    total = len(rows)
    status = charts.get("by_collection_type") or {}
    rating = charts.get("rating") or {}
    tags = profile.get("top_tags") or []
    comp = charts.get("completion") or {}
    kpis = [
        ("总条目", total),
        ("看过", status.get("看过", 0)),
        ("在看", status.get("在看", 0)),
        ("想看", status.get("想看", 0)),
        ("平均 BGM 评分", _fmt(charts.get("avg_bgm"))),
        ("我的平均分", _fmt(charts.get("avg_mine"))),
        ("兴趣标签数", (profile.get("diversity") or {}).get("distinct_tags", 0)),
        ("等效标签数", (profile.get("diversity") or {}).get("effective_tags", 0)),
    ]
    kpi_html = "".join(
        f"<div class='kpi'><div class='kpi-v'>{_fmt(v)}</div>"
        f"<div class='kpi-k'>{E(k)}</div></div>" for k, v in kpis)

    # ---- 图表 ----
    def _pairs(d, top=None):
        items = list((d or {}).items())
        return items[:top] if top else items

    year_pairs = [(str(k), v) for k, v in _pairs(charts.get("by_year"))]
    quarter = [(str(k).replace("20", "", 1), v)
               for k, v in list((charts.get("by_quarter") or {}).items())[-16:]]
    plat = [(str(k), v) for k, v in _pairs(charts.get("by_platform"))]
    tag_pairs = [(t["name"], t["count"]) for t in tags[:15]]
    bgm_dist = [(str(k), v) for k, v in _pairs(charts.get("bgm_score_dist"))]
    my_dist = [(str(k), v) for k, v in _pairs(charts.get("my_rate_dist"))]

    # ---- 画像 ----
    prof_html = ""
    if profile and not profile.get("empty"):
        ins = "".join(f"<li>{E(s)}</li>" for s in (profile.get("insights") or []))
        d = profile.get("diversity") or {}
        prof_html = f"""
<section>
  <h2>🧠 用户画像</h2>
  <ul class="insights">{ins}</ul>
  <div class="metrics">
    <div class="metric"><span>香农熵</span><b>{_fmt(d.get('entropy'))}</b></div>
    <div class="metric"><span>归一化熵</span><b>{_fmt(d.get('entropy_norm'))}</b></div>
    <div class="metric"><span>基尼系数</span><b>{_fmt(d.get('gini'))}</b></div>
    <div class="metric"><span>Top5 集中度</span><b>{_fmt((d.get('top5_share') or 0) * 100, 1)}%</b></div>
    <div class="metric"><span>平均集数</span><b>{_fmt((profile.get('length') or {}).get('avg'))}</b></div>
    <div class="metric"><span>单季番占比</span><b>{_fmt(((profile.get('length') or {}).get('single_cour_ratio') or 0) * 100, 0)}%</b></div>
  </div>
  <h3>兴趣标签 Top 15（按覆盖条数）</h3>
  {hbar_chart(tag_pairs)}
  {_studio_html(profile)}
</section>"""

    # ---- 推荐 ----
    rec_html = ""
    if recommend:
        cards = []
        for r in recommend:
            cards.append(f"""<a class="rec" href="{E(r['url'])}" target="_blank" rel="noreferrer">
  <div class="rec-top"><span class="rec-name">{E(r['name'])}</span>
    <span class="rec-score">{_fmt(r['score'])}</span></div>
  <div class="rec-meta">{E(str(r.get('date') or ''))} · {E(str(r.get('platform') or ''))}
    · 匹配度 {_fmt((r.get('match_score') or 0) * 100, 0)}%</div>
  <div class="rec-tags">{''.join(f'<i>{E(t)}</i>' for t in (r.get('tags') or [])[:5])}</div>
</a>""")
        rec_html = f"""
<section>
  <h2>✨ 猜你喜欢（基于画像相似度）</h2>
  <p class="muted">候选来自热度排序检索，并按口碑（评分 ≥ 6.5、评分人数 ≥ 200）过滤；
  得分为 0.7×画像匹配度 + 0.3×口碑分。</p>
  <div class="recs">{''.join(cards)}</div>
</section>"""

    # ---- 体检 ----
    diag_html = ""
    if diagnosis and diagnosis.get("columns"):
        icon = {"ok": "✅", "partial": "◐", "empty": "⬜", "all_zero": "0️⃣"}
        trs = "".join(
            f"<tr><td>{icon.get(c['status'], '')} {E(c['column'])}</td>"
            f"<td class='num'>{c['filled']}/{c['total']}</td>"
            f"<td><code>{E(c['source'])}</code></td><td>{E(c['explain'])}</td></tr>"
            for c in diagnosis["columns"])
        diag_html = f"""
<section>
  <h2>🩺 数据体检</h2>
  <p>{E(diagnosis.get('summary') or '')}</p>
  <table class="tbl"><thead><tr><th>列</th><th>填充</th><th>来源</th><th>说明</th></tr></thead>
  <tbody>{trs}</tbody></table>
</section>"""

    # ---- 变化对比 ----
    diff_html = ""
    if compare and compare.get("has_changes") is not None:
        def _names(lst, n=12):
            return "".join(f"<li>{E(x.get('中文名') or x.get('原名') or '')}</li>"
                           for x in lst[:n])
        diff_html = f"""
<section>
  <h2>📈 收藏变化</h2>
  <p class="muted">对比 {E(str((compare.get('old') or {}).get('saved_at_str') or ''))}
   → {E(str((compare.get('new') or {}).get('saved_at_str') or ''))}</p>
  <div class="metrics">
    <div class="metric"><span>新增</span><b>{len(compare.get('added') or [])}</b></div>
    <div class="metric"><span>删除</span><b>{len(compare.get('removed') or [])}</b></div>
    <div class="metric"><span>修改</span><b>{len(compare.get('changed') or [])}</b></div>
  </div>
  {('<h3>新增</h3><ul>' + _names(compare.get('added') or []) + '</ul>') if compare.get('added') else ''}
  {('<h3>删除</h3><ul>' + _names(compare.get('removed') or []) + '</ul>') if compare.get('removed') else ''}
</section>"""

    # ---- 全站对比 ----
    gcomp_html = ""
    if vs_global and vs_global.get("total"):
        g = vs_global
        ins = "".join(f"<li>{E(s)}</li>" for s in (g.get("insights") or []))
        gh = g.get("global_hist") or {}
        gh_total = g.get("global_hist_total") or 0
        hist_pairs = [(f"{k}分", gh.get(k, 0)) for k in
                      sorted(gh.keys(), key=lambda x: int(x))]
        met = [
            ("你收藏的等权全站均分", g.get("collection_avg_global")),
            ("全站打分人数", gh_total),
            ("按人数加权均分", g.get("global_mean")),
            ("你的平均分", g.get("my_mean") if g.get("my_mean") else "未打分"),
            ("公认高分(≥7.5)", g.get("high_count")),
            ("低于 6.0", g.get("low_count")),
        ]
        met_html = "".join(
            f"<div class='metric'><span>{E(k)}</span><b>{_fmt(v)}</b></div>" for k, v in met)
        rows_html = ""
        if g.get("rated"):
            rows_html = "<h3>我 vs 大众 差异最大的条目</h3><table class='tbl'><thead><tr>" \
                "<th>条目</th><th class='num'>我的评分</th><th class='num'>全站平均</th>" \
                "<th class='num'>差值</th><th class='num'>我的分位</th></tr></thead><tbody>"
            for x in g["rated"][:15]:
                pct = f"{x['percentile']}%" if x.get("percentile") is not None else "-"
                rows_html += (f"<tr><td>{E(x['name'])}</td><td class='num'>{x['my']}</td>"
                              f"<td class='num'>{x['global']}</td>"
                              f"<td class='num'>{x['delta']:+}</td>"
                              f"<td class='num'>{pct}</td></tr>")
            rows_html += "</tbody></table>"
        else:
            hi = sorted([i for i in (g.get("items") or [])
                         if isinstance(i.get("global"), (int, float))],
                        key=lambda x: -x["global"])[:15]
            if hi:
                rows_html = "<h3>你收藏里全站口碑最高的条目</h3><table class='tbl'><thead><tr>" \
                    "<th>条目</th><th class='num'>全站平均</th><th class='num'>排名</th>" \
                    "<th class='num'>评分人数</th></tr></thead><tbody>"
                for x in hi:
                    rows_html += (f"<tr><td>{E(x['name'])}</td>"
                                  f"<td class='num'>{x['global']}</td>"
                                  f"<td class='num'>{E(str(x['rank'] or '-'))}</td>"
                                  f"<td class='num'>{x['total']}</td></tr>")
                rows_html += "</tbody></table>"
        gcomp_html = f"""
<section>
  <h2>🌐 全站对比（我的口味 vs 大众）</h2>
  <ul class="insights">{ins}</ul>
  <div class="metrics">{met_html}</div>
  <h3>你收藏条目的全站评分分布（{gh_total} 次打分）</h3>
  {bar_chart(hist_pairs, color='#f472b6', unit='人')}
  {rows_html}
</section>"""

    # ---- 明细表 ----
    from .constants import FIELD_NAMES
    show = [c for c in FIELD_NAMES if c not in ("条目标签",)]
    head = "".join(f"<th>{E(c)}</th>" for c in show)
    body = []
    for r in rows:
        tds = []
        for c in show:
            v = r.get(c, "")
            if c == "条目链接":
                tds.append(f"<td><a href='{E(str(v))}' target='_blank' rel='noreferrer'>"
                           f"bgm</a></td>")
            elif c == "条目ID":
                tds.append(f"<td class='num'>{E(str(v))}</td>")
            else:
                tds.append(f"<td>{E(str(v))}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title or f'{nick} 的 Bangumi 收藏报告')}</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; padding:28px 20px 60px; background:#0f1424; color:#e8ecf8;
  font:15px/1.65 -apple-system,'Segoe UI','Microsoft YaHei',sans-serif; }}
.wrap {{ max-width:1080px; margin:0 auto; }}
header h1 {{ margin:0 0 6px; font-size:26px; }}
.muted {{ color:#8f9bbd; }}
section {{ background:#161d33; border:1px solid #242e4d; border-radius:14px;
  padding:20px 22px; margin:18px 0; }}
h2 {{ margin:0 0 14px; font-size:19px; }}
h3 {{ margin:18px 0 8px; font-size:15px; color:#b9c4e4; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin:18px 0; }}
.kpi {{ background:#161d33; border:1px solid #242e4d; border-radius:12px; padding:14px 16px; }}
.kpi-v {{ font-size:22px; font-weight:650; color:#7fb0ff; }}
.kpi-k {{ font-size:12px; color:#8f9bbd; margin-top:2px; }}
.tgrid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:14px; }}
.tcard {{ background:#161d33; border:1px solid #242e4d; border-radius:12px; padding:14px 16px; }}
.tcard h3 {{ margin:0 0 8px; font-size:15px; color:#c9d6ff; }}
.tmeta {{ font-size:13px; color:#a9b4d0; line-height:1.9; }}
.tmeta b {{ color:#7fb0ff; }}
.chart {{ width:100%; height:auto; display:block; }}
.axis {{ fill:#8f9bbd; font-size:11px; }}
.donut-num {{ fill:#e8ecf8; font-size:26px; font-weight:700; }}
.donut-lbl {{ fill:#8f9bbd; font-size:12px; }}
.donut-wrap {{ display:flex; align-items:center; gap:26px; flex-wrap:wrap; }}
.donut {{ width:210px; flex:0 0 auto; }}
.legend {{ list-style:none; margin:0; padding:0; font-size:13.5px; }}
.legend li {{ margin:5px 0; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:7px; }}
.insights {{ margin:0 0 6px; padding-left:20px; }}
.insights li {{ margin:6px 0; }}
.metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:12px 0; }}
.metric {{ background:#101731; border:1px solid #242e4d; border-radius:10px; padding:10px 13px; }}
.metric span {{ display:block; font-size:12px; color:#8f9bbd; }}
.metric b {{ font-size:17px; }}
.recs {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(255px,1fr)); gap:12px; }}
.rec {{ display:block; text-decoration:none; color:inherit; background:#101731;
  border:1px solid #242e4d; border-radius:11px; padding:13px 15px; transition:.15s; }}
.rec:hover {{ border-color:#4f8cff; transform:translateY(-2px); }}
.rec-top {{ display:flex; justify-content:space-between; gap:10px; align-items:baseline; }}
.rec-name {{ font-weight:620; }}
.rec-score {{ color:#38d39f; font-weight:700; }}
.rec-meta {{ font-size:12px; color:#8f9bbd; margin:5px 0 7px; }}
.rec-tags i {{ font-style:normal; font-size:11.5px; background:#1d2742; color:#9fb0d8;
  border-radius:20px; padding:2px 8px; margin:0 4px 4px 0; display:inline-block; }}
.tbl {{ width:100%; border-collapse:collapse; font-size:13px; }}
.tbl th, .tbl td {{ border-bottom:1px solid #242e4d; padding:7px 9px; text-align:left;
  vertical-align:top; }}
.tbl th {{ color:#8f9bbd; font-weight:600; position:sticky; top:0; background:#161d33; }}
.tbl td.num, .tbl th.num {{ text-align:right; }}
details summary {{ cursor:pointer; color:#7fb0ff; }}
code {{ background:#101731; padding:1px 5px; border-radius:4px; font-size:12px; }}
.tablewrap {{ max-height:620px; overflow:auto; }}
footer {{ text-align:center; color:#6b7699; font-size:12.5px; margin-top:28px; }}
</style></head>
<body><div class="wrap">
<header>
  <h1>{E(nick)} 的 Bangumi 收藏报告</h1>
  <div class="muted">UID {E(str(uid))} · 生成于 {now} · 共 {total} 条</div>
</header>
<div class="kpis">{kpi_html}</div>

<section>
  <h2>📊 收藏构成</h2>
  {donut(_pairs(charts.get('by_collection_type')))}
</section>

<section>
  <h2>🗓 放送年份分布</h2>
  {bar_chart(year_pairs)}
  <h3>最近 16 个季度</h3>
  {bar_chart(quarter, color='#a78bfa')}
</section>

<section>
  <h2>📺 平台分布</h2>
  {hbar_chart(plat, color='#ffb454')}
</section>

{type_html}

<section>
  <h2>⭐ 评分分布</h2>
  <h3>BGM 全站评分</h3>
  {bar_chart(bgm_dist, color='#4f8cff')}
  <h3>我的评分</h3>
  {bar_chart(my_dist, color='#38d39f') if my_dist else '<p class="muted">你还没有给任何条目打分。</p>'}
</section>
{prof_html}
{gcomp_html}
{rec_html}
{diag_html}
{diff_html}

<section>
  <h2>📋 全部条目（{total}）</h2>
  <div class="tablewrap"><table class="tbl">
    <thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody>
  </table></div>
</section>

<footer>由 bangumi_exporter 生成 · 纯离线单文件报告（图表为内联 SVG）</footer>
</div></body></html>
"""
