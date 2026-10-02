# -*- coding: utf-8 -*-
"""手动安装 PyInstaller 到工作区（绕开 pip 的沙箱兼容问题）

用 PyPI JSON API 解析最新版本的 wheel，urllib 下载，zipfile 解压到目标目录。
用法：python tools/bootstrap_pyinstaller.py [目标目录]
默认目标：项目根目录下的 .pyi 目录
"""
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else
              Path(__file__).resolve().parents[1] / ".pyi")

PACKAGES = [
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "altgraph",
    "packaging",
    "pefile",
    "pywin32-ctypes",
    "setuptools",
]

HEADERS = {"User-Agent": "bangumi-bootstrap/1.0"}


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def pick_wheel(files):
    cands = [f for f in files if f["filename"].endswith(".whl")]

    def score(fn):
        n = fn.lower()
        if "py3-none-any" in n:
            return 0
        if "py3-none-win_amd64" in n:
            return 1
        if "py2.py3-none-any" in n:
            return 2
        if n.endswith("win_amd64.whl"):
            return 3
        return 99

    cands.sort(key=lambda f: score(f["filename"]))
    return cands[0] if cands else None


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in PACKAGES:
        try:
            info = json.loads(fetch(f"https://pypi.org/pypi/{name}/json"))
            version = info["info"]["version"]
            wheel = pick_wheel(info["releases"].get(version) or [])
            if wheel is None:
                print(f"[跳过] {name}: 找不到合适的 wheel")
                continue
            url = wheel["url"]
            print(f"[下载] {name}=={version}  {wheel['filename']} "
                  f"({wheel['size'] / 1024 / 1024:.1f} MB)")
            data = fetch(url)
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                z.extractall(TARGET)
            print(f"[完成] {name}: {len(data) / 1024:.0f} KB")
        except Exception as e:
            print(f"[失败] {name}: {e}")
    print(f"\n安装目标: {TARGET}")
    print("使用方式：把该目录加入 PYTHONPATH，再执行 python -m PyInstaller ...")


if __name__ == "__main__":
    main()
