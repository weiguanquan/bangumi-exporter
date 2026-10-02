# -*- coding: utf-8 -*-
"""原生 tkinter 图形界面（离线备用方案，使用新引擎 + 真实进度）。"""

import os
import queue as queue_mod
import threading
from pathlib import Path

from .config import CONFIG_FILE, DEFAULT_OUTPUT, load_config, save_config
from .constants import FORMATS, SUBJECT_TYPES
from .engine import ExportOptions, Progress, run_export


def launch_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        from tkinter.scrolledtext import ScrolledText
    except ImportError:
        print("当前 Python 未安装 tkinter，无法启动图形界面，请改用 Web 模式或命令行。")
        return 1

    cfg = load_config()
    root = tk.Tk()
    root.title("Bangumi 收藏导出工具 v3")
    root.geometry("820x760")
    root.minsize(700, 620)

    log_queue = queue_mod.Queue()
    prog_ref = {"p": None}

    def queue_log(*args):
        log_queue.put(" ".join(str(a) for a in args))

    # ---- Token ----
    frm_token = ttk.LabelFrame(root, text="Access Token（bangumi.tv → 设置 → App 授权）")
    frm_token.pack(fill="x", padx=10, pady=6)
    token_var = tk.StringVar(value=cfg.get("token", ""))
    show_var = tk.BooleanVar(value=False)
    token_entry = ttk.Entry(frm_token, textvariable=token_var, show="*")
    token_entry.grid(row=0, column=0, padx=6, pady=6, sticky="ew")

    def toggle_show():
        token_entry.configure(show="" if show_var.get() else "*")

    ttk.Checkbutton(frm_token, text="显示", variable=show_var,
                    command=toggle_show).grid(row=0, column=1, padx=4)

    def save_token():
        cfg["token"] = token_var.get().strip()
        save_config(cfg)
        messagebox.showinfo("提示", f"Token 已保存到\n{CONFIG_FILE}")

    ttk.Button(frm_token, text="保存 Token", command=save_token).grid(row=0, column=2, padx=6)
    frm_token.columnconfigure(0, weight=1)

    # ---- 代理 ----
    frm_proxy = ttk.LabelFrame(root, text="代理（可选，如 http://127.0.0.1:7890）")
    frm_proxy.pack(fill="x", padx=10, pady=6)
    proxy_var = tk.StringVar(value=cfg.get("proxy", ""))
    ttk.Entry(frm_proxy, textvariable=proxy_var).pack(fill="x", padx=6, pady=6)

    # ---- 条目类型 ----
    frm_types = ttk.LabelFrame(root, text="条目类型")
    frm_types.pack(fill="x", padx=10, pady=6)
    type_vars = {}
    saved_types = set(cfg.get("subject_types") or [])
    for i, (key, meta) in enumerate(SUBJECT_TYPES.items()):
        var = tk.BooleanVar(value=(not saved_types) or (meta["code"] in saved_types))
        type_vars[key] = var
        ttk.Checkbutton(frm_types, text=meta["name"], variable=var).grid(
            row=0, column=i, padx=6, pady=4)

    # ---- 导出格式 ----
    frm_fmt = ttk.LabelFrame(root, text="导出格式")
    frm_fmt.pack(fill="x", padx=10, pady=6)
    fmt_vars = {}
    saved_fmts = set(cfg.get("formats") or [])
    for i, f in enumerate(FORMATS):
        var = tk.BooleanVar(value=(not saved_fmts and f == "csv") or (f in saved_fmts))
        fmt_vars[f] = var
        ttk.Checkbutton(frm_fmt, text=f, variable=var).grid(row=0, column=i, padx=6, pady=4)

    # ---- 输出 ----
    frm_out = ttk.LabelFrame(root, text="输出文件基础名（自动附加扩展名，另生成 _stats.md）")
    frm_out.pack(fill="x", padx=10, pady=6)
    out_var = tk.StringVar(value=cfg.get("output") or DEFAULT_OUTPUT)
    ttk.Entry(frm_out, textvariable=out_var).grid(row=0, column=0, padx=6, pady=6, sticky="ew")

    def browse():
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("所有文件", "*.*")])
        if p:
            out_var.set(str(Path(p).with_suffix("")))

    ttk.Button(frm_out, text="浏览...", command=browse).grid(row=0, column=1, padx=6)
    frm_out.columnconfigure(0, weight=1)

    # ---- 操作按钮 + 进度 ----
    frm_btn = ttk.Frame(root)
    frm_btn.pack(fill="x", padx=10, pady=6)
    start_btn = ttk.Button(frm_btn, text="开始导出")
    start_btn.pack(side="left", padx=4)

    def open_dir():
        d = str(Path(out_var.get()).parent)
        if hasattr(os, "startfile"):
            os.startfile(d)
        else:
            messagebox.showinfo("目录", d)

    ttk.Button(frm_btn, text="打开输出目录", command=open_dir).pack(side="left", padx=4)
    prog = ttk.Progressbar(frm_btn, mode="determinate", maximum=100)
    prog.pack(side="right", fill="x", expand=True, padx=8)
    prog_ref["p"] = prog

    # ---- 日志区 ----
    log_area = ScrolledText(root, height=18, state="disabled")
    log_area.pack(fill="both", expand=True, padx=10, pady=6)

    def append_log(text):
        log_area.configure(state="normal")
        log_area.insert("end", text + "\n")
        log_area.see("end")
        log_area.configure(state="disabled")

    def poll():
        try:
            while True:
                msg = log_queue.get_nowait()
                if msg is None:
                    start_btn.configure(state="normal")
                    continue
                if isinstance(msg, dict) and "percent" in msg:
                    prog["value"] = msg["percent"]
                    continue
                append_log(msg)
        except queue_mod.Empty:
            pass
        root.after(100, poll)

    def start():
        token = token_var.get().strip()
        if not token:
            messagebox.showerror("错误", "请先填写 Access Token")
            return
        selected_types = [SUBJECT_TYPES[k]["code"] for k, v in type_vars.items() if v.get()]
        selected_fmts = [k for k, v in fmt_vars.items() if v.get()]
        if not selected_types:
            messagebox.showerror("错误", "请至少选择一个条目类型")
            return
        if not selected_fmts:
            messagebox.showerror("错误", "请至少选择一个导出格式")
            return

        cfg["token"] = token
        cfg["subject_types"] = selected_types
        cfg["formats"] = selected_fmts
        cfg["output"] = out_var.get().strip()
        cfg["proxy"] = proxy_var.get().strip()
        save_config(cfg)

        options = ExportOptions(
            token=token,
            subject_types=tuple(selected_types),
            formats=tuple(selected_fmts),
            output=cfg["output"],
            proxy=cfg["proxy"],
        )
        start_btn.configure(state="disabled")
        prog["value"] = 0

        def on_progress(p):
            log_queue.put({"percent": p.percent})

        def worker():
            try:
                progress = Progress(callback=on_progress)
                run_export(options, log=queue_log, progress=progress,
                           cache_dir=str(Path(cfg["output"]).parent))
            except Exception as e:
                queue_log("发生异常：" + str(e))
            finally:
                log_queue.put(None)

        threading.Thread(target=worker, daemon=True).start()

    start_btn.configure(command=start)
    root.after(100, poll)
    append_log("欢迎使用 Bangumi 收藏导出工具 v3。")
    append_log("填写 Token 后选择类型与格式，点击「开始导出」。")
    append_log("提示：Token 保存在同目录 config.json，请勿分享给他人。")
    root.mainloop()
    return 0