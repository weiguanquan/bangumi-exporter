# -*- coding: utf-8 -*-
"""Bangumi 收藏导出工具 —— 现代化重排版

一个单文件、零第三方依赖、可直接双击使用的 Bangumi(bgm.tv) 收藏导出与数据看板工具。

模块划分：
  constants  类型/格式/镜像等常量与字段定义
  config     配置与 Token 解析
  api        HTTP 客户端（重试 / 退避 / 代理 / 镜像故障转移 / 并发分页）
  cache      评分缓存的持久化（支持增量导出）
  exporters  五种导出格式实现（csv / json / excel / markdown / html）
  stats      统计报告与前端图表数据
  engine     导出编排，实时进度上报
  server     Web 服务（HTTP API + 任务状态 + 现代 SPA 前端）

使用方式：
  python -m bangumi_exporter.cli --serve        # 打开 Web 界面
  python -m bangumi_exporter.cli --gui          # 原生图形界面
  python -m bangumi_exporter.cli -f csv -t all  # 命令行导出
"""

from .constants import (
    APP_NAME,
    API_BASES,
    SUBJECT_TYPES,
    SUBJECT_CODE_TO_NAME,
    COLLECTION_TYPE_NAME,
    FIELD_NAMES,
    FORMATS,
    EXPORT_EXT,
)
from .engine import run_export, build_cli_namespace, Result
from .config import load_config, save_config, resolve_token

__version__ = "3.0.0"
__title__ = "Bangumi 收藏导出工具"

__all__ = [
    "APP_NAME",
    "API_BASES",
    "SUBJECT_TYPES",
    "SUBJECT_CODE_TO_NAME",
    "COLLECTION_TYPE_NAME",
    "FIELD_NAMES",
    "FORMATS",
    "EXPORT_EXT",
    "run_export",
    "build_cli_namespace",
    "Result",
    "load_config",
    "save_config",
    "resolve_token",
    "__version__",
    "__title__",
]