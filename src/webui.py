#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兼容入口：启动 Web 界面（带增强错误捕获）。

v3 重构后，真正实现位于 bangumi_exporter 包中。
本文件仅作为「启动.bat」的历史入口保留。
增加了全局异常捕获，确保任何报错都能写入日志文件。
"""
import os
import sys
import traceback
from pathlib import Path

# 确保 src 目录在 import 路径中（支持直接 pythonw webui.py 运行）
sys.path.insert(0, str(Path(__file__).resolve().parent))

def _get_log_path():
    """获取日志文件路径（输出/launch.log）。"""
    base = os.environ.get("BANGUMI_HOME") or str(Path(__file__).resolve().parents[1])
    log_dir = Path(base) / "输出"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "launch.log"

def _write_log(msg):
    """追加写入日志文件。"""
    try:
        with open(_get_log_path(), "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

if __name__ == "__main__":
    os.environ.setdefault("BANGUMI_HOME", str(Path(__file__).resolve().parents[1]))
    try:
        from bangumi_exporter.cli import main  # noqa: E402
        sys.exit(main(["--serve"]))
    except Exception as e:
        err_msg = f"[致命错误] {type(e).__name__}: {e}\n{traceback.format_exc()}"
        _write_log(err_msg)
        # 如果是 pythonw 启动（无控制台），弹窗提示
        if not sys.stdout:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Bangumi 导出工具启动失败：\n{e}\n\n详细日志见：{_get_log_path()}",
                "启动失败",
                16
            )
        else:
            print(err_msg)
            input("\n按回车键退出...")
        sys.exit(1)
