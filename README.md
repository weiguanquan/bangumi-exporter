# 📺 Bangumi 收藏导出工具 v3.2

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![AI Generated](https://img.shields.io/badge/100%25-AI%20Generated-blueviolet)](#-关于本项目的来源全部内容由-ai-生成)
[![Python](https://img.shields.io/badge/Python-3.8%2B%20stdlib%20only-3776AB.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#)

一个现代化重排版的 **Bangumi (bgm.tv) 收藏导出与数据看板工具**。

零第三方依赖、单文件双击启动、纯标准库实现。

---

## 🤖 关于本项目的来源：**全部内容由 AI 生成**

> **本项目从第一行代码到这份 README，全部由 AI 编写，没有一行是人类手写的。**

| 项目 | 说明 |
|---|---|
| **代码** | `src/` 下全部 21 个 Python 模块（约 6,500 行）、`tools/` 下 3 个辅助脚本，**100% 由 AI 生成** |
| **文档** | 本 `README.md` 与 `说明.txt`，**100% 由 AI 生成** |
| **测试** | 单元回归（315 项断言）、服务端/UI 套件、交付物验收（42 项），**全部由 AI 编写并执行** |
| **架构与功能设计** | 模块划分、8 项功能的实现方案、缓存策略、回归测试思路，**由 AI 自主决定** |
| **人类参与** | 仅提出需求、选择功能范围、提供自己的 Bangumi 账号用于验证 |

- 生成方式：**AI 编程助手（DeepSeek Harness 驱动的编码代理）自主完成**
  需求拆解 → 模块设计 → 编码 → 调试 → 测试 → 文档
- 开发过程中 AI 自行发现并修复的问题包括：argparse `epilog` 元组导致的 `--help` 崩溃、
  推荐算法排序轴选错（把冷门低分作品推到最前）、离线模式下评分直方图缓存未初始化、
  画像标签按 TF-IDF 排序导致「最罕见」而非「最核心」的题材排在最前、
  JSON 直方图字符串键引发的 `TypeError`、infobox 脏数据污染星期分布等
- **请把本项目当作 AI 生成物来看待**：它没有经过人类逐行审查，
  在生产环境或重要数据上使用前，建议自行复核关键逻辑

如果你要引用、二次分发或用于作业/论文，请保留这段说明。

---

## ✨ v3.2 新特性（大数据分析 + 报告 + 自动化）

> 这一版的重点是**把「导出一张表」升级成「看懂自己」**：画像、推荐、
> 全站对比、可视化报告、历史快照、定时提醒、多账号。

### 🖼 单文件可视化 HTML 报告
导出时勾选「可视化 HTML 报告」（或 `--report`），会额外生成
`bangumi_export_报告.html`：**图表全部是手写内联 SVG，零外部依赖**，
断网、换电脑、直接发给朋友都能正常打开。

包含：收藏构成环形图、放送年份/季度柱状图、平台分布、BGM 评分分布、
兴趣标签横条图、用户画像、全站评分分布、猜你喜欢卡片、数据体检表、全部条目表。

### 🧠 用户画像（TF-IDF / 信息熵 / 基尼系数）
- **兴趣标签 Top 25**：按「覆盖了你多少条收藏」排序，并给出占比与 TF-IDF 区分度
- **多样性指标**：香农熵（bit）、归一化熵、**等效标签数**（2^H）、
  基尼系数、Top5 集中度 —— 量化「你是专精型还是杂食型」
- **口味洞察**：自动生成人话结论，例如
  「口味核心：战斗、异世界、搞笑、漫画改、轻改」「52% 的收藏是 2020 年后作品」
  「86% 是单季番」
- **个人评分模型**：有 ≥8 条评分时，用岭回归拟合「你会给什么样的作品打高分」，
  输出各特征（BGM 评分、年代、集数、标签）的权重与 R²

### ✨ 智能推荐（为什么不是随便推）
推荐链路刻意避开了两个坑：

1. **不用 `sort=rank` 检索**：Bangumi 会把「评分人数不足、rank=0」的冷门条目
   排在前面，结果全是没人看过的片子。改用 **`sort=heat`（热度排序）**。
2. **不裸推荐**：候选必须通过口碑阈值（**评分 ≥ 6.5 且评分人数 ≥ 200**），
   再按 `0.7 × 画像匹配度 + 0.3 × 口碑分` 排序。

实测效果（153 条动画的账号）：推的是《某科学的超电磁炮》《败犬女主太多了！》
《莉兹与青鸟》《化物语》《进击的巨人 第三季 Part.2》这类既对口味又公认好看的作品。

### 🌐 全站对比（我的口味 vs 大众）
利用条目详情里的 **`rating.count` 评分直方图**（1~10 分各有多少人打分，
已缓存进 `.rating_cache.json`，**完全离线可用**）：
- 你收藏的作品**等权全站平均分** vs 全站基准 6.5
- **按打分人数加权**的全站均分（与上一项口径不同，会因热门作品拉高）
- 公认高分（≥7.5）/ 低分（<6.0）各多少部
- 你收藏里全站口碑最高的 Top 15
- 有评分时：逐条的「我 vs 大众」差值、你的分位、差异最大的 Top 15

> 你没有给任何条目打分时，报告会明确说明「无法做我的评分 vs 大众的直接对比」，
> 并改为展示全站口径分布 —— 而不是编造数据。

### 📚 数据补全（简介 / 制作公司 / staff / 声优 / 分集 / 播出星期 / 卷数）
`--supplement` 会为每个条目额外抓取 4 个接口：

| 接口 | 得到什么 |
|---|---|
| `/v0/subjects/{id}` | **简介**、infobox（**放送星期** / 话数 / 原作 / 别名）、**卷数** |
| `/v0/subjects/{id}/persons` | **staff**（含职务：原作 / 导演 / 音乐 / **动画制作**…） |
| `/v0/subjects/{id}/characters` | 角色与**声优**（CV） |
| `/v0/episodes?subject_id=` | **分集列表**（集数 / 标题 / **播出日期**） |

- 结果写进表格的 4 个新列（**制作公司 / 放送星期 / 卷数 / 简介**），
  完整数据另存 `_详情.md` 与 `_详情.json`
- 单独缓存到 `.detail_cache.json`，**只抓缺失的条目** —— 第二次导出几乎零请求
- 「制作公司」按 `动画制作 → 制作 → 开发 → infobox` 依次回退取值，
  实测能正确得到 `スタジオバインド` / `WHITE FOX` / `MAPPA` 这类工作室名

### 📚 各类型专门统计（书籍卷数 / 游戏平台 / 音乐曲目数）
按「条目类型」分组做**类型专属**统计，而不是所有类型混在一张表里：

- **书籍**：卷数总量 / 平均卷数 / 最多卷数 / 中位数（`卷数` 为 0 的不计入，避免污染平均）
- **游戏**：平台分布（PC / PS5 / Switch…）+ 游玩人数
- **音乐**：曲目数
- **动画 / 三次元**：话数、平台、**播出星期**分布
- 每种类型还带：收藏状态构成、全站均分、我的均分、年代跨度、制作公司 Top、高频标签

### 🩺 数据体检（解释每一列为什么空）
有几列天生就是空的，但以前只会让人以为「工具坏了」。现在导出时会逐个字段给出
来源接口与判定（✅ 正常 / ◐ 部分 / ⬜ 空 / 0️⃣ 全为 0），并明确区分：

- **你自己填的内容**（我的评分 / 我的短评 / 我的标签）：站外接口不会替你编造，为空是正常的
- **官方接口缺失**（排名 / 总集数 / 放送日期 / 平台 / 中文名）：会给出去哪个接口取
- **全为 0 的列**（看到第几集）：单独标记为 `all_zero`

### 🕘 收藏历史归档 + 任意两次快照对比
`--archive` 会把本次结果归档为快照（默认保留最近 60 份）。
之后就能精确回答：**新增了哪些、删了哪些、把哪些从「在看」改成了「看过」、
评分/短评/进度发生了什么变化**。

```bash
# 列出所有快照 + 自动对比最近两份
python -m bangumi_exporter.cli --history
# 对比指定的两份快照
python -m bangumi_exporter.cli --compare 20261001-120000 20261002-230000
```

Web UI 的「导出」页也有「🕘 历史快照 / 对比变化」按钮，可视化对比。

### ⏰ 定时导出 + 变更提醒
```bash
python -m bangumi_exporter.cli --watch 30m    # 每 30 分钟
python -m bangumi_exporter.cli --watch 6h     # 每 6 小时
python -m bangumi_exporter.cli --watch 1d     # 每天
```
每轮都会导出并归档，**只有检测到变化时才写提醒**到 `输出/提醒.log`，
并在控制台高亮 `🔔 收藏有变化：新增 2 条（…）`。

### 👥 多账号 + 配置备份/恢复
```bash
# 保存/切换/查看/删除账号
python -m bangumi_exporter.cli --token <TOKEN> --account 主号
python -m bangumi_exporter.cli --use-account 主号 -f excel
python -m bangumi_exporter.cli --accounts
python -m bangumi_exporter.cli --del-account 小号

# 备份 / 恢复（config.json + 账号 + 全部缓存与状态）
python -m bangumi_exporter.cli --backup D:\备份
python -m bangumi_exporter.cli --restore D:\备份\bangumi_exporter_backup_xxx.zip
```
账号存在 `accounts.json`。Token 做了 **XOR + Base64 混淆**（密钥由本机用户名/
主机名派生），**明文不再肉眼可见**；但要如实说明：**这是混淆、不是强加密** ——
能读到文件的人同样能还原出 Token。真正的安全只能靠系统权限或专门的密钥管理。

### 🐛 v3.2 顺手修掉的老问题
- **`--help` 一直是崩的**：`epilog=(...,)` 多了个逗号，被 Python 当成
  1 元组，`argparse` 一格式化帮助信息就 `AttributeError`。已修复。
- **离线模式下读不到评分直方图**：`RatingCache` 原本只在联网分支创建，
  导致「全站对比」在离线时静默退化为空。现在缓存对象始终建立（纯本地读文件）。
- **`_percentile` 遇到字符串键会崩**：JSON 里直方图的键是字符串，
  `str < int` 直接 `TypeError`。已统一转 int 并加了防御。
- **画像排序反了**：`top_tags` 原本按 TF-IDF 排序，等于把「你自己收藏里最罕见的
  标签」顶到最前面，而不是「你最爱看的题材」。现在按覆盖条数排序，
  TF-IDF 仅用于相似度向量与区分度展示。

---

## ✨ v3.1 新特性

### 🌐 智能多数据源（参考 Kazumi 的源列表）
内置 5 个数据源，**导出前自动并发探测、按实测延迟排序、只挑最快的可用源**：

| 数据源 | 地址 | 说明 |
|---|---|---|
| BGMAPI 镜像 | `api.bgmapi.com` | ⭐ Kazumi 同款鉴权镜像，鉴权/收藏/条目/搜索全支持 |
| Anibt 镜像 | `bgmapi.anibt.net` | 备用镜像，**不支持 `/v0/me` 鉴权** |
| 官方 API | `api.bgm.tv` | 官方源（国内常不可达） |
| 官方 Next API | `next.bgm.tv` | 官方新版源 |
| BGM.ICU 镜像 | `api.bgm.icu` | 备用镜像 |

- **熔断冷却**：连续失败 3 次的源进入指数退避冷却（60s → 900s），不再拖慢导出
- **鉴权能力区分**：明确区分「Token 无效(401)」/「该源不支持鉴权」/「网络不通」，
  彻底修掉了「拿不支持鉴权的镜像去验 Token，导致用有效 Token 也被误报失效」的老问题
- **探测快**：并发 + 提前退出，实测 **2.5 秒**出结果（旧版串行最长可等 280 秒）
- **设置页可视化**：每个源的延迟/可用性/是否支持鉴权一目了然，可一键重新探测或手动指定

### ⚡ 增量导出 / 离线导出 / 时间过滤
- **增量导出**：只导出与上次相比**新增 + 有变化**的条目；没有变化时直接跳过、不生成空文件
- **离线导出**：完全断网，用本地完整数据缓存重新生成任意格式的文件（实测 153 条 0.02 秒）
- **时间过滤**：`--since 2026-01-01`、`--since 7d`、`--since 24h` 只导出最近有更新的条目
- **完整数据缓存**（`.data_cache.json`）：以「条目 ID → 整行数据」保存，可精确算出
  新增/变化/未变/删除四类差异

### 📊 高级统计分析
- **按放送年份**、**按放送季度**（最近 12 季）
- **我的标签 Top 20**、**按平台分布**（TV/OVA/剧场版/WEB）
- **我的评分 vs BGM 评分**：平均分差、皮尔逊相关系数、我打分更高/更低的分档榜单
- **追番完成度**：已看完 / 看了一部分 / 未开始

### 🩺 导出结果自检
每次导出后自动校验生成的文件是否真的可解析、条数是否一致
（CSV 重新读行数、JSON 重新解析、xlsx 校验 zip 结构与工作表 XML），
自检不通过会明确告警，而不是给你一个悄悄损坏的文件。

### 🐛 顺手修掉的老问题
- **「平台」列永远是空的**：详情接口其实已经返回了 `platform`，但旧代码把整份响应
  用完就扔、只留下评分。现在一次请求同时拿到评分与平台（实测 153/153 全部填充）
- **评分人数可能被算错**：收藏接口内嵌的 `collection_total` 是「收藏人数」，
  与「评分人数」语义不同，新代码绝不混用

---

## ✨ v3 重构亮点

### 🎨 全新 UI
- **现代暗色玻璃拟态设计**：渐变配色（Bangumi 粉 #f09199 + 蓝 #7aa2f7）
- **左侧导航栏**：导出 / 仪表盘 / 数据表 / 日志 / 设置
- **真实结构化进度条**：阶段 + 百分比 + 当前类型 + 已获取计数，不再是无限滚动
- **纯 SVG 图表**：收藏分布环图、评分分布柱图、Top 10 榜单
- **数据表格**：封面图、搜索、排序、状态过滤、直达 bgm.tv、CSV 复制

### 🚀 新功能
- **按收藏状态过滤**：只导出看过 / 在看 / 想看 / 搁置 / 抛弃
- **任务取消**：运行中可随时取消
- **Token 测试连接**：导出前验证 Token 有效性
- **浏览器内下载**：导出完成后直接在浏览器下载文件
- **评分缓存**：二次导出跳过已缓存条目的网络请求
- **封面图显示**：数据表格展示条目封面缩略图
- **直达链接**：点击条目名直接跳转 bgm.tv 详情页

### 🏗️ 架构重构
- **模块化包结构**：`bangumi_exporter/` 包，职责清晰
  - `constants.py` — 类型/格式/**数据源注册表**常量
  - `config.py` — 配置管理
  - `api.py` — HTTP 客户端（重试/退避/代理/**多源故障转移**）
  - `sources.py` — 数据源探测、排序、熔断与持久化
  - `cache.py` — 评分缓存 + 完整数据缓存
  - `exporters.py` — 五种导出格式
  - `stats.py` — 统计报告 + 图表数据
  - `engine.py` — 导出编排 + 实时进度
  - `server.py` — Web 服务 + 任务状态
  - `ui.py` — SPA 前端
  - `cli.py` — 统一入口
  - `gui.py` — 原生 tkinter 界面（备用）
- **三种运行模式**：Web UI（默认） / 原生 GUI / 命令行

---

## 🚀 快速开始

### 双击启动
```bash
双击「启动.bat」
```
浏览器自动打开，粘贴 Token 即可使用。

### 命令行导出
```bash
# 不带任何参数 = 启动 Web 界面（和 --serve 一样）
python -m bangumi_exporter.cli

# 导出动画到 CSV（指定任一导出参数才会走命令行导出）
python -m bangumi_exporter.cli --type anime -f csv

# 导出全部类型、全部格式
python -m bangumi_exporter.cli --type all -f all

# 指定 Token 和输出路径
python -m bangumi_exporter.cli --token xxx -o 我的收藏

# 只导出看过的动画
python -m bangumi_exporter.cli --type anime --status 2

# 通过代理
python -m bangumi_exporter.cli --proxy http://127.0.0.1:7890
```

> ⚠️ `--proxy` 单独使用不会触发导出，请至少再带一个导出参数
> （如 `--type anime`）或 `--serve`。

### 数据源管理
```bash
# 探测所有数据源并给出推荐（实测约 2.5 秒）
python -m bangumi_exporter.cli --list-sources

# 手动指定数据源
python -m bangumi_exporter.cli --source https://api.bgmapi.com

# 强制重新探测（忽略本地健康记录）
python -m bangumi_exporter.cli --probe-sources
```

### 增量 / 离线 / 时间过滤
```bash
# 只导出与上次相比有变化的条目（无变化则不生成文件）
python -m bangumi_exporter.cli --incremental

# 完全离线，用本地缓存重新生成文件
python -m bangumi_exporter.cli --offline -f excel

# 只导出 2026 年之后有更新的条目
python -m bangumi_exporter.cli --since 2026-01-01

# 只导出最近 7 天有更新的条目
python -m bangumi_exporter.cli --since 7d

# 跳过详情补取（更快，但「平台」列为空）
python -m bangumi_exporter.cli --no-details
```

### 高级分析 / 报告 / 自动化（v3.2）
```bash
# 一次拿到「全部格式 + 画像 + 推荐 + 可视化报告 + 归档快照 + 数据补全」
python -m bangumi_exporter.cli --type anime -f all --recommend --report --archive --supplement

# 数据补全（简介 / 制作公司 / staff / 声优 / 分集 / 播出星期 / 卷数）
python -m bangumi_exporter.cli -f excel --supplement
python -m bangumi_exporter.cli -f csv --supplement --supplement-limit 5   # 只补前 5 条试试

# 只要画像（本地计算，不额外联网）
python -m bangumi_exporter.cli -f excel --no-profile    # 关掉画像
python -m bangumi_exporter.cli -f excel                 # 默认就带画像

# 推荐 30 条
python -m bangumi_exporter.cli -f csv --recommend --recommend-limit 30

# 看历史快照 / 对比任意两次
python -m bangumi_exporter.cli --history
python -m bangumi_exporter.cli --compare 20261001-120000 20261002-230000

# 定时导出（每 30 分钟检查一次变化，有变化才写提醒）
python -m bangumi_exporter.cli --watch 30m

# 多账号
python -m bangumi_exporter.cli --token <TOKEN> --account 主号
python -m bangumi_exporter.cli --use-account 主号 -f excel
python -m bangumi_exporter.cli --accounts

# 备份 / 恢复（配置 + 账号 + 全部缓存）
python -m bangumi_exporter.cli --backup D:\备份
python -m bangumi_exporter.cli --restore D:\备份\bangumi_exporter_backup_20261002-231130.zip
```

### 原生 GUI
```bash
python -m bangumi_exporter.cli --gui
```

---

## 📦 功能详情

### 导出格式
- **CSV** — 通用表格格式
- **JSON** — 结构化数据
- **Excel (.xlsx)** — 纯标准库生成，无需 openpyxl
- **Markdown** — 可直接粘贴到文档
- **HTML** — 带搜索和排序的交互式表格

### 条目类型
- 动画（默认）
- 书籍
- 音乐
- 游戏
- 三次元

### 收藏状态过滤
- 想看
- 看过
- 在看
- 搁置
- 抛弃

### 仪表盘
- 总收藏数、BGM 均分、我的均分、看过/在看/想看统计
- 收藏状态分布（SVG 环图）
- 条目类型分布（横向柱图）
- BGM 评分分布（柱图）
- 我的评分分布（柱图）
- BGM 评分 Top 10
- 我的评分 Top 10
- 按放送年份分布（柱图）
- 我的标签 Top 15
- 平台分布（TV / OVA / 剧场版 / WEB）
- 我的评分 vs BGM 评分（平均分差 + 相关系数 + 双向榜单）
- 追番完成度（已看完 / 看了一部分 / 未开始）

### 数据表
- 封面图缩略图
- 条目名（点击跳转 bgm.tv）
- **23 列**：序号 / 条目类型 / 收藏类型 / 中文名 / 原名 / 我的评分 / BGM评分 /
  **评分人数** / 排名 / 看到第几集 / 总集数 / **卷数** / 放送日期 / **放送星期** /
  **平台** / **制作公司** / **条目标签** / **简介** / 我的短评 / 我的标签 /
  条目ID / **条目链接** / 更新时间
- 搜索（名称 / 短评 / 标签）
- 点击表头排序
- 状态过滤
- 复制 CSV 到剪贴板
- 「看到第几集」为 0 时显示为 `-`（0 表示还没记录进度，不是「看了 0 集」）

### 画像页（v3.2）
- **用户画像**：口味核心洞察、兴趣标签 Top 25 横条图、
  多样性指标卡（归一化熵 / 等效标签数 / 基尼系数 / Top5 集中度 / 平均集数 / 单季番占比）
- **个人评分模型**：岭回归系数与 R²（需要 ≥8 条评分）
- **猜你喜欢**：推荐卡片，含评分、排名、匹配度与「命中你的口味：…」原因
- **全站对比**：全站评分分布图、口碑最高 Top 15、我 vs 大众差异榜
- **数据体检**：逐列来源与判定表格，并在顶部提示哪些空列属于「你自己没填」

---

## ⚙️ 配置

配置保存在 `config.json`：

```json
{
  "token": "你的 Bangumi Access Token",
  "proxy": "http://127.0.0.1:7890",
  "subject_types": [2],
  "formats": ["excel"],
  "collection_types": [],
  "output": "C:\\Users\\...\\输出\\bangumi_export",
  "api_base": "",
  "source": "",
  "username": "",
  "enrich_details": true,
  "workers": 6
}
```

| 字段 | 说明 |
|---|---|
| `source` | 指定数据源，留空 = 每次自动选最快的可用源 |
| `username` | Bangumi 用户名，填了可跳过 `/v0/me` 身份识别 |
| `enrich_details` | 是否补取条目详情（`platform` 等），默认 `true` |
| `api_base` | 自定义 API 地址，优先级高于 `source` |

### Token 获取
1. 登录 [bangumi.tv](https://bgm.tv)
2. 进入 **设置 → App 授权**
3. 创建新应用，复制 Access Token

### Token 优先级
1. `--token` 命令行参数
2. 环境变量 `BANGUMI_TOKEN`
3. `config.json` 的 `token` 字段

---

## 📁 目录结构

```
banggumi/
├── 启动.bat                    # 双击启动（纯 ASCII，避免 cmd 编码问题）
├── config.json                 # 配置文件
├── README.md                   # 本文件
├── 说明.txt                    # 简明使用说明
├── src/
│   ├── webui.py                # 兼容入口（调用包）
│   ├── icon.ico                # 应用图标
│   └── bangumi_exporter/       # 主包
│       ├── __init__.py
│       ├── constants.py        # 常量 + 数据源注册表
│       ├── config.py           # 配置管理
│       ├── api.py              # HTTP 客户端
│       ├── sources.py          # 数据源探测/排序/熔断
│       ├── cache.py            # 评分缓存 + 完整数据缓存
│       ├── exporters.py        # 导出格式
│       ├── stats.py            # 统计报告
│       ├── diagnose.py         # 数据体检（每列为什么有值/没值）
│       ├── profile.py          # 用户画像 / 评分模型 / 智能推荐
│       ├── compare.py          # 全站对比（我的评分 vs 大众）
│       ├── history.py          # 快照归档与收藏变化对比
│       ├── schedule.py         # 定时导出与变更提醒
│       ├── accounts.py         # 多账号与备份/恢复
│       ├── report.py           # 单文件可视化 HTML 报告
│       ├── details.py          # 数据补全（简介/staff/声优/分集）
│       ├── engine.py           # 导出引擎
│       ├── server.py           # Web 服务
│       ├── ui.py               # SPA 前端
│       ├── cli.py              # 命令行入口
│       └── gui.py              # 原生 GUI
├── tools/
│   ├── tee_run.py              # 启动包装：控制台 + launch.log 双写
│   ├── bootstrap_pyinstaller.py
│   └── make_icon.py
└── 输出/                       # 导出结果
    ├── bangumi_export.xlsx
    ├── bangumi_export_报告.html  # 可视化报告（单文件，内联 SVG）
    ├── bangumi_export_详情.md    # 简介 / staff / 声优 / 分集（完整）
    ├── bangumi_export_详情.json  # 同上，结构化
    ├── bangumi_export_stats.md
    ├── 历史归档/                # 快照（对比收藏变化用）
    ├── 提醒.log                 # 定时导出的变更提醒
    ├── launch.log              # 启动日志
    ├── .detail_cache.json      # 详情补全缓存（只抓缺失的条目）
    ├── .rating_cache.json      # 评分/平台/打分直方图缓存
    ├── .data_cache.json        # 完整数据缓存（增量/离线导出用）
    └── .sources.json           # 数据源健康记录
```

---

## 🔧 技术细节

### 零依赖
- 纯 Python 标准库实现
- Excel 通过 zipfile 手写 XML 生成
- 图表使用纯 SVG（无 JS 库）

### HTTP 客户端
- 指数退避重试（429/5xx/网络错误）
- **多数据源并发探测 + 按延迟排序 + 熔断冷却**
- 鉴权能力区分（401 / 不支持鉴权 / 网络不通 三种错误分开报告）
- 代理支持
- 并发分页获取

### 进度报告
- 结构化 `Progress` 对象
- 阶段：auth → fetch → enrich → sort → export → stats → done
- 实时百分比 + 当前类型 + 已获取计数

### 取消支持
- `threading.Event` 控制
- 在 fetch / enrich 循环中检查取消标志
- 优雅中止

### 数据缓存
- `.rating_cache.json` — 评分 + 平台，按条目 ID 缓存（兼容 v3.0 的纯评分旧格式）
- `.data_cache.json` — 完整行数据，支持 `diff()` 差异计算与 `filter_since()` 时间过滤
- `.sources.json` — 数据源健康与熔断状态
- 全部为原子写入（先写临时文件再 `replace`），断电不会留下半个文件

---

## 📝 更新日志

### v3.2.0（大数据分析 + 报告 + 自动化）
新增模块（全部零依赖）：

| 模块 | 作用 |
|---|---|
| `diagnose.py` | 数据体检：逐列解释为什么有值/没值，区分「用户自有」与「官方缺失」 |
| `profile.py` | 用户画像：TF-IDF 兴趣权重、香农熵/归一化熵/等效标签数/基尼系数、品味洞察、岭回归评分模型、智能推荐 |
| `compare.py` | 全站对比：基于 `rating.count` 直方图，我的评分 vs 大众分布、分位、差异榜 |
| `history.py` | 快照归档与任意两次快照对比（新增/删除/修改） |
| `schedule.py` | 定时导出循环 + 变更提醒日志 |
| `accounts.py` | 多账号（Token 混淆存储）+ 配置/缓存 zip 备份恢复 |
| `report.py` | 单文件可视化 HTML 报告（内联 SVG，零外部依赖） |
| `details.py` | 数据补全：简介 / 制作公司 / staff / 声优 / 分集 / 播出星期 / 卷数（带增量缓存） |

其他：
- 表格字段从 17 列扩到 **23 列**，新增 **评分人数 / 平台 / 条目标签 / 卷数 /
  放送星期 / 制作公司 / 简介 / 条目链接**
- 统计报告新增「社区标签 Top 20」「数据体检」「全站对比」「用户画像」
  「各类型专门统计（书籍卷数 / 游戏平台 / 音乐曲目数）」「猜你喜欢」「条目详情」
- CLI 新增 `--profile --recommend --report --archive --supplement
  --history --compare --accounts --backup --restore --watch
  --account/--use-account/--del-account`
- Web UI 新增 **画像页**（画像 / 推荐 / 全站对比 / 数据体检）与历史快照对比面板
- 修复：`--help` 崩溃、离线模式拿不到评分直方图、`_percentile` 字符串键崩溃、
  画像标签排序依据错误

### v3.1.0（数据源 + 高级功能）
- ✨ **内置 5 个数据源并自动择优**：新增 Kazumi 同款鉴权镜像 `api.bgmapi.com`，
  并发探测 + 提前退出，实测 **2.5 秒**出结果
- ✨ **数据源熔断冷却**：连续失败 3 次的源进入指数退避（60s → 900s）
- ✨ **增量导出**（`--incremental`）：只导出新增 + 有变化的条目，无变化直接跳过
- ✨ **离线导出**（`--offline`）：断网用本地缓存重新生成任意格式
- ✨ **时间过滤**（`--since 2026-01-01` / `7d` / `24h`）
- ✨ **完整数据缓存** `.data_cache.json`：精确算出新增/变化/未变/删除
- ✨ **导出结果自检**：CSV 行数、JSON 可解析、xlsx zip 与工作表 XML 全部校验
- ✨ **高级统计**：放送年份/季度、标签 Top 20、平台分布、
  我的评分 vs BGM 评分（平均分差 + 皮尔逊相关系数 + 双向榜单）、追番完成度
- ✨ **数据源管理面板**：设置页可视化每个源的延迟/可用性/鉴权能力，可一键重测
- ✨ `--list-sources` / `--source` / `--probe-sources` / `--username` / `--no-details`
- 🐛 **修复「平台」列永远为空**：详情接口本就返回 `platform`，
  旧代码把整份响应用完即弃、只留评分；现在一次请求同时拿到评分与平台
  （实测 153/153 填充，平台分布 TV 125 / 剧场版 16 / OVA 11 / WEB 1）
- 🐛 **修复 Token 被误判失效**：旧逻辑拿不支持 `/v0/me` 的镜像去验 Token，
  于是**有效的 Token 也会被报「Token 无效或已过期」并直接中断导出**；
  现在区分 401 / 该源不支持鉴权 / 网络不通，仅在**所有**源都 401 时才报 Token 失效
- 🐛 **修复评分人数可能算错**：收藏接口内嵌的 `collection_total` 是收藏人数，
  与评分人数（`rating.total`）语义不同，新代码不再混用
- 🐛 **修复离线模式不计算差异**：`--offline --incremental` 现在与在线语义一致
  （缓存对自身 = 无变化 → 跳过，而不是无提示地全量导出）
- 🐛 **修复数据源健康状态不落盘**：失败次数与冷却列表以前既不保存也不读取，
  导致熔断只在单次进程内有效 —— 每次命令行导出都会重新去撞已知的坏源；
  现在状态原子写入 `.sources.json`（失败立即写盘，成功写盘节流）
- 🐛 **修复自检遇到非法路径直接抛异常**：自检本身绝不应该崩，
  现在把无效路径如实报告为「不通过」
- ⚡ 收藏接口内嵌的 `score`/`rank` 现在被直接利用，省掉大量无谓请求

### v3.0.1（修复版）
- 🐛 **修复代理完全不可用**：配置代理后请求会抛
  `AttributeError: 'OpenerDirector' object has no attribute 'urlopen'`，
  代理路径与直连路径现在分开处理
- 🐛 **修复 CSV 导出必然失败**：表格行含「封面 / 条目链接」两个额外字段，
  导致 `csv.DictWriter` 抛 `ValueError`，已显式忽略多余键
- 🐛 **修复启动.bat 无法启动**：原文用了 Windows 不存在的 `tee`，
  且 `cmd /c` 内嵌引号导致整段 `if` 块解析失败（退出码 255）；
  现已改为纯 ASCII 批处理 + `tools/tee_run.py` 双写日志
- 🐛 **修复 /api/test 泄漏 Token**：测试连接后会把该 Token 留在全局请求头里
- 🐛 **修复畸形请求导致连接被重置**：`subject_types` 等字段非法时
  现在返回明确的 JSON 错误，而不是抛异常断开连接
- 🐛 **修复仪表盘少算「搁置」**：进度统计现覆盖全部五种收藏状态
- 🐛 **修复镜像故障转移过慢**：不可达镜像会让启动等待数分钟，
  探测改为短超时（实测 280s → 22s）
- 🔒 **TLS 默认开启证书校验**：仅在证书链不完整时降级并告警
- ℹ️ **错误提示更准确**：区分「Token 无效（HTTP 401）」与「网络不通」
- 📄 文档与工具默认路径已同步（`说明.txt`、`make_icon.py`、
  `bootstrap_pyinstaller.py` 不再硬编码某台机器的绝对路径）

### v3.0.0（重构版）
- ✨ 全新现代 SPA 前端界面
- ✨ 仪表盘 + SVG 图表
- ✨ 数据表格（封面图 + 搜索 + 排序 + 过滤）
- ✨ 按收藏状态过滤
- ✨ 任务取消
- ✨ Token 测试连接
- ✨ 浏览器内下载
- ✨ 评分缓存
- 🏗️ 模块化包结构
- 🏗️ 三种运行模式

### v2.0（旧版）
- 基础导出功能
- 单文件 Web UI
- tkinter GUI

---

## 🩺 常见问题

**导出时提示「Token 无效或已过期」**
只有在**所有**数据源都返回 HTTP 401 时才会这样提示，此时 Token 确实失效了：
请到 bgm.tv → 设置 → App 授权 重新生成 Access Token 并填入。

**提示「无法连接任何 Bangumi 数据源」**
本机可能访问不了所有镜像（DNS 能解析但 TCP 443 超时是典型表现）。
先在「设置 → 数据源」点「重新探测」看每个源的实测结果；
若全部不可用，请在「设置 → HTTP 代理」填写代理地址（如 `http://127.0.0.1:7890`），
命令行可用 `--proxy`。也可以用 `--list-sources` 在终端里查看探测结果。

**「平台」列是空的**
平台字段只有条目详情接口才返回，需要开启「补全平台等详情」（默认开启）。
用了 `--no-details` 或离线导出时该列可能为空。

**增量导出说「没有任何变化，未生成文件」**
这是正常的：本地完整数据缓存与本次拉取结果完全一致，没有新增或变化的条目。
想强制生成完整文件就不要勾选增量导出。

**离线导出提示「缓存中没有数据」**
离线模式依赖 `.data_cache.json`，需要先联网成功导出一次以建立缓存。

**双击 启动.bat 没反应**
查看 `输出\launch.log`。若提示找不到 Python，请安装 Python 3.8+
并勾选 “Add Python to PATH”。

**CSV 用 Excel 打开是乱码**
CSV 以 UTF-8 BOM 写出，Excel 可直接识别；若仍乱码请改用 Excel(.xlsx) 格式。

---

## 📜 许可证

[MIT License](LICENSE) © 2026 weiguanquan

你可以自由使用、修改、分发、商用本项目，只需保留版权声明与许可证原文。
软件按「原样」提供，不附带任何担保。

---

## 🙏 致谢

- [Bangumi](https://bgm.tv) 提供 API
- [Kazumi](https://github.com/Predidit/Kazumi) 提供鉴权镜像 `api.bgmapi.com` 的参考
- 社区镜像：api.bgmapi.com / bgmapi.anibt.net / api.bgm.icu

---

**享受你的收藏导出之旅！** 🎉
