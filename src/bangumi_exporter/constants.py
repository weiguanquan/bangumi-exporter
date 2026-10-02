# -*- coding: utf-8 -*-
"""常量定义：条目类型 / 收藏类型 / 导出格式 / 镜像 / 字段。"""

APP_NAME = "Bangumi 收藏导出工具"
APP_VERSION = "3.2.0"

# 条目类型（Bangumi subject_type 代码）
SUBJECT_TYPES = {
    "anime": {"code": 2, "name": "动画", "color": "#f09199"},
    "book":  {"code": 1, "name": "书籍", "color": "#e5c07b"},
    "music": {"code": 3, "name": "音乐", "color": "#7aa2f7"},
    "game":  {"code": 4, "name": "游戏", "color": "#9ece6a"},
    "real":  {"code": 6, "name": "三次元", "color": "#bb9af7"},
}
SUBJECT_CODE_TO_NAME = {v["code"]: v["name"] for v in SUBJECT_TYPES.values()}

# 收藏类型（collection type 代码）
COLLECTION_TYPE_NAME = {1: "想看", 2: "看过", 3: "在看", 4: "搁置", 5: "抛弃"}

# 排序优先级：在看 > 想看 > 看过 > 搁置 > 抛弃
COLLECTION_TYPE_ORDER = {3: 0, 1: 1, 2: 2, 4: 3, 5: 4}

# 条目类型分组排序
SUBJECT_TYPE_ORDER = {2: 0, 1: 1, 3: 2, 4: 3, 6: 4}

# ==================== 数据源（官方 + 第三方镜像） ====================
# 每个源的能力不同，字段含义：
#   base    API 根地址
#   name    界面显示名
#   kind    official（官方）/ mirror（第三方镜像）
#   auth    是否支持 /v0/me 鉴权端点
#           ⚠ 关键：部分镜像对 /v0/me 一律返回 401，但收藏端点完全正常。
#             这类源若排在前面，会让程序误报「Token 无效或已过期」并中止导出。
#             因此 auth=False 的源绝不能用于身份识别，只能用于取数据。
#   note    说明（展示给用户）
#
# 排序即「默认尝试顺序」，实际运行时会并发探测并按实测延迟重新排序。
SOURCES = [
    {
        "base": "https://api.bgmapi.com",
        "name": "BGMAPI 镜像",
        "kind": "mirror",
        "auth": True,
        "note": "Kazumi 同款鉴权镜像；鉴权、收藏、条目、搜索端点均可用",
    },
    {
        "base": "https://api.bgm.tv",
        "name": "官方 API",
        "kind": "official",
        "auth": True,
        "note": "官方源，数据最权威；部分网络环境不可达",
    },
    {
        "base": "https://next.bgm.tv",
        "name": "官方 Next API",
        "kind": "official",
        "auth": True,
        "note": "官方新版 API；部分网络环境不可达",
    },
    {
        "base": "https://bgmapi.anibt.net",
        "name": "Anibt 镜像",
        "kind": "mirror",
        "auth": False,
        "note": "收藏端点可用，但 /v0/me 恒返回 401，不能用于身份识别",
    },
    {
        "base": "https://api.bgm.icu",
        "name": "BGM.ICU 镜像",
        "kind": "mirror",
        "auth": True,
        "note": "证书链不完整，连接时会自动降级为不校验证书",
    },
]

SOURCE_BY_BASE = {s["base"]: s for s in SOURCES}

# 向后兼容：旧代码里的 API_BASES
API_BASES = [s["base"] for s in SOURCES]

# 熔断参数：连续失败达到阈值后冷却，避免每次导出都卡在坏源上
SOURCE_FAIL_THRESHOLD = 3
SOURCE_COOLDOWN_BASE = 60.0      # 秒，首次冷却时长
SOURCE_COOLDOWN_MAX = 900.0      # 秒，冷却时长上限

# 源探测用的短超时：坏源不应让启动卡住几分钟（探测是并发的，总耗时≈最慢的源）
# 注意 socket.create_connection 会对每个解析出的 IP 各用一次 timeout，
# 多 A 记录的坏域名最坏耗时 ≈ timeout × IP 数，因此这里取较小的值。
PROBE_TIMEOUT = 6
PROBE_RETRIES = 1

# 并发探测预算：拿到可用源后最多再等这么久就返回（其余源在后台继续探测）
PROBE_MIN_BUDGET = 2.5
PROBE_BUDGET = 20.0

# 导出格式
FORMATS = ["csv", "json", "excel", "markdown", "html"]
FORMAT_LABEL = {
    "csv": "CSV",
    "json": "JSON",
    "excel": "Excel",
    "markdown": "Markdown",
    "html": "HTML",
}
EXPORT_EXT = {"csv": ".csv", "json": ".json", "excel": ".xlsx",
              "markdown": ".md", "html": ".html"}

# 导出行字段（顺序即表格顺序）
FIELD_NAMES = [
    "序号", "条目类型", "收藏类型", "中文名", "原名",
    "我的评分", "BGM评分", "评分人数", "排名",
    "看到第几集", "总集数", "卷数", "放送日期", "放送星期", "平台",
    "制作公司", "条目标签", "简介",
    "我的短评", "我的标签", "条目ID", "条目链接", "更新时间",
]

# 每行最多导出多少个社区标签（避免单元格过长）
TAG_LIMIT = 15

# 标准放送星期（Bangumi 的 infobox 偶尔会给出
# 「星期三、星期四（8话起）」这类混合值，统计时要过滤掉，
# 否则会把一个脏值当成第八个「星期」）
WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def clean_weekday(value):
    """只保留标准的一周七天，其余（混合/带备注/空）返回空串。"""
    s = str(value or "").strip()
    return s if s in WEEKDAYS else ""

# 字段类型（前端表格用）
FIELD_META = {
    "序号": {"type": "num"},
    "条目类型": {"type": "cat"},
    "收藏类型": {"type": "cat"},
    "中文名": {"type": "title"},
    "原名": {"type": "sub"},
    "我的评分": {"type": "score"},
    "BGM评分": {"type": "score"},
    "评分人数": {"type": "num"},
    "排名": {"type": "num"},
    "看到第几集": {"type": "num"},
    "总集数": {"type": "num"},
    "卷数": {"type": "num"},
    "放送日期": {"type": "date"},
    "放送星期": {"type": "cat"},
    "平台": {"type": "cat"},
    "制作公司": {"type": "cat"},
    "条目标签": {"type": "tags"},
    "简介": {"type": "text"},
    "我的短评": {"type": "text"},
    "我的标签": {"type": "tags"},
    "条目ID": {"type": "id"},
    "条目链接": {"type": "link"},
    "更新时间": {"type": "date"},
}

# 收藏状态可选（用于过滤与统计）
COLLECTION_STATUS_OPTIONS = [
    {"name": "想看", "code": 1},
    {"name": "看过", "code": 2},
    {"name": "在看", "code": 3},
    {"name": "搁置", "code": 4},
    {"name": "抛弃", "code": 5},
]