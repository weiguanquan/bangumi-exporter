# -*- coding: utf-8 -*-
"""统一命令行入口。

用法：
  python -m bangumi_exporter.cli                     # 启动 Web 界面（默认）
  python -m bangumi_exporter.cli --serve             # 同上
  python -m bangumi_exporter.cli --gui               # 原生 tkinter 图形界面
  python -m bangumi_exporter.cli --type all -f all   # 纯命令行导出
  python -m bangumi_exporter.cli --type anime,game -f csv,excel --token xxx
"""

import argparse
import sys

from .config import BASE_DIR, DEFAULT_OUTPUT, load_config, resolve_token, save_config
from .constants import APP_NAME, APP_VERSION
from .engine import build_cli_namespace, run_export


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="bangumi-exporter",
        description=f"{APP_NAME} v{APP_VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "模式：不带导出参数时默认启动 Web 界面。\n"
            "Token 优先级：--token > 环境变量 BANGUMI_TOKEN > config.json。\n"
            "条目类型: anime(动画) book(书籍) music(音乐) game(游戏) real(三次元) all(全部)。\n"
            "导出格式: csv json excel(xlsx) markdown(md) html all。\n"
            "收藏状态: 1想看 2看过 3在看 4搁置 5抛弃，逗号分隔，默认全部。\n"
            "\n"
            "数据源：程序会自动并发探测所有官方源与镜像（含 Kazumi 同款\n"
            "api.bgmapi.com），按实测延迟与鉴权能力自动选最快的那个；\n"
            "坏源会被熔断冷却，不再拖慢每次导出。也可用 --source 手动指定。\n"
            "\n"
            "增量导出：首次导出会建立完整数据缓存（输出/.data_cache.json），\n"
            "之后用 --incremental 只导出新增/有变化的条目；--since 按更新时间\n"
            "过滤；--offline 可完全离线用缓存重新生成文件。\n"
            "\n"
            "示例：\n"
            "  bangumi-exporter --list-sources\n"
            "  bangumi-exporter --type all -f all -o 输出/备份\n"
            "  bangumi-exporter --type anime -f csv --incremental\n"
            "  bangumi-exporter --type all --since 2026-01-01 -f excel\n"
            "  bangumi-exporter --offline -f markdown -o 输出/离线"
        ),
    )
    p.add_argument("--serve", action="store_true", help="启动 Web 界面（默认行为）")
    p.add_argument("--no-browser", action="store_true", help="启动 Web 时不自动打开浏览器")
    p.add_argument("--gui", action="store_true", help="启动原生 tkinter 图形界面")
    p.add_argument("-t", "--token", help="Bangumi Access Token（优先级最高）")
    p.add_argument("--save-token", action="store_true", help="把 --token 保存到 config.json")
    p.add_argument("-o", "--output", default=None,
                   help=f"输出文件基础名（不含扩展名），默认 {DEFAULT_OUTPUT}")
    p.add_argument("--type", "--subject-type", dest="subject_type", default=None,
                   help="条目类型，逗号分隔或 all，默认取配置或 anime")
    p.add_argument("-f", "--format", dest="formats", default=None,
                   help="导出格式，逗号分隔或 all，默认取配置或 csv")
    p.add_argument("--status", dest="collection_types", default="",
                   help="收藏状态过滤，如 2,3 或 看过,在看，默认全部")
    p.add_argument("--workers", type=int, default=6, help="补取评分并发数，默认 6")
    p.add_argument("--proxy", default=None,
                   help="HTTP 代理，例如 http://127.0.0.1:7890")
    p.add_argument("--api-base", default=None, help="自定义 API 镜像地址，优先尝试")
    p.add_argument("--no-stats", action="store_true", help="不生成统计报告")

    # ---- 数据源 ----
    src = p.add_argument_group("数据源")
    src.add_argument("--source", default="",
                     help="指定数据源根地址（默认自动选最快的可用源）")
    src.add_argument("--list-sources", action="store_true",
                     help="并发探测并列出所有数据源的可用性与延迟后退出")
    src.add_argument("--probe-sources", action="store_true",
                     help="强制重新探测所有数据源（忽略缓存的健康状态）")
    src.add_argument("--username", default="",
                     help="直接指定 Bangumi 用户名，跳过 /v0/me 身份识别")

    # ---- 高级导出 ----
    adv = p.add_argument_group("高级导出")
    adv.add_argument("--since", default="",
                     help="只导出更新时间在该时间之后的条目，"
                          "支持 2026-01-01 / 2026-01-01T00:00:00 / 7d / 24h")
    adv.add_argument("--incremental", action="store_true",
                     help="只导出与上次缓存相比 新增/有变化 的条目")
    adv.add_argument("--offline", action="store_true",
                     help="离线模式：不联网，用本地缓存重新生成导出文件")
    adv.add_argument("--no-details", dest="enrich_details", action="store_false",
                     help="不补取条目详情（平台等）。可显著加快速度，"
                          "但「平台」列会为空")
    p.set_defaults(enrich_details=True)

    # ---- 高级分析（v3.2） ----
    ana = p.add_argument_group("高级分析")
    ana.add_argument("--no-profile", dest="profile", action="store_false",
                     help="不生成用户画像（默认生成）")
    ana.add_argument("--recommend", action="store_true",
                     help="生成智能推荐（需要联网检索，耗时约 10-20 秒）")
    ana.add_argument("--recommend-limit", type=int, default=20,
                     help="推荐条数，默认 20")
    ana.add_argument("--report", action="store_true",
                     help="额外生成单文件可视化 HTML 报告（内联 SVG 图表）")
    ana.add_argument("--archive", action="store_true",
                     help="把本次结果归档为快照，供以后对比收藏变化")
    ana.add_argument("--supplement", action="store_true",
                     help="补全简介 / 制作公司 / staff / 声优 / 分集 / 播出星期 / 卷数"
                          "（每个条目 4 次请求，首次较慢，之后走缓存）")
    ana.add_argument("--supplement-limit", type=int, default=0, metavar="N",
                     help="只补全前 N 个条目（调试用，0 = 全部）")
    ana.add_argument("--history", action="store_true",
                     help="列出所有历史快照并对比最近两份后退出")
    ana.add_argument("--compare", nargs=2, metavar=("旧快照", "新快照"),
                     help="对比指定的两份快照后退出")
    ana.add_argument("--accounts", action="store_true",
                     help="列出所有已保存的账号后退出")
    ana.add_argument("--backup", metavar="目录",
                     help="把配置与状态备份到该目录后退出")
    ana.add_argument("--restore", metavar="文件",
                     help="从备份文件恢复配置与状态后退出")
    ana.add_argument("--watch", metavar="间隔",
                     help="定时导出，例如 30m / 6h / 1d（按收藏更新时间判断变化）")
    ana.add_argument("--account", metavar="名称",
                     help="把本次使用的 Token 保存为指定名称的账号（多账号）")
    ana.add_argument("--use-account", metavar="名称",
                     help="切换当前账号后再导出")
    ana.add_argument("--del-account", metavar="名称",
                     help="删除指定账号后退出")
    p.set_defaults(profile=True)

    p.add_argument("--version", action="version", version=f"{APP_NAME} v{APP_VERSION}")
    return p.parse_args(argv)


