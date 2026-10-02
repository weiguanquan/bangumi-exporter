# -*- coding: utf-8 -*-
"""多账号管理 + 配置备份/恢复。

账号存放在 config.json 同级的 accounts.json：

    {"version": 1, "current": "主号",
     "accounts": [{"name": "主号", "token": "<混淆串>", "uid": ..., ...}]}

关于 Token 存储：这里做的是**混淆**（XOR + Base64，密钥由本机
用户名/主机名派生），目的是让 Token 不要以明文肉眼可见地躺在文件里，
**它不是强加密** —— 能读到文件的人同样能还原出 Token。
真正的安全只能靠操作系统权限或专门的密钥管理。这一点如实说明。
"""

import base64
import getpass
import json
import os
import platform
import shutil
import socket
import time
import zipfile
from pathlib import Path

VERSION = 1
ACCOUNTS_FILE = "accounts.json"
BACKUP_NAME = "bangumi_exporter_backup_{ts}.zip"

# 备份时要一并带上的文件（config.json + 输出目录下的状态文件）
STATE_FILES = [".rating_cache.json", ".data_cache.json", ".sources.json"]


def _machine_key():
    """由本机信息派生一个稳定的混淆密钥（非安全密钥）。"""
    parts = []
    for fn in (getpass.getuser, socket.gethostname, platform.node):
        try:
            parts.append(str(fn()))
        except Exception:
            parts.append("?")
    seed = "|".join(parts) or "banggumi"
    return (seed * 8).encode("utf-8")


def obfuscate(text):
    """把明文变成不易肉眼直读的串（可逆，非加密）。"""
    if not text:
        return ""
    key = _machine_key()
    raw = str(text).encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    return "obf:" + base64.urlsafe_b64encode(xored).decode("ascii")


def deobfuscate(text):
    """还原 obfuscate() 的结果；明文（无 obf: 前缀）原样返回。"""
    if not text:
        return ""
    s = str(text)
    if not s.startswith("obf:"):
        return s                      # 兼容历史明文
    try:
        raw = base64.urlsafe_b64decode(s[4:].encode("ascii"))
        key = _machine_key()
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(raw)).decode("utf-8")
    except Exception:
        return ""


def accounts_path(base_dir=None):
    from .config import CONFIG_FILE
    d = Path(base_dir) if base_dir else Path(CONFIG_FILE).parent
    return d / ACCOUNTS_FILE


