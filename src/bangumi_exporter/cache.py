# -*- coding: utf-8 -*-
"""缓存层。

- :class:`RatingCache`  —— 评分缓存（避免重复请求 BGM 评分）
- :class:`DataCache`    —— 完整收藏数据缓存，支持「增量导出」与「离线重导出」

DataCache 以「条目ID」为键保存**展平后的完整记录**，因此：
  * 增量导出：本次抓到的数据与上次缓存对比，只导出 新增/有变化 的条目；
  * 离线重导出：完全没有网络时，也能用缓存重新生成任意格式的文件；
  * 变化审计：能列出 新增 / 修改 / 删除 三类差异。
"""

import json
import threading
import time
from pathlib import Path

# 展平记录里不参与「变化检测」的字段（序号每次都会重排）
_VOLATILE_FIELDS = ("序号",)


def _norm(value):
    """把值归一化，避免 0/""/None 之间的伪差异。"""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _signature(row):
    return tuple(sorted((k, _norm(v)) for k, v in row.items()
                        if k not in _VOLATILE_FIELDS))


class RatingCache:
    """线程安全的评分缓存管理器。"""

    def __init__(self, cache_path):
        self._path = Path(cache_path)
        self._lock = threading.Lock()
        self._data = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def save(self):
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, ensure_ascii=False),
                encoding="utf-8",
            )

    def get(self, subject_id):
        with self._lock:
            return self._data.get(str(subject_id))

    def put(self, subject_id, rating):
        with self._lock:
            self._data[str(subject_id)] = rating

    def has(self, subject_id):
        with self._lock:
            return str(subject_id) in self._data

    def clear(self):
        with self._lock:
            self._data.clear()
        self.save()

    def count(self):
        with self._lock:
            return len(self._data)


class DataCache:
    """完整收藏数据缓存（增量导出 / 离线重导出）。"""

    VERSION = 1

    def __init__(self, path):
        self._path = Path(path)
        self._lock = threading.RLock()
        self._items = {}      # str(条目ID) -> 展平记录
        self._meta = {}
        self._load()

    # ---------------- 读写 ----------------
    def _load(self):
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(raw, dict):
            return
        items = raw.get("items")
        if isinstance(items, dict):
            self._items = {str(k): v for k, v in items.items()
                           if isinstance(v, dict)}
        meta = raw.get("meta")
        if isinstance(meta, dict):
            self._meta = meta

    def save(self):
        with self._lock:
            payload = {
                "version": self.VERSION,
                "meta": self._meta,
                "items": self._items,
            }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False),
                           encoding="utf-8")
            tmp.replace(self._path)      # 原子替换，避免半截文件
        except Exception:
            pass

    def clear(self):
        with self._lock:
            self._items.clear()
            self._meta = {}
        self.save()

    def count(self):
        with self._lock:
            return len(self._items)

    def loaded_at(self):
        with self._lock:
            return self._meta.get("saved_at")

    def items(self):
        with self._lock:
            return list(self._items.values())

    def set_meta(self, **kw):
        with self._lock:
            self._meta.update(kw)
            self._meta["saved_at"] = time.time()

    def meta(self):
        with self._lock:
            return dict(self._meta)

    # ---------------- 差异计算 ----------------
    def diff(self, rows):
        """把本次抓到的 rows 与缓存对比。

        返回 dict(added, changed, unchanged, removed, total)：
          added/changed 为**本次的行**（可直接导出），removed 为缓存中被删掉的旧行。
        """
        with self._lock:
            old = dict(self._items)
        seen = set()
        added, changed, unchanged = [], [], 0
        for row in rows:
            key = str(row.get("条目ID") or "")
            if not key:
                continue
            seen.add(key)
            prev = old.get(key)
            if prev is None:
                added.append(row)
            elif _signature(prev) != _signature(row):
                changed.append(row)
            else:
                unchanged += 1
        removed = [v for k, v in old.items() if k not in seen]
        return {"added": added, "changed": changed, "unchanged": unchanged,
                "removed": removed, "total": len(rows)}

    def merge(self, rows):
        """把本次 rows 并入缓存（整表替换语义：缓存 = 最近一次抓取的结果）。"""
        with self._lock:
            self._items = {str(r.get("条目ID")): r for r in rows
                           if r.get("条目ID")}
        return self.count()

    # ---------------- 过滤 ----------------
    @staticmethod
    def filter_since(rows, since):
        """只保留「更新时间 >= since」的行。since 支持 ISO 日期或时间戳。"""
        if not since:
            return list(rows)
        cutoff = _parse_since(since)
        if cutoff is None:
            return list(rows)
        out = []
        for r in rows:
            ts = _parse_iso(r.get("更新时间"))
            if ts is not None and ts >= cutoff:
                out.append(r)
        return out


def _parse_iso(text):
    """解析 Bangumi 的 '2026-10-02T08:47:44+08:00' 时间戳。"""
    if not text:
        return None
    s = str(text).strip()
    try:
        from datetime import datetime
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _parse_since(since):
    """把 --since 参数解析成时间戳：支持 ISO 日期、'YYYY-MM-DD'、相对天数。"""
    from datetime import datetime, timezone
    if isinstance(since, (int, float)):
        return float(since)
    s = str(since).strip()
    if not s:
        return None
    # 相对写法：7d / 24h / 30m
    if s[:-1].isdigit() and s[-1] in "dhm":
        unit = {"m": 60, "h": 3600, "d": 86400}[s[-1]]
        return time.time() - int(s[:-1]) * unit
    ts = _parse_iso(s)
    if ts is not None:
        return ts
    try:                                  # 纯日期
        dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None