def is_export_mode(args):
    """只要指定了任一导出相关参数，就走命令行导出而非 Web。

    注意：不带任何参数运行 = 启动 Web 界面（与 --serve 相同），
    这是刻意设计，但很容易误解，所以这里把「任何与导出有关的开关」
    （含 --probe-sources / --username 等）全部算作导出模式。
    """
    return any([args.token, args.output, args.subject_type,
                args.formats, args.collection_types, args.no_stats,
                args.since, args.incremental, args.offline,
                args.source, args.username, args.list_sources,
                getattr(args, "probe_sources", False),
                getattr(args, "report", False),
                getattr(args, "recommend", False),
                getattr(args, "archive", False),
                getattr(args, "supplement", False),
                getattr(args, "account", None),
                getattr(args, "use_account", None)])


def cmd_serve(args):
    from .server import serve
    return serve(open_browser=not args.no_browser)


def cmd_list_sources(args):
    """并发探测所有数据源并打印可用性与延迟。"""
    from . import api
    from .sources import get_manager

    cfg = load_config()
    token = resolve_token(getattr(args, "token", None), cfg)
    if token:
        api.set_token(token)
    proxy = getattr(args, "proxy", None) or cfg.get("proxy", "")
    if proxy:
        api.set_proxy(proxy, log=print)

    manager = get_manager(state_path=BASE_DIR / "输出" / ".sources.json",
                          log=None)
    print(f"正在并发探测数据源（{APP_NAME} v{APP_VERSION}）...\n")
    manager.probe(token=token or None)
    rows = manager.snapshot()
    print(f"\n{'数据源':<22} {'地址':<28} {'状态':<8} {'延迟':<8} {'鉴权':<10} 说明")
    print("-" * 108)
    for s in rows:
        if s["ok"]:
            status = "可用"
        elif s["ok"] is None:
            status = "未知"
        else:
            status = "不可用"
        ms = f"{s['ms']}ms" if s["ms"] else "-"
        auth = {True: "支持", False: "不支持", None: "-"}.get(s["auth"], "-")
        note = s["note"] if s["ok"] else (s["error"] or s["note"])
        mark = "★ " if s["recommended"] else "  "
        print(f"{mark}{s['name']:<20} {s['base']:<28} {status:<8} "
              f"{ms:<8} {auth:<10} {note[:40]}")
    best = manager.best()
    print(f"\n推荐数据源：{best}")
    print("（★ 为当前推荐；程序每次导出会自动选最快的可用源）")
    return 0


