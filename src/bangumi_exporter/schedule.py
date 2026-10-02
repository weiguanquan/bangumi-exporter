# -*- coding: utf-8 -*-
"""定时导出 + 变更提醒。

用法（CLI）：python -m bangumi_exporter.cli --watch 30m --type anime -f excel

每轮都会：导出 → 归档快照 → 与上一份快照对比；
一旦发现新增/删除/修改，就写一条提醒到「输出/提醒.log」并在控制台高亮。
"""

import re
import time
from datetime import datetime
from pathlib import Path

ALERT_FILENAME = "提醒.log"
_UNITS = {"s": 1, "秒": 1, "m": 60, "分": 60, "h": 3600, "时": 3600,
          "d": 86400, "天": 86400}
_INTERVAL_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhd秒分时天]?)\s*$")


def parse_interval(text, default_unit="m"):
    """把 "30m" / "6h" / "1d" / "90" 解析成秒数。"""
    if text is None:
        raise ValueError("间隔不能为空")
    if isinstance(text, (int, float)):
        secs = float(text)
    else:
        m = _INTERVAL_RE.match(str(text))
        if not m:
            raise ValueError(f"无法解析间隔: {text!r}（示例：30m / 6h / 1d / 90s）")
        value = float(m.group(1))
        unit = m.group(2) or default_unit
        secs = value * _UNITS.get(unit, 60)
    if secs <= 0:
        raise ValueError("间隔必须大于 0")
    return secs


def format_interval(secs):
    secs = float(secs)
    for unit, size in (("天", 86400), ("小时", 3600), ("分钟", 60)):
        if secs >= size:
            return f"{secs / size:g} {unit}"
    return f"{secs:g} 秒"


def append_alert(path, message):
    """把一条提醒追加到提醒日志（同时返回该行）。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    with open(p, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


def read_alerts(path, limit=50):
    p = Path(path)
    if not p.is_file():
        return []
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def summarize_diff(diff):
    """把快照差异变成一句人话。"""
    if not diff:
        return "首次运行，已建立基线快照。"
    parts = []
    if diff.get("added"):
        names = "、".join((r.get("中文名") or r.get("原名") or "")[:18]
                          for r in diff["added"][:5])
        parts.append(f"新增 {len(diff['added'])} 条（{names}）")
    if diff.get("removed"):
        parts.append(f"删除 {len(diff['removed'])} 条")
    if diff.get("changed"):
        sample = diff["changed"][0]
        fields = "、".join(f["field"] for f in sample.get("fields", [])[:3])
        parts.append(f"修改 {len(diff['changed'])} 条（如 {sample.get('name', '')[:18]}：{fields}）")
    return "；".join(parts) if parts else "无变化"


def run_watch(build_options, interval_seconds, log=print, max_rounds=None,
              cancel_event=None, alert_path=None, on_round=None):
    """定时导出主循环。

    build_options : 每轮调用一次，返回 ExportOptions（允许参数随轮次变化）
    返回 {"rounds": n, "changes": m, "last_diff": ..., "stopped": 原因}
    """
    rounds = 0
    changes = 0
    last_diff = None
    stopped = "达到轮次上限" if max_rounds else "被中断"

    while True:
        if cancel_event is not None and cancel_event.is_set():
            stopped = "已取消"
            break
        if max_rounds is not None and rounds >= max_rounds:
            stopped = "达到轮次上限"
            break

        rounds += 1
        started = time.time()
        log(f"\n===== 第 {rounds} 轮（{datetime.now().strftime('%H:%M:%S')}）=====")
        result = None
        try:
            from .engine import run_export
            opts = build_options()
            opts.archive = True                 # 定时模式必须归档才能对比
            result = run_export(opts, log=log)
        except Exception as e:
            log(f"本轮导出失败：{type(e).__name__}: {e}")
            if alert_path:
                append_alert(alert_path, f"导出失败：{type(e).__name__}: {e}")

        if result is not None:
            diff = result.compare or None
            last_diff = diff
            changed = bool(diff and diff.get("has_changes"))
            if changed:
                changes += 1
                msg = "收藏有变化：" + summarize_diff(diff)
                log("🔔 " + msg)
                if alert_path:
                    append_alert(alert_path, msg)
            else:
                log("本轮无变化。" if rounds > 1 else "已建立基线快照。")
            if on_round:
                try:
                    on_round(result, diff)
                except Exception:
                    pass

        if max_rounds is not None and rounds >= max_rounds:
            stopped = "达到轮次上限"
            break

        # 可中断的等待
        wait = interval_seconds - (time.time() - started)
        if wait < 0:
            wait = 0
        log(f"下一轮在 {format_interval(max(wait, interval_seconds))} 后...")
        end = time.time() + max(wait, interval_seconds)
        while time.time() < end:
            if cancel_event is not None and cancel_event.is_set():
                stopped = "已取消"
                break
            time.sleep(min(0.5, max(0.0, end - time.time())))
        else:
            continue
        break

    return {"rounds": rounds, "changes": changes,
            "last_diff": last_diff, "stopped": stopped}
