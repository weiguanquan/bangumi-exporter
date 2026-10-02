#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动 Web 界面，并把输出同时写到控制台与日志文件。

Windows 没有 Unix 的 tee，在 .bat 里用管道 + 嵌套引号拼 tee 极易解析失败，
所以这里用纯标准库实现「双写」，由启动.bat 调用。

环境变量：
  BANGUMI_HOME  项目根目录（启动.bat 已设置）
  BANGUMI_LOG   日志文件路径，默认 <BANGUMI_HOME>/输出/launch.log
"""
import os
import subprocess
import sys
from pathlib import Path


def _resolve_paths():
    home = Path(os.environ.get("BANGUMI_HOME")
                or Path(__file__).resolve().parents[1])
    log_path = Path(os.environ.get("BANGUMI_LOG") or (home / "输出" / "launch.log"))
    return home, log_path


def main():
    # 控制台编码可能不是 UTF-8（例如未执行 chcp 时），保证不会因编码异常中断启动
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass

    home, log_path = _resolve_paths()
    webui = home / "src" / "webui.py"
    if not webui.exists():
        print(f"错误：找不到入口文件 {webui}")
        return 1

    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    # 让子进程统一以 UTF-8 输出，避免管道里 cp936/UTF-8 混用导致乱码
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # 管道里的 stdout 默认是块缓冲，会导致控制台/日志长时间空白，必须关闭缓冲
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("BANGUMI_HOME", str(home))

    cmd = [sys.executable, str(webui)]
    with open(log_path, "a", encoding="utf-8", errors="replace") as log_file:
        proc = subprocess.Popen(
            cmd, cwd=str(home), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        try:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log_file.write(line)
                log_file.flush()
        except KeyboardInterrupt:
            proc.terminate()
        finally:
            if proc.stdout is not None:
                proc.stdout.close()
    return proc.wait()


if __name__ == "__main__":
    sys.exit(main())