def cmd_cli_export(args):
    cfg = load_config()
    # 多账号：--use-account 切换当前账号；--account 把本次 Token 存成命名账号
    from .accounts import add_account, set_current, current_token, remove_account
    if getattr(args, "del_account", None):
        n = remove_account(args.del_account)
        print(f"已删除账号 {args.del_account}（命中 {n} 个）")
        return 0
    if getattr(args, "use_account", None):
        try:
            set_current(args.use_account)
            print(f"已切换当前账号：{args.use_account}")
        except KeyError as e:
            print(f"切换失败：{e}")
            return 2
    if getattr(args, "account", None):
        tok = args.token or current_token()
        if not tok:
            print("没有可保存的 Token：请同时用 --token 指定，"
                  "或先保存一个账号。")
            return 2
        add_account(args.account, tok, username=args.username or "",
                    note="命令行保存", make_current=True)
        print(f"已保存账号：{args.account}")
    ns = build_cli_namespace(
        token=args.token,
        output=args.output or cfg.get("output") or DEFAULT_OUTPUT,
        subject_type=args.subject_type or ",".join(
            str(c) for c in (cfg.get("subject_types") or [2])),
        formats=args.formats or ",".join(cfg.get("formats") or ["csv"]),
        workers=args.workers,
        no_stats=args.no_stats,
        save_token=args.save_token,
        proxy=args.proxy if args.proxy is not None else cfg.get("proxy", ""),
        api_base=args.api_base,
        collection_types=args.collection_types,
        source=args.source or cfg.get("source", "") or "",
        username=args.username or cfg.get("username", "") or "",
        since=args.since,
        incremental=args.incremental,
        offline=args.offline,
        probe_sources=args.probe_sources,
        enrich_details=args.enrich_details,
        profile=getattr(args, "profile", True),
        recommend=getattr(args, "recommend", False),
        recommend_limit=getattr(args, "recommend_limit", 20),
        report=getattr(args, "report", False),
        archive=getattr(args, "archive", False),
        supplement=getattr(args, "supplement", False),
        supplement_limit=getattr(args, "supplement_limit", 0),
    )
    if args.save_token and args.token:
        cfg["token"] = args.token
        save_config(cfg)
    # 支持多账号：命令行未显式给 Token 时，优先用当前账号保存的 Token
    if not ns.token:
        from .accounts import current_token
        ns.token = current_token() or ""
    # 与 Web 端保持一致：缓存/源状态统一放在应用级 输出/ 目录，
    # 这样命令行与 Web UI 共享同一份缓存（见 README 与 /api/cache/clear）。
    res = run_export(ns, log=print, cache_dir=str(BASE_DIR / "输出"))
    if res.skipped:
        return 0
    return 0 if res.ok else 1


# ---------------------------------------------------------------- v3.2 子命令

def cmd_history(args):
    """列出历史快照，并对比最近两份。"""
    from .history import list_snapshots, diff_latest, render_diff_markdown
    d = BASE_DIR / "输出" / "历史归档"
    snaps = list_snapshots(d)
    if not snaps:
        print("还没有任何历史快照。\n"
              "先跑一次带 --archive 的导出即可建立基线，例如：\n"
              "  python -m bangumi_exporter.cli --type anime -f excel --archive")
        return 0
    print(f"共 {len(snaps)} 份历史快照（新 → 旧）：\n")
    print(f"{'快照 ID':<22}{'时间':<22}{'条数':<8}账号")
    print("-" * 68)
    for s in snaps:
        meta = s.get("meta") or {}
        who = meta.get("nickname") or meta.get("uid") or ""
        print(f"{s['id']:<22}{s['saved_at_str']:<22}{s['count']:<8}{who}")
    diff = diff_latest(d)
    if diff:
        print()
        print(render_diff_markdown(diff))
    return 0


def cmd_compare(args):
    """对比指定的两份快照。"""
    from .history import compare_snapshots, render_diff_markdown, list_snapshots
    d = BASE_DIR / "输出" / "历史归档"
    old, new = args.compare
    ids = {s["id"] for s in list_snapshots(d)}
    for x in (old, new):
        if x not in ids:
            print(f"找不到快照：{x}")
            print("可用快照：" + "、".join(sorted(ids)) or "（无）")
            return 1
    print(render_diff_markdown(compare_snapshots(d, old, new)))
    return 0


