# -*- coding: utf-8 -*-
"""配置管理：应用目录、config.json 读写、Token 优先级解析。"""

import json
import os
import threading
from pathlib import Path


def _find_base_dir():
    env = os.environ.get("BANGUMI_HOME")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    cand = here.parents[2]
    if (cand / "config.json").exists():
        return cand
    return here.parents[1]


BASE_DIR = _find_base_dir()
CONFIG_FILE = BASE_DIR / "config.json"
DEFAULT_OUTPUT = str(BASE_DIR / "输出" / "bangumi_export")

_lock = threading.Lock()


def load_config():
    with _lock:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def save_config(cfg):
    with _lock:
        CONFIG_FILE.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def resolve_token(cli_token=None, cfg=None):
    cfg = cfg if cfg is not None else load_config()
    token = cli_token or os.environ.get("BANGUMI_TOKEN") or cfg.get("token") or ""
    return str(token).strip()


def make_dirs(path):
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p