def load_accounts(base_dir=None):
    p = accounts_path(base_dir)
    if not p.is_file():
        return {"version": VERSION, "current": "", "accounts": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": VERSION, "current": "", "accounts": []}
    data.setdefault("version", VERSION)
    data.setdefault("accounts", [])
    data.setdefault("current", "")
    return data


def save_accounts(data, base_dir=None):
    p = accounts_path(base_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
    return str(p)


def list_accounts(base_dir=None, mask=True):
    """列出账号（默认打码 Token）。"""
    data = load_accounts(base_dir)
    out = []
    for a in data.get("accounts", []):
        tok = deobfuscate(a.get("token", ""))
        out.append({
            "name": a.get("name", ""),
            "username": a.get("username", ""),
            "nickname": a.get("nickname", ""),
            "uid": a.get("uid") or "",
            "note": a.get("note", ""),
            "created_at": a.get("created_at", ""),
            "current": a.get("name") == data.get("current"),
            "token_masked": _mask(tok) if mask else tok,
            "has_token": bool(tok),
        })
    return out


def _mask(tok):
    if not tok:
        return ""
    if len(tok) <= 10:
        return tok[:2] + "*" * max(0, len(tok) - 2)
    return f"{tok[:6]}{'*' * 8}{tok[-4:]}"


def add_account(name, token, uid="", username="", nickname="", note="",
                base_dir=None, make_current=False):
    """新增或更新一个账号。"""
    name = str(name or "").strip()
    if not name:
        raise ValueError("账号名不能为空")
    data = load_accounts(base_dir)
    for a in data["accounts"]:
        if a.get("name") == name:
            a.update({"token": obfuscate(token), "uid": uid or a.get("uid", ""),
                      "username": username or a.get("username", ""),
                      "nickname": nickname or a.get("nickname", ""),
                      "note": note or a.get("note", "")})
            break
    else:
        data["accounts"].append({
            "name": name, "token": obfuscate(token), "uid": uid,
            "username": username, "nickname": nickname, "note": note,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
    if make_current or not data.get("current"):
        data["current"] = name
    save_accounts(data, base_dir)
    return name


def remove_account(name, base_dir=None):
    data = load_accounts(base_dir)
    before = len(data["accounts"])
    data["accounts"] = [a for a in data["accounts"] if a.get("name") != name]
    if data.get("current") == name:
        data["current"] = data["accounts"][0]["name"] if data["accounts"] else ""
    save_accounts(data, base_dir)
    return before - len(data["accounts"])


def set_current(name, base_dir=None):
    data = load_accounts(base_dir)
    if not any(a.get("name") == name for a in data["accounts"]):
        raise KeyError(f"账号不存在: {name}")
    data["current"] = name
    save_accounts(data, base_dir)
    return name


def current_account(base_dir=None):
    data = load_accounts(base_dir)
    cur = data.get("current")
    for a in data["accounts"]:
        if a.get("name") == cur:
            return a
    return None


def current_token(base_dir=None):
    """取当前账号的明文 Token（没有账号时返回 ""）。"""
    a = current_account(base_dir)
    return deobfuscate(a.get("token", "")) if a else ""


# ---------------------------------------------------------------- 备份 / 恢复

def create_backup(dest_dir, base_dir=None):
    """把配置与状态文件打包成一个 zip。"""
    from .config import CONFIG_FILE
    root = Path(base_dir) if base_dir else Path(CONFIG_FILE).parent
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = dest / BACKUP_NAME.format(ts=ts)

    members = []
    cfg = Path(CONFIG_FILE)
    if cfg.is_file():
        members.append((cfg, "config.json"))
    acc = accounts_path(base_dir)
    if acc.is_file():
        members.append((acc, ACCOUNTS_FILE))
    out_dir = root / "输出"
    for name in STATE_FILES:
        f = out_dir / name
        if f.is_file():
            members.append((f, f"输出/{name}"))

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        manifest = {"version": VERSION, "created_at": time.time(),
                    "created_at_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "files": []}
        for src, arc in members:
            z.write(src, arc)
            manifest["files"].append({"arc": arc, "size": src.stat().st_size})
        z.writestr("manifest.json",
                   json.dumps(manifest, ensure_ascii=False, indent=2))
    return {"path": str(out), "count": len(members),
            "files": [m[1] for m in members], "size": out.stat().st_size}


def restore_backup(zip_path, base_dir=None, overwrite=True):
    """从备份 zip 恢复。返回恢复了哪些文件。"""
    from .config import CONFIG_FILE
    root = Path(base_dir) if base_dir else Path(CONFIG_FILE).parent
    zp = Path(zip_path)
    if not zp.is_file():
        raise FileNotFoundError(f"备份文件不存在: {zp}")

    restored, skipped = [], []
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
        # 先解压到临时目录，确认结构后再就位
        for name in names:
            if name == "manifest.json":
                continue
            base = Path(name).name
            if name == "config.json":
                target = Path(CONFIG_FILE)
            elif name == ACCOUNTS_FILE:
                target = accounts_path(base_dir)
            elif name.startswith("输出/"):
                target = root / "输出" / base
            else:
                skipped.append(name)
                continue
            if target.exists() and not overwrite:
                skipped.append(name)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            restored.append(str(target))
    return {"restored": restored, "skipped": skipped, "from": str(zp)}