def cmd_accounts(args):
    """列出所有已保存的账号。"""
    from .accounts import list_accounts, current_account
    rows = list_accounts()
    if not rows:
        print("还没有保存任何账号。\n"
              "保存方法（会做混淆处理后写入 accounts.json）：\n"
              "  python -m bangumi_exporter.cli --token 你的Token --account 主号")
        return 0
    print(f"{'':<3}{'账号名':<14}{'昵称':<16}{'UID':<12}{'Token':<22}备注")
    print("-" * 82)
    for a in rows:
        star = "★ " if a["current"] else "  "
        print(f"{star}{a['name']:<14}{a['nickname'] or '-':<16}"
              f"{str(a['uid'] or '-'):<12}{a['token_masked']:<22}{a['note'] or ''}")
    cur = current_account()
    if cur:
        print(f"\n当前账号：{cur.get('name')}")
    return 0


def cmd_backup(args):
    from .accounts import create_backup
    info = create_backup(args.backup)
    print(f"已备份 {info['count']} 个文件 -> {info['path']}（{info['size']} 字节）")
    for f in info["files"]:
        print("  " + f)
    return 0


def cmd_restore(args):
    from .accounts import restore_backup
    info = restore_backup(args.restore)
    print(f"已从 {info['from']} 恢复 {len(info['restored'])} 个文件：")
    for f in info["restored"]:
        print("  " + f)
    if info["skipped"]:
        print("跳过：" + "、".join(info["skipped"]))
    return 0


def cmd_watch(args):
    """定时导出 + 变更提醒。"""
    from .schedule import parse_interval, format_interval, run_watch, ALERT_FILENAME

    try:
        secs = parse_interval(args.watch)
    except ValueError as e:
        print(f"参数错误：{e}")
        return 2
    alert_path = BASE_DIR / "输出" / ALERT_FILENAME
    print(f"定时导出已启动：每 {format_interval(secs)} 一轮；"
          f"提醒写入 {alert_path}")
    print("按 Ctrl+C 结束。\n")

    def build_options():
        # 复用同一套解析结果，但每轮都重新读配置（改动配置无需重启）
        cfg = load_config()
        ns = build_cli_namespace(
            token=args.token,
            output=args.output or cfg.get("output") or DEFAULT_OUTPUT,
            subject_type=args.subject_type or ",".join(
                str(c) for c in (cfg.get("subject_types") or [2])),
            formats=args.formats or ",".join(cfg.get("formats") or ["csv"]),
            workers=args.workers,
            no_stats=args.no_stats,
            proxy=args.proxy if args.proxy is not None else cfg.get("proxy", ""),
            api_base=args.api_base,
            collection_types=args.collection_types,
            source=args.source or cfg.get("source", "") or "",
            username=args.username or cfg.get("username", "") or "",
            since="",                     # 定时模式必须全量，否则 diff 失真
            incremental=False,
            offline=args.offline,
            probe_sources=False,
            enrich_details=args.enrich_details,
            profile=getattr(args, "profile", True),
            recommend=False,              # 定时模式不做推荐，省时间
            report=getattr(args, "report", False),
            archive=True,
        )
        if not ns.token:
            from .accounts import current_token
            ns.token = current_token() or ""
        return ns

    try:
        out = run_watch(build_options, secs, log=print,
                        alert_path=str(alert_path))
    except KeyboardInterrupt:
        print("\n已手动停止。")
        return 0
    print(f"\n定时导出结束：{out['rounds']} 轮，{out['changes']} 次检测到变化"
          f"（{out['stopped']}）")
    return 0


def cmd_gui(_args):
    from .gui import launch_gui
    return launch_gui()


def main(argv=None):
    args = parse_args(argv)
    if args.list_sources:
        return cmd_list_sources(args)
    if getattr(args, "gui", False):
        return cmd_gui(args)
    if getattr(args, "del_account", None):
        return cmd_cli_export(args)
    # v3.2 独立子命令（都带「做完即退出」的语义）
    if getattr(args, "history", False):
        return cmd_history(args)
    if getattr(args, "compare", None):
        return cmd_compare(args)
    if getattr(args, "accounts", False):
        return cmd_accounts(args)
    if getattr(args, "backup", None):
        return cmd_backup(args)
    if getattr(args, "restore", None):
        return cmd_restore(args)
    if getattr(args, "watch", None):
        return cmd_watch(args)
    if args.serve or not is_export_mode(args):
        return cmd_serve(args)
    return cmd_cli_export(args)


if __name__ == "__main__":
    sys.exit(main())