# -*- coding: utf-8 -*-
"""现代 SPA 前端界面（单文件 HTML/CSS/JS，零依赖）。

设计：
  - 左侧导航栏（导出 / 仪表盘 / 数据 / 设置）
  - 顶部状态栏（用户信息 + 运行状态徽章）
  - 真实结构化进度条（阶段 + 百分比 + 计数）
  - 纯 SVG 图表：收藏分布环图、评分分布柱图、Top 榜单
  - 数据表格：封面图、搜索、排序、状态过滤、直达 bgm.tv
"""

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bangumi 收藏导出工具</title>
<style>
:root{
  --bg:#0b0e13; --bg2:#11151d; --card:#151b26; --card2:#1a2130;
  --line:#232c3d; --line2:#2e3950;
  --txt:#e8edf4; --txt2:#9aa7b8; --txt3:#5d6a7d;
  --pink:#f09199; --pink2:#e07a86; --blue:#7aa2f7; --green:#3fb68b;
  --red:#f7768e; --yellow:#e5c07b; --purple:#bb9af7; --orange:#ff9e64;
  --radius:14px;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:"Microsoft YaHei","PingFang SC",-apple-system,"Segoe UI",sans-serif;
  background:var(--bg);color:var(--txt);overflow:hidden}
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-thumb{background:var(--line2);border-radius:4px}
::-webkit-scrollbar-track{background:transparent}

.app{display:flex;height:100vh}

/* ===== 侧边栏 ===== */
.sidebar{width:210px;background:var(--bg2);border-right:1px solid var(--line);
  display:flex;flex-direction:column;flex-shrink:0}
.logo{padding:20px 18px;display:flex;align-items:center;gap:10px;
  border-bottom:1px solid var(--line)}
.logo-icon{width:36px;height:36px;border-radius:10px;flex-shrink:0;
  background:linear-gradient(135deg,var(--pink),var(--blue));
  display:flex;align-items:center;justify-content:center;font-size:18px}
.logo-txt b{font-size:14px;display:block}
.logo-txt span{font-size:11px;color:var(--txt3)}
.nav{flex:1;padding:12px 10px;display:flex;flex-direction:column;gap:4px}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 12px;
  border-radius:9px;cursor:pointer;font-size:13.5px;color:var(--txt2);
  transition:.15s;user-select:none;border:1px solid transparent}
.nav-item:hover{background:var(--card);color:var(--txt)}
.nav-item.active{background:linear-gradient(135deg,rgba(240,145,153,.15),rgba(122,162,247,.12));
  border-color:rgba(240,145,153,.3);color:var(--txt);font-weight:600}
.nav-item .ico{width:18px;text-align:center;font-size:15px}
.nav-badge{margin-left:auto;font-size:10px;padding:2px 7px;border-radius:8px;
  background:var(--pink);color:#fff;display:none}
.nav-badge.on{display:inline-block}
.side-foot{padding:14px;border-top:1px solid var(--line);font-size:11px;color:var(--txt3)}
.side-foot .user{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.side-foot .user img{width:28px;height:28px;border-radius:50%;background:var(--card2)}
.side-foot .user b{font-size:12px;color:var(--txt2);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;max-width:110px}

/* ===== 主区域 ===== */
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.topbar{height:54px;border-bottom:1px solid var(--line);display:flex;
  align-items:center;padding:0 22px;gap:12px;background:var(--bg2);flex-shrink:0}
.topbar h1{font-size:15px;font-weight:600}
.badge{margin-left:auto;padding:5px 14px;border-radius:14px;font-size:12px;
  background:var(--card2);border:1px solid var(--line);color:var(--txt2);
  display:flex;align-items:center;gap:7px;white-space:nowrap}
.badge .dot{width:7px;height:7px;border-radius:50%;background:var(--txt3)}
.badge.run .dot{background:var(--blue);animation:pulse 1s infinite}
.badge.ok{color:var(--green);border-color:rgba(63,182,139,.3)} .badge.ok .dot{background:var(--green)}
.badge.err{color:var(--red);border-color:rgba(247,118,142,.3)} .badge.err .dot{background:var(--red)}
@keyframes pulse{50%{opacity:.3}}

.content{flex:1;overflow-y:auto;padding:22px}
.page{display:none;max-width:1180px;margin:0 auto}
.page.on{display:block}

/* ===== 卡片与控件 ===== */
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px;margin-bottom:16px}
.card h2{font-size:13px;color:var(--txt2);margin-bottom:14px;display:flex;
  align-items:center;gap:8px;font-weight:600;letter-spacing:.4px}
.card h2::before{content:"";width:5px;height:5px;border-radius:50%;background:var(--pink)}
.card h2 .hint{margin-left:auto;font-weight:400;font-size:11px;color:var(--txt3)}
label{font-size:12.5px;color:var(--txt2);display:block;margin:12px 0 6px}
label:first-of-type{margin-top:0}
input[type=text],input[type=password],input[type=number]{width:100%;
  background:var(--bg);border:1px solid var(--line);border-radius:9px;
  padding:10px 12px;color:var(--txt);font-size:13.5px;outline:none;transition:.15s;
  font-family:inherit}
input:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(122,162,247,.12)}
.row{display:flex;gap:10px;align-items:center}
.grow{flex:1}
.btn{padding:10px 20px;border-radius:9px;border:1px solid transparent;
  font-size:13.5px;cursor:pointer;transition:.15s;color:#fff;font-family:inherit;
  display:inline-flex;align-items:center;gap:7px;white-space:nowrap}
.btn.primary{background:linear-gradient(135deg,var(--pink),var(--pink2));font-weight:600;
  box-shadow:0 4px 14px rgba(240,145,153,.25)}
.btn.primary:hover{filter:brightness(1.08);transform:translateY(-1px)}
.btn.blue{background:linear-gradient(135deg,var(--blue),#5f8ae0);font-weight:600}
.btn.ghost{background:transparent;border-color:var(--line2);color:var(--txt2)}
.btn.ghost:hover{border-color:var(--blue);color:var(--txt)}
.btn.danger{background:transparent;border-color:rgba(247,118,142,.4);color:var(--red)}
.btn.danger:hover{background:rgba(247,118,142,.1)}
.btn:disabled{opacity:.45;cursor:not-allowed;transform:none!important}
.btn.sm{padding:6px 13px;font-size:12px;border-radius:7px}

.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{padding:8px 17px;border:1px solid var(--line2);border-radius:20px;
  cursor:pointer;font-size:13px;color:var(--txt2);background:transparent;
  transition:.15s;user-select:none;display:flex;align-items:center;gap:6px}
.chip:hover{border-color:var(--txt3);color:var(--txt)}
.chip .cdot{width:8px;height:8px;border-radius:50%}
.chip.active{color:#fff;font-weight:600}
.chip.active .cdot{box-shadow:0 0 6px currentColor}

/* ===== 进度 ===== */
.prog-wrap{display:none;margin-top:6px}
.prog-wrap.on{display:block}
.prog-head{display:flex;justify-content:space-between;font-size:12.5px;
  color:var(--txt2);margin-bottom:8px}
.prog-head b{color:var(--txt)}
.prog-bar{height:9px;background:var(--bg);border-radius:5px;overflow:hidden;
  border:1px solid var(--line)}
.prog-bar i{display:block;height:100%;width:0;border-radius:5px;
  background:linear-gradient(90deg,var(--pink),var(--blue));transition:width .4s}
.prog-bar.indet i{width:35%!important;animation:slide 1.1s linear infinite}
@keyframes slide{0%{margin-left:-35%}100%{margin-left:100%}}
.prog-stages{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
.pstage{font-size:11px;padding:4px 11px;border-radius:12px;background:var(--bg);
  border:1px solid var(--line);color:var(--txt3);transition:.2s}
.pstage.done{color:var(--green);border-color:rgba(63,182,139,.35)}
.pstage.now{color:var(--blue);border-color:rgba(122,162,247,.5);
  background:rgba(122,162,247,.08);font-weight:600}
.pstage.fail{color:var(--red);border-color:rgba(247,118,142,.4)}

/* ===== 控制台 ===== */
.console{background:#080b10;border:1px solid var(--line);border-radius:10px;
  padding:14px;font-family:Consolas,"Courier New",monospace;font-size:12px;
  line-height:1.75;height:250px;overflow-y:auto;white-space:pre-wrap;
  word-break:break-all;color:#8d9bad}
.console div.ok{color:var(--green)} .console div.err{color:var(--red)}
.console div.hl{color:var(--blue)}

/* ===== 文件结果 ===== */
.files{display:none;margin-top:14px}
.files.on{display:block}
.file{display:flex;align-items:center;gap:11px;padding:11px 14px;
  background:var(--card2);border:1px solid var(--line);border-radius:9px;
  margin-bottom:8px;font-size:12.5px}
.file .fico{width:30px;height:30px;border-radius:7px;display:flex;
  align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
.file .fname{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  font-family:Consolas,monospace;color:var(--txt2)}
.file .fsize{color:var(--txt3);font-size:11px;flex-shrink:0}

/* ===== 仪表盘 ===== */
.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:12px;margin-bottom:16px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px 18px;position:relative;overflow:hidden}
.stat::after{content:"";position:absolute;right:-18px;top:-18px;width:64px;height:64px;
  border-radius:50%;opacity:.09;background:var(--ac,var(--pink))}
.stat .sv{font-size:26px;font-weight:700;line-height:1.2;
  background:linear-gradient(135deg,var(--ac,var(--pink)),#fff8);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
.stat .sk{font-size:11.5px;color:var(--txt3);margin-top:3px}
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:900px){.chart-grid{grid-template-columns:1fr}}
.chart-box{background:var(--card);border:1px solid var(--line);
  border-radius:var(--radius);padding:18px}
.chart-box.wide{grid-column:1 / -1}
/* ---- 数据源列表 ---- */
.src-list{display:flex;flex-direction:column;gap:8px}
.src-row{display:flex;align-items:center;gap:12px;padding:10px 12px;
  background:var(--card2);border:1px solid var(--line);border-radius:10px;font-size:12.5px}
.src-row.best{border-color:rgba(63,182,139,.5);background:rgba(63,182,139,.07)}
.src-row .sr-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.src-row .sr-name{font-weight:600;min-width:110px}
.src-row .sr-base{color:var(--txt3);font-size:11.5px;flex:1;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.src-row .sr-ms{color:var(--txt2);width:60px;text-align:right;flex-shrink:0}
.src-row .sr-tag{font-size:10.5px;padding:2px 7px;border-radius:6px;
  background:var(--card);border:1px solid var(--line);color:var(--txt3);flex-shrink:0}
.src-note{margin-top:12px;font-size:11.5px;color:var(--txt3);line-height:1.8}
/* ---- 高级导出选项 ---- */
.adv-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.hbar{display:flex;align-items:center;gap:10px;margin:4px 0;font-size:13px}
.hbar .hl{flex:0 0 132px;text-align:right;color:var(--txt2);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.hbar .hb{flex:1;height:10px;background:var(--card);border:1px solid var(--line);
  border-radius:6px;overflow:hidden}
.hbar .hb i{display:block;height:100%;background:var(--blue);border-radius:6px}
.hbar .hv{flex:0 0 52px;color:var(--txt2);font-variant-numeric:tabular-nums}
.insights{margin:0 0 12px;padding-left:20px;line-height:1.9}
.insights li{color:var(--txt)}
table.mini{width:100%;border-collapse:collapse;font-size:13px}
table.mini th,table.mini td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}
table.mini th{color:var(--txt2);font-weight:600}
table.mini td:first-child{max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.warnbox{background:rgba(255,180,84,.1);border:1px solid rgba(255,180,84,.35);
  border-radius:8px;padding:10px 12px;margin-bottom:12px;font-size:13px;line-height:1.7}
.rec-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.rec{display:block;text-decoration:none;color:inherit;background:var(--card);
  border:1px solid var(--line);border-radius:10px;padding:12px 14px;transition:.15s}
.rec:hover{border-color:var(--blue);transform:translateY(-2px)}
.rec-top{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.rec-name{font-weight:600}
.rec-score{color:var(--green);font-weight:700}
.rec-meta{font-size:12px;color:var(--txt2);margin:5px 0 7px}
.rec-tags i{font-style:normal;font-size:11px;background:var(--bg);color:var(--txt2);
  border-radius:20px;padding:2px 8px;margin:0 4px 4px 0;display:inline-block}
.rec-why{font-size:11.5px;color:var(--txt2);margin-top:5px}
.tags .tag{display:inline-block;font-size:11px;background:var(--bg);color:var(--txt2);
  border-radius:4px;padding:1px 6px;margin:1px 3px 1px 0;white-space:nowrap}
td.sub{color:var(--txt2);font-size:12px}
.chk{display:flex;flex-direction:column;gap:3px;padding:10px 12px;
  background:var(--card2);border:1px solid var(--line);border-radius:10px;
  font-size:12.5px;cursor:pointer;margin:0}
.chk input{margin-right:6px;vertical-align:-1px}
.chk .hint2{font-size:11px;color:var(--txt3);padding-left:20px}
.delta-table{width:100%;font-size:12px;border-collapse:collapse}
.delta-table th{text-align:left;color:var(--txt3);font-weight:500;
  padding:6px 8px;border-bottom:1px solid var(--line)}
.delta-table td{padding:6px 8px;border-bottom:1px solid var(--line)}
.delta-table tr:last-child td{border-bottom:none}
.delta-pos{color:var(--green)}.delta-neg{color:var(--red)}
.chart-box h3{font-size:13px;color:var(--txt2);margin-bottom:14px;font-weight:600}
.legend{display:flex;flex-wrap:wrap;gap:8px 14px;margin-top:10px;font-size:11.5px;color:var(--txt2)}
.legend span{display:flex;align-items:center;gap:5px}
.legend i{width:9px;height:9px;border-radius:3px;display:inline-block}
.hbar{display:flex;align-items:center;gap:9px;margin-bottom:7px;font-size:12px}
.hbar .hb-k{width:34px;color:var(--txt2);text-align:right;flex-shrink:0}
.hbar .hb-t{flex:1;height:16px;background:var(--bg);border-radius:4px;overflow:hidden}
.hbar .hb-t i{display:block;height:100%;border-radius:4px;
  background:linear-gradient(90deg,var(--bc,var(--pink)),var(--bc2,var(--pink2)));
  transition:width .6s}
.hbar .hb-v{width:38px;color:var(--txt3);flex-shrink:0}
.toplist{counter-reset:t}
.toplist li{display:flex;align-items:center;gap:10px;padding:7px 4px;
  border-bottom:1px solid var(--line);font-size:12.5px;list-style:none}
.toplist li:last-child{border-bottom:none}
.toplist .rank{width:20px;height:20px;border-radius:6px;background:var(--card2);
  display:flex;align-items:center;justify-content:center;font-size:11px;
  color:var(--txt3);flex-shrink:0;font-weight:700}
.toplist li:nth-child(1) .rank{background:rgba(229,192,123,.18);color:var(--yellow)}
.toplist li:nth-child(2) .rank{background:rgba(154,167,184,.15);color:#c3ccd9}
.toplist li:nth-child(3) .rank{background:rgba(255,158,100,.14);color:var(--orange)}
.toplist .tn{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.toplist .tv{color:var(--pink);font-weight:700;font-family:Consolas,monospace}
.empty{color:var(--txt3);font-size:13px;text-align:center;padding:40px 0}

/* ===== 数据表格 ===== */
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.toolbar input{width:250px}
.fchip{padding:6px 13px;border:1px solid var(--line2);border-radius:16px;
  cursor:pointer;font-size:12px;color:var(--txt2);background:transparent;
  transition:.15s;user-select:none}
.fchip:hover{border-color:var(--txt3)}
.fchip.active{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:600}
.tbl-wrap{background:var(--card);border:1px solid var(--line);
  border-radius:var(--radius);overflow:auto;max-height:calc(100vh - 220px)}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th{position:sticky;top:0;background:var(--card2);color:var(--txt2);
  padding:10px 12px;text-align:left;font-weight:600;cursor:pointer;
  user-select:none;white-space:nowrap;border-bottom:1px solid var(--line);z-index:2}
th:hover{color:var(--txt)}
th .arr{opacity:.35;font-size:10px;margin-left:3px}
th.sorted .arr{opacity:1;color:var(--blue)}
td{padding:8px 12px;border-bottom:1px solid var(--line);color:var(--txt2);
  white-space:nowrap;max-width:260px;overflow:hidden;text-overflow:ellipsis}
tr:hover td{background:rgba(122,162,247,.045)}
td.cover img{width:34px;height:46px;object-fit:cover;border-radius:4px;
  background:var(--card2);display:block}
td.title a{color:var(--txt);text-decoration:none;font-weight:600}
td.title a:hover{color:var(--blue)}
td.title .sub{display:block;font-size:11px;color:var(--txt3);font-weight:400;
  max-width:220px;overflow:hidden;text-overflow:ellipsis}
.tchip{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;
  border-radius:11px;font-size:11px;font-weight:600}
.score{font-weight:700;font-family:Consolas,monospace}
.score.hi{color:var(--green)} .score.mid{color:var(--yellow)} .score.lo{color:var(--red)}
.mine{color:var(--pink);font-weight:700;font-family:Consolas,monospace}
.tbl-foot{display:flex;justify-content:space-between;font-size:12px;
  color:var(--txt3);padding:10px 4px 0}

/* ===== 设置页 ===== */
.set-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:860px){.set-grid{grid-template-columns:1fr}}
.kv{display:flex;justify-content:space-between;padding:8px 0;
  border-bottom:1px solid var(--line);font-size:12.5px}
.kv:last-child{border-bottom:none}
.kv b{color:var(--txt2);font-weight:400}
.toast{position:fixed;bottom:26px;left:50%;transform:translateX(-50%) translateY(80px);
  background:var(--card2);border:1px solid var(--line2);color:var(--txt);
  padding:11px 22px;border-radius:10px;font-size:13px;transition:.3s;opacity:0;
  z-index:99;box-shadow:0 8px 30px rgba(0,0,0,.5)}
.toast.on{transform:translateX(-50%) translateY(0);opacity:1}
.toast.ok{border-color:rgba(63,182,139,.5)} .toast.err{border-color:rgba(247,118,142,.5)}
</style>
</head>
<body>
<div class="app">
  <!-- 侧边栏 -->
  <aside class="sidebar">
    <div class="logo">
      <div class="logo-icon">📺</div>
      <div class="logo-txt"><b>Bangumi 导出</b><span>Collection Exporter v3</span></div>
    </div>
    <nav class="nav">
      <div class="nav-item active" data-page="export"><span class="ico">🚀</span>导出<span class="nav-badge" id="navBadge">NEW</span></div>
      <div class="nav-item" data-page="dash"><span class="ico">📊</span>仪表盘</div>
      <div class="nav-item" data-page="data"><span class="ico">📋</span>数据表</div>
      <div class="nav-item" data-page="logs"><span class="ico">📜</span>日志</div>
      <div class="nav-item" data-page="profile"><span class="ico">🧠</span>画像</div>
      <div class="nav-item" data-page="settings"><span class="ico">⚙️</span>设置</div>
    </nav>
    <div class="side-foot">
      <div class="user" id="userBox" style="display:none">
        <img id="userAvatar" src="" alt="">
        <b id="userName"></b>
      </div>
      <div id="mirrorInfo">镜像: 未连接</div>
    </div>
  </aside>

  <!-- 主区域 -->
  <div class="main">
    <div class="topbar">
      <h1 id="pageTitle">导出收藏</h1>
      <div class="badge" id="badge"><span class="dot"></span><span id="badgeTxt">就绪</span></div>
    </div>
    <div class="content">

      <!-- ============ 导出页 ============ -->
      <div class="page on" id="page-export">
        <div class="card">
          <h2>Access Token<span class="hint">bangumi.tv → 设置 → App 授权 获取</span></h2>
          <div class="row">
            <input class="grow" type="password" id="token" placeholder="粘贴你的 Bangumi Access Token" autocomplete="off">
            <button class="btn ghost" id="toggleBtn">👁 显示</button>
            <button class="btn ghost" id="testBtn">🔗 测试连接</button>
          </div>
        </div>

        <div class="card">
          <h2>导出设置</h2>
          <label>条目类型（可多选）</label>
          <div class="chips" id="typeChips"></div>
          <label>导出格式（可多选）</label>
          <div class="chips" id="fmtChips"></div>
          <label>收藏状态过滤（不选 = 全部）</label>
          <div class="chips" id="statusChips"></div>
          <label style="margin-top:18px">高级（增量 / 过滤）</label>
          <div class="adv-grid">
            <label class="chk"><input type="checkbox" id="optIncremental"> 增量导出
              <span class="hint2">只导出与上次相比有变化的条目</span></label>
            <label class="chk"><input type="checkbox" id="optDetails" checked> 补全平台等详情
              <span class="hint2">多花几秒，但「平台」列不会为空</span></label>
            <label class="chk"><input type="checkbox" id="optOffline"> 离线模式
              <span class="hint2">不联网，用本地缓存重新生成文件</span></label>
          </div>

          <label style="margin-top:18px">高级分析（v3.2 新功能）</label>
          <div class="adv-grid">
            <label class="chk"><input type="checkbox" id="optProfile" checked> 用户画像
              <span class="hint2">TF-IDF 兴趣标签、香农熵、基尼系数、口味洞察</span></label>
            <label class="chk"><input type="checkbox" id="optRecommend"> 智能推荐
              <span class="hint2">按画像检索候选并排序，需联网，约 10~20 秒</span></label>
            <label class="chk"><input type="checkbox" id="optReport"> 可视化 HTML 报告
              <span class="hint2">单文件、内联 SVG 图表，断网也能打开</span></label>
            <label class="chk"><input type="checkbox" id="optArchive"> 归档本次快照
              <span class="hint2">供以后对比「收藏变化」，建议开启</span></label>
            <label class="chk"><input type="checkbox" id="optSupplement"> 数据补全
              <span class="hint2">简介 / 制作公司 / staff / 声优 / 分集 / 播出星期 / 卷数
              （首次较慢，之后走缓存）</span></label>
          </div>
          <div class="row" style="margin-top:10px">
            <label class="chk" style="max-width:220px">推荐条数
              <input type="number" id="optRecLimit" value="20" min="1" max="100"
                     style="width:80px;margin-left:6px"></label>
            <button class="btn ghost" id="histBtn">🕘 历史快照 / 对比变化</button>
            <button class="btn ghost" id="repBtn">🌐 打开可视化报告</button>
          </div>
          <div id="histBox" style="display:none;margin-top:10px"></div>
          <div class="row" style="margin-top:10px">
            <input class="grow" type="text" id="optSince"
                   placeholder="只导出此时间之后有更新的条目，如 2026-01-01 或 7d（留空 = 全部）">
          </div>
        </div>

        <div class="card">
          <h2>开始导出</h2>
          <div class="row">
            <button class="btn primary" id="startBtn">🚀 开始导出</button>
            <button class="btn danger" id="cancelBtn" style="display:none">✕ 取消</button>
            <button class="btn ghost" id="openDirBtn">📂 打开输出目录</button>
            <button class="btn ghost" id="quitBtn">⏻ 退出程序</button>
          </div>
          <div class="prog-wrap" id="progWrap">
            <div class="prog-head">
              <span id="progStage">准备中...</span>
              <b id="progPct">0%</b>
            </div>
            <div class="prog-bar" id="progBar"><i id="progFill"></i></div>
            <div class="prog-stages" id="progStages"></div>
          </div>
          <div class="files" id="filesBox">
            <label style="margin-top:16px">生成的文件</label>
            <div id="fileList"></div>
          </div>
        </div>

        <div class="card">
          <h2>实时日志<span class="hint" id="logCount"></span></h2>
          <div class="console" id="console">等待启动...</div>
        </div>
      </div>

      <!-- ============ 仪表盘 ============ -->
      <div class="page" id="page-dash">
        <div id="dashEmpty" class="card"><div class="empty">还没有数据 —— 先在「导出」页完成一次导出 🚀</div></div>
        <div id="dashBody" style="display:none">
          <div class="stat-grid" id="statGrid"></div>
          <div class="chart-grid">
            <div class="chart-box"><h3>收藏状态分布</h3><div id="donutBox"></div></div>
            <div class="chart-box"><h3>条目类型分布</h3><div id="typeBarBox"></div></div>
            <div class="chart-box"><h3>BGM 评分分布</h3><div id="bgmDistBox"></div></div>
            <div class="chart-box"><h3>我的评分分布</h3><div id="myDistBox"></div></div>
            <div class="chart-box"><h3>🏆 BGM 评分 Top 10</h3><ol class="toplist" id="topBgm"></ol></div>
            <div class="chart-box"><h3>💖 我的评分 Top 10</h3><ol class="toplist" id="topMine"></ol></div>
            <div class="chart-box wide"><h3>📅 按放送年份</h3><div id="yearBox"></div></div>
            <div class="chart-box"><h3>🏷 我的标签 Top 15</h3><div id="tagBox"></div></div>
            <div class="chart-box"><h3>📺 平台分布</h3><div id="platformBox"></div></div>
            <div class="chart-box wide" id="ratingBox">
              <h3>⚖️ 我的评分 vs BGM 评分</h3>
              <div id="ratingDelta"></div>
            </div>
            <div class="chart-box wide"><h3>✅ 追番完成度</h3><div id="completionBox"></div></div>
          </div>
        </div>
      </div>

      <!-- ============ 数据表 ============ -->
      <div class="page" id="page-data">
        <div id="dataEmpty" class="card"><div class="empty">还没有数据 —— 先在「导出」页完成一次导出 🚀</div></div>
        <div id="dataBody" style="display:none">
          <div class="toolbar">
            <input type="text" id="searchBox" placeholder="🔍 搜索名称 / 短评 / 标签...">
            <div class="chips" id="dataFilters"></div>
            <button class="btn ghost sm" id="copyCsvBtn">📄 复制 CSV</button>
          </div>
          <div class="tbl-wrap">
            <table id="dataTable">
              <thead><tr id="dataHead"></tr></thead>
              <tbody id="dataBodyRows"></tbody>
            </table>
          </div>
          <div class="tbl-foot"><span id="dataCount"></span><span id="dataHint">点击表头排序</span></div>
        </div>
      </div>

      <!-- ============ 日志页 ============ -->
      <div class="page" id="page-logs">
        <div class="card">
          <h2>完整日志<span class="hint"><a href="javascript:void(0)" id="clearLogBtn" style="color:var(--blue);text-decoration:none">清空</a></span></h2>
          <div class="console" id="console2" style="height:calc(100vh - 190px)">等待启动...</div>
        </div>
      </div>

      <!-- ============ 画像页 ============ -->
      <div class="page" id="page-profile">
        <div id="profEmpty" class="card"><div class="empty">
          还没有画像数据 —— 先在「导出」页勾选「用户画像」并完成一次导出 🧠</div></div>
        <div id="profBody" style="display:none">
          <div class="card">
            <h2>用户画像<span class="hint">TF-IDF 兴趣权重 · 香农熵 · 基尼系数</span></h2>
            <div id="profInsights"></div>
            <div class="stat-grid" id="profMetrics"></div>
          </div>
          <div class="card">
            <h2>兴趣标签 Top 25</h2>
            <div id="profTags"></div>
          </div>
          <div class="card" id="profModelCard" style="display:none">
            <h2>个人评分模型<span class="hint">岭回归拟合你的打分偏好</span></h2>
            <div id="profModel"></div>
          </div>
          <div class="card" id="recCard" style="display:none">
            <h2>猜你喜欢<span class="hint">热度检索 + 口碑过滤 + 画像相似度</span></h2>
            <div id="recBox"></div>
          </div>
          <div class="card" id="vsCard" style="display:none">
            <h2>全站对比<span class="hint">我的口味 vs 大众分布</span></h2>
            <div id="vsInsights"></div>
            <div class="stat-grid" id="vsMetrics"></div>
            <h3 style="margin:14px 0 8px">你收藏条目的全站评分分布</h3>
            <div id="vsHist"></div>
            <div id="vsTable"></div>
          </div>
          <div class="card" id="diagCard" style="display:none">
            <h2>数据体检<span class="hint">每一列为什么有值 / 没值</span></h2>
            <div id="diagBox"></div>
          </div>
        </div>
      </div>

      <!-- ============ 设置页 ============ -->
      <div class="page" id="page-settings">
        <div class="card">
          <h2>数据源
            <span class="hint">
              <a href="javascript:void(0)" id="probeBtn" style="color:var(--blue);text-decoration:none">重新探测</a>
              <span id="probeState"></span>
            </span>
          </h2>
          <div class="src-list" id="srcList"><div class="empty">正在加载数据源...</div></div>
          <label style="margin-top:14px">手动指定数据源（留空 = 自动选最快的可用源）</label>
          <div class="row">
            <select class="grow" id="setSource"><option value="">自动（推荐）</option></select>
            <button class="btn ghost" id="applySourceBtn">应用</button>
          </div>
          <div class="src-note" id="srcNote"></div>
        </div>

        <div class="set-grid">
          <div class="card">
            <h2>网络与路径</h2>
            <label>HTTP 代理（国内网络常需，如 http://127.0.0.1:7890）</label>
            <input type="text" id="setProxy" placeholder="留空 = 直连">
            <label>输出文件基础名（自动附加扩展名）</label>
            <input type="text" id="setOutput" placeholder="输出路径">
            <label>自定义 API 地址（留空 = 用上面的数据源列表）</label>
            <input type="text" id="setMirror" placeholder="https://api.bgmapi.com">
            <label>Bangumi 用户名（可选，用于跳过身份识别）</label>
            <input type="text" id="setUsername" placeholder="留空 = 用 Token 自动识别">
            <label>补取详情并发数：<b id="wkVal" style="color:var(--pink)">6</b></label>
            <input type="range" id="setWorkers" min="1" max="16" value="6" style="width:100%">
            <div class="row" style="margin-top:16px">
              <button class="btn blue" id="saveSetBtn">💾 保存设置</button>
            </div>
          </div>
          <div class="card">
            <h2>缓存与运行时</h2>
            <div class="kv"><b>评分/详情缓存</b><span id="cacheCount">-</span></div>
            <div class="kv"><b>完整数据缓存</b><span id="dataCacheCount">-</span></div>
            <div class="kv"><b>缓存时间</b><span id="dataCacheAt">-</span></div>
            <div class="kv"><b>输出目录</b><span id="outDirInfo" style="max-width:220px;overflow:hidden;text-overflow:ellipsis">-</span></div>
            <div class="kv"><b>程序版本</b><span id="verInfo">-</span></div>
            <div class="row" style="margin-top:16px">
              <button class="btn ghost" id="clearCacheBtn">🗑 清空评分缓存</button>
              <button class="btn ghost" id="clearDataBtn">🗑 清空数据缓存</button>
            </div>
            <div style="margin-top:22px;font-size:12px;color:var(--txt3);line-height:1.8">
              💡 提示：<br>
              · Token 保存在本地 config.json，请勿分享给他人<br>
              · 评分缓存让二次导出跳过已缓存条目的网络请求<br>
              · 完整数据缓存是「增量导出 / 离线导出」的基础<br>
              · 数据源会自动探测并按实测延迟排序，坏源会被熔断
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
"use strict";
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
const SUBJECT_TYPES=__SUBJECT_TYPES__;
const FORMATS=__FORMATS__;
const STATUS_OPTIONS=__STATUS_OPTIONS__;
const FMT_COLORS={csv:"#9ece6a",json:"#e5c07b",excel:"#3fb68b",markdown:"#7aa2f7",html:"#f09199"};
const STATUS_COLORS={"在看":"#7aa2f7","想看":"#e5c07b","看过":"#3fb68b","搁置":"#9aa7b8","抛弃":"#f7768e"};

let after=0, wasRunning=false, logLines=0;
let RESULT=null;              // {rows, charts, files, user, ...}
let tblSort={key:"序号",asc:true}, tblFilter="", tblStatus="全部";

function api(path,opt){return fetch(path,opt).then(r=>r.json())}
function get(path){return api(path)}
function post(path,body){return api(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})})}
function toast(msg,cls){const t=$("#toast");t.textContent=msg;t.className="toast on "+(cls||"");
  clearTimeout(t._h);t._h=setTimeout(()=>t.className="toast",2600)}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function fmtSize(n){if(n==null)return"";if(n<1024)return n+" B";if(n<1048576)return (n/1024).toFixed(1)+" KB";return (n/1048576).toFixed(2)+" MB"}

/* ===== 导航 ===== */
const PAGE_TITLES={export:"导出收藏",dash:"数据仪表盘",data:"收藏数据表",profile:"用户画像",logs:"运行日志",settings:"设置"};
$$(".nav-item").forEach(n=>n.onclick=()=>{
  $$(".nav-item").forEach(x=>x.classList.remove("active"));
  n.classList.add("active");
  const p=n.dataset.page;
  $$(".page").forEach(x=>x.classList.remove("on"));
  $("#page-"+p).classList.add("on");
  $("#pageTitle").textContent=PAGE_TITLES[p];
  $("#navBadge").classList.remove("on");
});

/* ===== 构建 chips ===== */
function buildChips(){
  $("#typeChips").innerHTML=Object.values(SUBJECT_TYPES).map(t=>
    `<div class="chip" data-code="${t.code}" data-color="${t.color}"><span class="cdot" style="background:${t.color}"></span>${t.name}</div>`).join("");
  $("#fmtChips").innerHTML=Object.entries(FORMATS).map(([k,label])=>
    `<div class="chip" data-fmt="${k}"><span class="cdot" style="background:${FMT_COLORS[k]}"></span>${label}</div>`).join("");
  $("#statusChips").innerHTML=STATUS_OPTIONS.map(s=>
    `<div class="chip" data-st="${s.code}"><span class="cdot" style="background:${STATUS_COLORS[s.name]}"></span>${s.name}</div>`).join("");
  $("#dataFilters").innerHTML=["全部",...STATUS_OPTIONS.map(s=>s.name)].map(s=>
    `<div class="fchip${s==="全部"?" active":""}" data-f="${s}">${s}</div>`).join("");

  $$("#typeChips .chip,#fmtChips .chip,#statusChips .chip").forEach(c=>c.onclick=()=>{
    const on=c.classList.toggle("active");
    if(on){const col=c.dataset.color||FMT_COLORS[c.dataset.fmt]||"#7aa2f7";
      c.style.background=col+"26";c.style.borderColor=col;}
    else{c.style.background="";c.style.borderColor="";}
  });
  $$("#dataFilters .fchip").forEach(c=>c.onclick=()=>{
    $$("#dataFilters .fchip").forEach(x=>x.classList.remove("active"));
    c.classList.add("active");tblStatus=c.dataset.f;renderTable();
  });
}

function selectedTypes(){return $$("#typeChips .chip.active").map(c=>+c.dataset.code)}
function selectedFormats(){return $$("#fmtChips .chip.active").map(c=>c.dataset.fmt)}
function selectedStatuses(){return $$("#statusChips .chip.active").map(c=>+c.dataset.st)}

/* ===== Token 显示切换 ===== */
$("#toggleBtn").onclick=()=>{const t=$("#token");
  t.type=t.type==="password"?"text":"password";
  $("#toggleBtn").textContent=t.type==="password"?"👁 显示":"🙈 隐藏";};

/* ===== 测试连接 ===== */
$("#testBtn").onclick=async()=>{
  const tk=$("#token").value.trim();
  if(!tk)return toast("请先填写 Token","err");
  $("#testBtn").disabled=true;$("#testBtn").textContent="⏳ 测试中...";
  try{
    const j=await post("/api/test",{token:tk,proxy:$("#setProxy").value.trim()});
    if(j.ok){toast("✓ 连接成功："+j.nickname,"ok");showUser(j.user);}
    else toast("✗ "+(j.error||"连接失败"),"err");
  }catch(e){toast("请求失败："+e,"err")}
  $("#testBtn").disabled=false;$("#testBtn").textContent="🔗 测试连接";
};

function showUser(u){
  if(!u||!u.id)return;
  $("#userBox").style.display="flex";
  $("#userName").textContent=u.nickname||u.username||u.id;
  if(u.avatar)$("#userAvatar").src=u.avatar;
}

/* ===== 开始导出 ===== */
$("#startBtn").onclick=()=>{
  const token=$("#token").value.trim();
  const offline=$("#optOffline").checked;
  if(!token&&!offline)return toast("请填写 Token（离线模式可留空）","err");
  const types=selectedTypes(),fmts=selectedFormats();
  if(!types.length)return toast("请至少选择一个条目类型","err");
  if(!fmts.length)return toast("请至少选择一个导出格式","err");
  $("#filesBox").classList.remove("on");
  post("/api/export",{token,subject_types:types,formats:fmts,
    collection_types:selectedStatuses(),
    proxy:$("#setProxy").value.trim(),
    output:$("#setOutput").value.trim(),
    api_base:$("#setMirror").value.trim(),
    username:$("#setUsername").value.trim(),
    source:$("#setSource").value,
    since:$("#optSince").value.trim(),
    incremental:$("#optIncremental").checked,
    offline:offline,
    enrich_details:$("#optDetails").checked,
    profile:$("#optProfile").checked,
    recommend:$("#optRecommend").checked,
    recommend_limit:+($("#optRecLimit").value||20),
    report:$("#optReport").checked,
    archive:$("#optArchive").checked,
    supplement:$("#optSupplement").checked,
    workers:+$("#setWorkers").value}).then(j=>{
    if(j.error)toast(j.error,"err");
    else{setRunning(true);wasRunning=true;switchPage("export");}
  });
};

/* ===== 历史快照 / 对比变化 ===== */
$("#histBtn").onclick=()=>{
  const box=$("#histBox");
  if(box.style.display==="block"){box.style.display="none";return}
  get("/api/snapshots").then(j=>{
    if(!j||j.error)return toast((j&&j.error)||"读取失败","err");
    box.style.display="block";
    if(!j.count){box.innerHTML='<div class="hint2">还没有历史快照。勾选「归档本次快照」导出一次即可建立基线。</div>';return}
    const opts=j.snapshots.map(s=>`<option value="${esc(s.id)}">${esc(s.saved_at_str)} · ${s.count} 条</option>`).join("");
    let html=`<div class="row"><select id="snapA" class="grow">${opts}</select>
      <select id="snapB" class="grow">${opts}</select>
      <button class="btn ghost" id="doCmp">对比</button></div>
      <div class="hint2" style="margin-top:6px">共 ${j.count} 份快照（左=旧，右=新）</div><div id="cmpOut"></div>`;
    box.innerHTML=html;
    if(j.snapshots.length>1)$("#snapB").value=j.snapshots[0].id,$("#snapA").value=j.snapshots[1].id;
    $("#doCmp").onclick=()=>{
      const a=$("#snapA").value,b=$("#snapB").value;
      get(`/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`).then(d=>{
        if(!d||d.error)return toast((d&&d.error)||"对比失败","err");
        const df=d.diff;
        const li=(arr,fn,lim=15)=>arr.length?`<ul class="hint2" style="max-height:180px;overflow:auto;padding-left:18px">${arr.slice(0,lim).map(fn).join("")}</ul><div class="hint2">共 ${arr.length} 条</div>`:'<div class="hint2">无</div>';
        $("#cmpOut").innerHTML=`
          <div class="stat-grid" style="margin-top:10px">
            <div class="stat" style="--ac:var(--ok)"><div class="sv">${df.added.length}</div><div class="sk">新增</div></div>
            <div class="stat" style="--ac:var(--err)"><div class="sv">${df.removed.length}</div><div class="sk">删除</div></div>
            <div class="stat" style="--ac:var(--warn)"><div class="sv">${df.changed.length}</div><div class="sk">修改</div></div>
            <div class="stat" style="--ac:var(--txt2)"><div class="sv">${df.unchanged}</div><div class="sk">未变</div></div>
          </div>
          <div style="margin-top:10px"><b>新增</b>${li(df.added,r=>`<li>${esc(r["中文名"]||r["原名"]||"")}（${esc(r["收藏类型"]||"")}）</li>`)}</div>
          <div><b>删除</b>${li(df.removed,r=>`<li>${esc(r["中文名"]||r["原名"]||"")}</li>`)}</div>
          <div><b>修改</b>${li(df.changed,c=>`<li>${esc(c.name)}：${c.fields.map(f=>esc(f.field+" "+f.from+" → "+f.to)).join("；")}</li>`,10)}</div>`;
      });
    };
  });
};
$("#repBtn").onclick=()=>{
  if(!RESULT)return toast("请先导出一次","err");
  const f=(RESULT.files||[]).find(x=>/报告\.html$/.test(x.path||""));
  if(!f)return toast("本次没有生成报告：请勾选「可视化 HTML 报告」再导出","err");
  window.open("/api/download?i="+(RESULT.files||[]).indexOf(f),"_blank");
};

$("#cancelBtn").onclick=()=>post("/api/cancel").then(()=>toast("已请求取消..."));
$("#openDirBtn").onclick=()=>post("/api/open-dir").then(j=>{if(j.error)toast(j.error,"err")});
$("#quitBtn").onclick=()=>{if(confirm("确定退出程序？"))post("/api/quit").then(()=>window.close())};

function switchPage(p){const n=$$(".nav-item").find(x=>x.dataset.page===p);if(n)n.onclick();}

/* ===== 运行状态 ===== */
const STAGES=[["auth","验证身份"],["fetch","拉取收藏"],["enrich","补全评分"],["sort","整理数据"],["export","写入文件"],["stats","生成统计"],["done","完成"]];
function setRunning(run){
  $("#progWrap").classList.toggle("on",run||$("#progWrap").classList.contains("on"));
  $("#startBtn").disabled=run;
  $("#cancelBtn").style.display=run?"inline-flex":"none";
  $("#badge").className="badge"+(run?" run":"");
  $("#badgeTxt").textContent=run?"导出中...":"就绪";
}
function renderProgress(p){
  if(!p||p.stage==="idle")return;
  $("#progWrap").classList.add("on");
  $("#progStage").innerHTML=p.stage==="fetch"&&p.current_type
    ?`正在拉取「<b style="color:var(--pink)">${esc(p.current_type)}</b>」收藏（已获取 ${p.items_fetched} 条）`
    :esc(p.stage_label||p.message||"");
  $("#progPct").textContent=Math.round(p.percent)+"%";
  const bar=$("#progBar");
  bar.classList.toggle("indet",p.percent<=0&&p.stage!=="done"&&p.stage!=="error");
  $("#progFill").style.width=Math.max(p.percent,0)+"%";
  const idx=STAGES.findIndex(s=>s[0]===p.stage);
  $("#progStages").innerHTML=STAGES.map((s,i)=>{
    let cls="pstage";
    if(p.stage==="error"){cls+=i<=idx?" fail":""}
    else if(p.stage==="done"){cls+=" done"}
    else if(i<idx)cls+=" done";else if(i===idx)cls+=" now";
    return `<span class="${cls}">${s[1]}</span>`}).join("");
}

/* ===== 日志 ===== */
function appendLog(lines){
  if(!lines.length)return;
  logLines+=lines.length;
  $("#logCount").textContent=logLines+" 行";
  ["#console","#console2"].forEach(sel=>{
    const con=$(sel);
    if(con.textContent.includes("等待启动"))con.innerHTML="";
    const frag=document.createDocumentFragment();
    lines.forEach(l=>{
      const d=document.createElement("div");
      d.textContent=l;
      if(/错误|失败|取消/.test(l))d.className="err";
      else if(/完成|成功|已导出/.test(l))d.className="ok";
      else if(/^===/.test(l))d.className="hl";
      frag.appendChild(d);
    });
    con.appendChild(frag);
    while(con.children.length>2000)con.removeChild(con.firstChild);
    con.scrollTop=con.scrollHeight;
  });
}
$("#clearLogBtn").onclick=()=>{$("#console2").innerHTML="";logLines=0;$("#logCount").textContent=""};

/* ===== 文件结果 ===== */
function showFiles(files){
  const box=$("#filesBox"),list=$("#fileList");
  if(!files||!files.length){box.classList.remove("on");return}
  const ICONS={csv:["📗","#9ece6a"],json:["📘","#e5c07b"],xlsx:["📊","#3fb68b"],md:["📝","#7aa2f7"],html:["🌐","#f09199"]};
  list.innerHTML=files.map((f,i)=>{
    const ext=(f.name||"").split(".").pop().toLowerCase();
    const [ic,col]=ICONS[ext]||["📄","#9aa7b8"];
    return `<div class="file"><div class="fico" style="background:${col}22;color:${col}">${ic}</div>
      <div class="fname" title="${esc(f.path)}">${esc(f.name)}</div>
      <div class="fsize">${fmtSize(f.size)}</div>
      <a class="btn ghost sm" href="/api/download?i=${i}" download>⬇ 下载</a></div>`}).join("");
  box.classList.add("on");
  $("#navBadge").classList.add("on");
}

/* ===== 轮询 ===== */
function poll(){
  api("/api/logs?after="+after).then(j=>{after=j.next||after;appendLog(j.logs||[])}).catch(()=>{});
  api("/api/status").then(s=>{
    renderProgress(s.progress);
    if(s.running){wasRunning=true;setRunning(true)}
    else if(wasRunning){
      wasRunning=false;setRunning(false);
      const b=$("#badge");
      if(s.cancelled){b.className="badge err";$("#badgeTxt").textContent="已取消"}
      else if(s.skipped&&s.ok){b.className="badge ok";
        $("#badgeTxt").textContent="✓ 增量导出：无变化";toast("与上次相比没有任何变化，未生成文件")}
      else if(s.ok){
        b.className="badge ok";
        const d=s.diff||{};
        const extra=(d.added||d.changed)
          ? ` · 新增 ${d.added||0} / 变化 ${d.changed||0}` : "";
        $("#badgeTxt").textContent="✓ 完成 · "+s.row_count+" 条 · "+s.elapsed+"s"+extra;
      }
      else{b.className="badge err";$("#badgeTxt").textContent="✗ "+(s.error||"失败")}
      showFiles(s.files||[]);
      showSelfCheck(s.selfcheck||{});
      if(s.ok&&!s.skipped)loadResult();
      loadSources(false);
    }
    if(s.user)showUser(s.user);
    if(s.mirror)$("#mirrorInfo").textContent="数据源: "+s.mirror.replace("https://","");
  }).catch(()=>{});
  setTimeout(poll,600);
}

/* ===== 导出自检结果 ===== */
function showSelfCheck(sc){
  const names=Object.keys(sc||{});
  if(!names.length)return;
  const bad=names.filter(n=>!sc[n].ok);
  if(bad.length)toast("自检发现问题："+bad.join("、"),"err");
}

/* ===== 结果数据（仪表盘 + 数据表） ===== */
function loadResult(){
  api("/api/result").then(j=>{
    if(j.error||!j.rows)return;
    RESULT=j;renderDash(j.charts);renderTable();renderProfile(j);
    $("#dashEmpty").style.display="none";$("#dashBody").style.display="block";
    $("#dataEmpty").style.display="none";$("#dataBody").style.display="block";
  }).catch(()=>{});
}

/* ---- 画像页 ---- */
function hbar(pairs,color,max){
  if(!pairs.length)return '<div class="hint2">暂无数据</div>';
  const m=max||Math.max(...pairs.map(p=>p[1]))||1;
  return pairs.map(([k,v])=>`<div class="hbar"><span class="hl" title="${esc(k)}">${esc(k)}</span>
    <span class="hb"><i style="width:${Math.max(2,v/m*100)}%;background:${color||"var(--blue)"}"></i></span>
    <span class="hv">${v}</span></div>`).join("");
}
function renderProfile(j){
  const p=j.profile||{};
  const hasP=p.top_tags&&p.top_tags.length;
  const hasV=j.vs_global&&j.vs_global.total;
  const hasR=(j.recommend||[]).length;
  const hasD=j.diagnosis&&j.diagnosis.columns;
  if(!hasP&&!hasV&&!hasR&&!hasD)return;
  $("#profEmpty").style.display="none";$("#profBody").style.display="block";

  if(hasP){
    $("#profInsights").innerHTML='<ul class="insights">'+
      (p.insights||[]).map(s=>`<li>${esc(s)}</li>`).join("")+'</ul>';
    const d=p.diversity||{},L=p.length||{},ts=p.taste_score||{};
    const pct=x=>x==null?"-":(x*100).toFixed(0)+"%";
    $("#profMetrics").innerHTML=[
      ["兴趣标签数",d.distinct_tags,"var(--pink)"],["归一化熵",(d.entropy_norm||0).toFixed(3),"var(--blue)"],
      ["等效标签数",d.effective_tags,"var(--blue)"],["基尼系数",(d.gini||0).toFixed(3),"var(--orange)"],
      ["Top5 集中度",pct(d.top5_share),"var(--purple)"],["平均集数",L.avg??"-","var(--green)"],
      ["单季番占比",pct(L.single_cour_ratio),"var(--green)"],["收藏 BGM 均分",ts.avg_bgm??"-","var(--orange)"],
      ["高分占比(≥7.5)",pct(ts.high_ratio),"var(--ok)"],["近年占比",pct(p.recent_ratio),"var(--txt2)"],
    ].map(([k,v,c])=>`<div class="stat" style="--ac:${c}"><div class="sv">${v??"-"}</div><div class="sk">${k}</div></div>`).join("");
    $("#profTags").innerHTML=hbar(p.top_tags.map(t=>[t.name,t.count]),"var(--pink)");
    const m=p.rating_model;
    if(m&&m.trained){
      $("#profModelCard").style.display="block";
      $("#profModel").innerHTML=`<div class="hint2">样本 ${m.samples} 条，R² = ${(m.r2||0).toFixed(3)}（越接近 1 拟合越好）</div>`+
        hbar(Object.entries(m.coefficients||{}).filter(([k])=>k!=="截距").map(([k,v])=>[k,+(+v).toFixed(2)]),"var(--purple)",2);
    }
  }
  if(hasR){
    $("#recCard").style.display="block";
    $("#recBox").innerHTML='<div class="rec-grid">'+j.recommend.map(r=>`
      <a class="rec" href="${esc(r.url)}" target="_blank" rel="noreferrer">
        <div class="rec-top"><span class="rec-name">${esc(r.name)}</span><span class="rec-score">${r.score}</span></div>
        <div class="rec-meta">${esc(r.date||"")} · ${esc(r.platform||"")} · 匹配度 ${((r.match_score||0)*100).toFixed(0)}%</div>
        <div class="rec-tags">${(r.tags||[]).slice(0,5).map(t=>`<i>${esc(t)}</i>`).join("")}</div>
        <div class="rec-why">${esc(r.reason||"")}</div>
      </a>`).join("")+'</div>';
  }
  if(hasV){
    const g=j.vs_global;
    $("#vsCard").style.display="block";
    $("#vsInsights").innerHTML='<ul class="insights">'+(g.insights||[]).map(s=>`<li>${esc(s)}</li>`).join("")+'</ul>';
    $("#vsMetrics").innerHTML=[
      ["你收藏的等权全站均分",g.collection_avg_global,"var(--orange)"],
      ["全站打分人数",(g.global_hist_total||0).toLocaleString(),"var(--blue)"],
      ["按人数加权均分",g.global_mean,"var(--blue)"],
      ["你的平均分",g.my_mean??"未打分","var(--green)"],
      ["公认高分(≥7.5)",g.high_count,"var(--ok)"],
      ["低于 6.0",g.low_count,"var(--err)"],
    ].map(([k,v,c])=>`<div class="stat" style="--ac:${c}"><div class="sv">${v??"-"}</div><div class="sk">${k}</div></div>`).join("");
    const gh=g.global_hist||{};
    $("#vsHist").innerHTML=hbar(Object.keys(gh).sort((a,b)=>a-b).map(k=>[k+" 分",gh[k]]),"var(--purple)");
    const rated=g.rated||[];
    if(rated.length){
      $("#vsTable").innerHTML='<h3 style="margin:14px 0 8px">我 vs 大众 差异最大</h3><table class="mini"><thead><tr><th>条目</th><th>我的</th><th>全站</th><th>差值</th><th>分位</th></tr></thead><tbody>'+
        rated.slice(0,15).map(x=>`<tr><td>${esc(x.name)}</td><td>${x.my}</td><td>${x.global}</td><td>${x.delta>0?"+":""}${x.delta}</td><td>${x.percentile??"-"}%</td></tr>`).join("")+'</tbody></table>';
    }else{
      const hi=(g.items||[]).filter(x=>typeof x.global==="number").sort((a,b)=>b.global-a.global).slice(0,15);
      $("#vsTable").innerHTML=hi.length?'<h3 style="margin:14px 0 8px">你收藏里全站口碑最高</h3><table class="mini"><thead><tr><th>条目</th><th>全站均分</th><th>排名</th><th>评分人数</th></tr></thead><tbody>'+
        hi.map(x=>`<tr><td>${esc(x.name)}</td><td>${x.global}</td><td>${x.rank||"-"}</td><td>${(x.total||0).toLocaleString()}</td></tr>`).join("")+'</tbody></table>':"";
    }
  }
  if(hasD){
    $("#diagCard").style.display="block";
    const ic={ok:"✅",partial:"◐",empty:"⬜",all_zero:"0️⃣"};
    const need=j.diagnosis.user_owned_empty||[];
    $("#diagBox").innerHTML=(need.length?`<div class="warnbox">⬜ ${need.map(esc).join("、")} 为空 —— 这几列是<b>你自己在 Bangumi 上填写的内容</b>，站外接口不会替你编造，属于正常现象。</div>`:"")+
      '<table class="mini"><thead><tr><th>列</th><th>填充</th><th>来源接口</th><th>说明</th></tr></thead><tbody>'+
      j.diagnosis.columns.map(c=>`<tr><td>${ic[c.status]||""} ${esc(c.column)}</td><td>${c.filled}/${c.total}</td><td><code>${esc(c.source)}</code></td><td>${esc(c.explain)}</td></tr>`).join("")+'</tbody></table>';
  }
}

/* ---- 仪表盘 ---- */
function renderDash(c){
  if(!c)return;
  const cards=[
    ["总收藏",c.total,"var(--pink)"],["BGM 均分",c.avg_bgm||"-","var(--blue)"],
    ["我的均分",c.avg_mine||"-","var(--purple)"],["看过",c.progress.finished,"var(--green)"],
    ["在看",c.progress.watching,"var(--yellow)"],["想看",c.progress.plan,"var(--orange)"],
    ["搁置",c.progress.on_hold||0,"var(--txt2)"],["抛弃",c.progress.dropped||0,"var(--red)"],
  ];
  $("#statGrid").innerHTML=cards.map(([k,v,col])=>
    `<div class="stat" style="--ac:${col}"><div class="sv">${v}</div><div class="sk">${k}</div></div>`).join("");

  // 收藏状态环图（SVG donut）
  const cd=c.by_collection_type||{};
  const total=Object.values(cd).reduce((a,b)=>a+b,0)||1;
  let acc=0;const R=54,C=2*Math.PI*R;
  const segs=Object.entries(cd).map(([k,v])=>{
    const frac=v/total,off=acc;acc+=frac;
    return `<circle r="${R}" cx="70" cy="70" fill="none" stroke="${STATUS_COLORS[k]||"#555"}"
      stroke-width="20" stroke-dasharray="${(frac*C).toFixed(2)} ${C.toFixed(2)}"
      stroke-dashoffset="${(-off*C).toFixed(2)}" transform="rotate(-90 70 70)"/>`}).join("");
  $("#donutBox").innerHTML=`<div style="display:flex;align-items:center;gap:18px">
    <svg width="140" height="140" viewBox="0 0 140 140">${segs}
      <text x="70" y="66" text-anchor="middle" fill="#e8edf4" font-size="22" font-weight="700">${total}</text>
      <text x="70" y="84" text-anchor="middle" fill="#5d6a7d" font-size="10">条目</text></svg>
    <div class="legend" style="flex-direction:column;gap:6px">
      ${Object.entries(cd).map(([k,v])=>`<span><i style="background:${STATUS_COLORS[k]||"#555"}"></i>${k} · ${v}（${(v/total*100).toFixed(0)}%）</span>`).join("")}
    </div></div>`;

  // 条目类型横向柱
  const td=c.by_subject_type||{};
  const tmax=Math.max(...Object.values(td),1);
  const tcol=Object.fromEntries(Object.values(SUBJECT_TYPES).map(t=>[t.name,t.color]));
  $("#typeBarBox").innerHTML=Object.entries(td).map(([k,v])=>
    hbar(k,v,tmax,`--bc:${tcol[k]||"#7aa2f7"};--bc2:${tcol[k]||"#7aa2f7"}88`)).join("")||'<div class="empty">无数据</div>';

  // BGM 评分分布
  $("#bgmDistBox").innerHTML=distBars(c.bgm_score_dist,"var(--blue)","#5f8ae0")||'<div class="empty">无评分数据</div>';
  // 我的评分分布
  $("#myDistBox").innerHTML=distBars(c.my_rate_dist,"var(--pink)","var(--pink2)")||'<div class="empty">还没有打过评分</div>';

  // Top 榜
  $("#topBgm").innerHTML=topList(c.top_bgm);
  $("#topMine").innerHTML=topList(c.top_mine);

  /* ===== v3.1 高级统计 ===== */
  // 年度分布
  const yd=c.by_year||{};
  const ymax=Math.max(...Object.values(yd),1);
  $("#yearBox").innerHTML=Object.keys(yd).length
    ? Object.entries(yd).map(([k,v])=>hbar(k,v,ymax,"--bc:var(--purple);--bc2:#8b7ae0")).join("")
    : '<div class="empty">没有放送日期数据</div>';

  // Top 标签
  const tg=c.top_tags||[];
  $("#tagBox").innerHTML=tg.length
    ? tg.map(t=>hbar(t.name,t.value,tg[0].value,"--bc:var(--green);--bc2:#5fd3ac")).join("")
    : '<div class="empty">你还没有给条目打标签</div>';

  // 平台分布
  const pf=c.by_platform||{};
  const known=Object.entries(pf).filter(([k])=>k!=="未知");
  $("#platformBox").innerHTML=known.length
    ? known.map(([k,v])=>hbar(k,v,Math.max(...known.map(x=>x[1])),"--bc:var(--orange);--bc2:#ffbe76")).join("")
    : '<div class="empty">没有平台数据（可开启「补全平台等详情」）</div>';

  // 评分差异
  const rt=c.rating||{};
  if((rt.paired||0)>0){
    const deltaRows=arr=>(arr||[]).map(r=>`<tr><td>${esc(r.name)}</td>
      <td>${r.mine}</td><td>${r.bgm}</td>
      <td class="${r.delta>0?'delta-pos':'delta-neg'}">${r.delta>0?"+":""}${r.delta}</td></tr>`).join("");
    $("#ratingDelta").innerHTML=`
      <div class="stat-grid" style="margin-bottom:14px">
        <div class="stat" style="--ac:var(--blue)"><div class="sv">${rt.avg_delta>0?"+":""}${rt.avg_delta}</div><div class="sk">平均分差（我-BGM）</div></div>
        <div class="stat" style="--ac:var(--green)"><div class="sv">${rt.correlation===null?"-":rt.correlation}</div><div class="sk">与大众口味相关系数</div></div>
        <div class="stat" style="--ac:var(--red)"><div class="sv">${rt.harsher}</div><div class="sk">我打分更低</div></div>
        <div class="stat" style="--ac:var(--yellow)"><div class="sv">${rt.kinder}</div><div class="sk">我打分更高</div></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
        <div><h3 style="margin-bottom:8px">我打分更低</h3>
          <table class="delta-table"><tr><th>条目</th><th>我</th><th>BGM</th><th>差</th></tr>${deltaRows(rt.most_harsh)}</table></div>
        <div><h3 style="margin-bottom:8px">我打分更高</h3>
          <table class="delta-table"><tr><th>条目</th><th>我</th><th>BGM</th><th>差</th></tr>${deltaRows(rt.most_kind)}</table></div>
      </div>`;
  }else{
    $("#ratingBox").style.display="none";
  }

  // 追番完成度
  const cp=c.completion||{};
  const ctot=(cp.completed||0)+(cp.in_progress||0)+(cp.not_started||0);
  $("#completionBox").innerHTML=ctot
    ? `<div class="hbar" style="--bc:var(--green);--bc2:#5fd3ac"><span class="hb-k" style="width:76px">已看完</span>
         <span class="hb-t"><i style="width:${(cp.completed/ctot*100).toFixed(1)}%"></i></span><span class="hb-v">${cp.completed}</span></div>
       <div class="hbar" style="--bc:var(--blue);--bc2:#5f8ae0"><span class="hb-k" style="width:76px">看了一部分</span>
         <span class="hb-t"><i style="width:${(cp.in_progress/ctot*100).toFixed(1)}%"></i></span><span class="hb-v">${cp.in_progress}</span></div>
       <div class="hbar" style="--bc:var(--txt3);--bc2:var(--txt3)"><span class="hb-k" style="width:76px">未开始</span>
         <span class="hb-t"><i style="width:${(cp.not_started/ctot*100).toFixed(1)}%"></i></span><span class="hb-v">${cp.not_started}</span></div>`
    : '<div class="empty">没有总集数数据</div>';
}
function hbar(k,v,max,style){
  return `<div class="hbar" style="${style||""}"><span class="hb-k">${esc(k)}</span>
    <span class="hb-t"><i style="width:${(v/max*100).toFixed(1)}%"></i></span>
    <span class="hb-v">${v}</span></div>`}
function distBars(dist,c1,c2){
  const es=Object.entries(dist||{});
  if(!es.length)return"";
  const max=Math.max(...es.map(e=>e[1]),1);
  return es.map(([k,v])=>`<div class="hbar" style="--bc:${c1};--bc2:${c2}">
    <span class="hb-k">${k}</span><span class="hb-t"><i style="width:${(v/max*100).toFixed(1)}%"></i></span>
    <span class="hb-v">${v}</span></div>`).join("")}
function topList(arr){
  if(!arr||!arr.length)return'<div class="empty">无数据</div>';
  return arr.map((r,i)=>`<li><span class="rank">${i+1}</span>
    <span class="tn" title="${esc(r.name)}">${esc(r.name)}</span>
    <span class="tv">${r.value}</span></li>`).join("")}

/* ---- 数据表 ---- */
const TBL_COLS=[
  {k:"封面",t:"cover"},{k:"中文名",t:"title"},{k:"条目类型",t:"chip"},
  {k:"收藏类型",t:"status"},{k:"我的评分",t:"mine"},{k:"BGM评分",t:"score"},
  {k:"评分人数",t:"num"},{k:"排名",t:"num"},{k:"平台",t:"text"},
  {k:"放送日期",t:"text"},{k:"看到第几集",t:"num"},{k:"总集数",t:"num"},
  {k:"条目标签",t:"text"},{k:"我的短评",t:"text"},{k:"我的标签",t:"text"},
  {k:"更新时间",t:"text"},
];
function renderTable(){
  if(!RESULT||!RESULT.rows)return;
  $("#dataHead").innerHTML=TBL_COLS.map(c=>{
    const sorted=tblSort.key===c.k;
    return `<th data-k="${c.k}" class="${sorted?"sorted":""}">${c.k}<span class="arr">${sorted?(tblSort.asc?"▲":"▼"):"⇅"}</span>`}).join("");
  $$("#dataHead th").forEach(th=>th.onclick=()=>{
    const k=th.dataset.k;
    if(tblSort.key===k)tblSort.asc=!tblSort.asc;else{tblSort.key=k;tblSort.asc=true}
    renderTable()});
  renderRows();
}
function renderRows(){
  let rows=RESULT.rows.slice();
  if(tblStatus!=="全部")rows=rows.filter(r=>r["收藏类型"]===tblStatus);
  if(tblFilter)rows=rows.filter(r=>
    String(r["中文名"]||"").toLowerCase().includes(tblFilter)||
    String(r["原名"]||"").toLowerCase().includes(tblFilter)||
    String(r["我的短评"]||"").toLowerCase().includes(tblFilter)||
    String(r["我的标签"]||"").toLowerCase().includes(tblFilter));
  const k=tblSort.key,dir=tblSort.asc?1:-1;
  rows.sort((a,b)=>{
    let av=a[k],bv=b[k];
    const an=parseFloat(av),bn=parseFloat(bv);
    if(!isNaN(an)&&!isNaN(bn))return (an-bn)*dir;
    return String(av??"").localeCompare(String(bv??""),"zh")*dir});
  const LIMIT=500,shown=rows.slice(0,LIMIT);
  $("#dataBodyRows").innerHTML=shown.map(r=>{
    const tcol=Object.values(SUBJECT_TYPES).find(t=>t.name===r["条目类型"]);
    const sc=parseFloat(r["BGM评分"]),scls=isNaN(sc)?"":sc>=8?"hi":sc>=6.5?"mid":"lo";
    return `<tr>
      <td class="cover">${r["封面"]?`<img src="${esc(r["封面"])}" loading="lazy" onerror="this.style.display='none'">`:""}</td>
      <td class="title"><a href="${esc(r["条目链接"]||"#")}" target="_blank">${esc(r["中文名"]||r["原名"])}</a>
        <span class="sub">${esc(r["原名"]||"")}</span></td>
      <td><span class="tchip" style="background:${(tcol&&tcol.color||"#888")}22;color:${tcol&&tcol.color||"#888"}">${esc(r["条目类型"])}</span></td>
      <td><span class="tchip" style="background:${(STATUS_COLORS[r["收藏类型"]]||"#888")}22;color:${STATUS_COLORS[r["收藏类型"]]||"#888"}">${esc(r["收藏类型"])}</span></td>
      <td class="mine">${r["我的评分"]||"-"}</td>
      <td class="score ${scls}">${r["BGM评分"]||"-"}</td>
      <td>${r["评分人数"]?Number(r["评分人数"]).toLocaleString():"-"}</td>
      <td>${r["排名"]||"-"}</td>
      <td>${esc(r["平台"]||"-")}</td>
      <td>${esc(r["放送日期"]||"-")}</td>
      <td>${+r["看到第几集"]>0?r["看到第几集"]:"-"}</td>
      <td>${r["总集数"]||"-"}</td>
      <td class="tags" title="${esc(r["条目标签"])}">${(r["条目标签"]||"").split("|").filter(Boolean).slice(0,4).map(t=>`<span class="tag">${esc(t)}</span>`).join("")||"-"}</td>
      <td title="${esc(r["我的短评"])}">${esc(r["我的短评"]||"-")}</td>
      <td title="${esc(r["我的标签"])}">${esc(r["我的标签"]||"-")}</td>
      <td class="sub">${esc((r["更新时间"]||"").replace("T"," ").slice(0,10)||"-")}</td>
    </tr>`}).join("")||'<tr><td colspan="17" class="empty">无匹配数据</td></tr>';
  $("#dataCount").textContent=`显示 ${shown.length} / ${rows.length} 条`+(rows.length>LIMIT?`（仅渲染前 ${LIMIT} 条，完整数据见导出文件）`:"");
}
$("#searchBox").addEventListener("input",e=>{tblFilter=e.target.value.trim().toLowerCase();renderRows()});
$("#copyCsvBtn").onclick=()=>{
  if(!RESULT)return toast("暂无数据","err");
  const cols=["序号","条目类型","收藏类型","中文名","原名","我的评分","BGM评分","评分人数","排名","看到第几集","总集数","放送日期","平台","条目标签","我的短评","我的标签","条目ID","条目链接","更新时间"];
  const csv=[cols.join(","),...RESULT.rows.map(r=>cols.map(c=>{
    const v=String(r[c]??"").replace(/"/g,'""');
    return /[",\n]/.test(v)?`"${v}"`:v}).join(","))].join("\n");
  navigator.clipboard.writeText("\ufeff"+csv).then(()=>toast("✓ 已复制 "+RESULT.rows.length+" 行 CSV","ok"),
    ()=>toast("复制失败","err"));
};

/* ===== 设置 ===== */
$("#setWorkers").oninput=e=>$("#wkVal").textContent=e.target.value;
$("#saveSetBtn").onclick=()=>{
  post("/api/config",{
    token:$("#token").value.trim(),
    proxy:$("#setProxy").value.trim(),
    output:$("#setOutput").value.trim(),
    api_base:$("#setMirror").value.trim(),
    username:$("#setUsername").value.trim(),
    source:$("#setSource").value,
    workers:+$("#setWorkers").value,
    subject_types:selectedTypes(),
    formats:selectedFormats(),
    collection_types:selectedStatuses(),
  }).then(j=>{toast(j.ok?"✓ 设置已保存":"保存失败","ok");loadSettings()});
};
$("#clearCacheBtn").onclick=()=>post("/api/cache/clear",{what:"rating"}).then(j=>{
  toast(j.ok?"✓ 评分缓存已清空（"+j.cleared+" 条）":"失败","ok");loadSettings()});
$("#clearDataBtn").onclick=()=>{
  if(!confirm("清空完整数据缓存？\n\n之后将无法使用增量导出与离线导出，需要重新联网全量导出一次。"))return;
  post("/api/cache/clear",{what:"data"}).then(j=>{
    toast(j.ok?"✓ 数据缓存已清空（"+j.cleared_data+" 条）":"失败","ok");loadSettings()});
};

/* ===== 数据源 ===== */
const SRC_COLORS={true:"var(--green)",false:"var(--red)",null:"var(--txt3)"};
function renderSources(payload){
  const list=payload.sources||[];
  $("#srcList").innerHTML=list.length?list.map(s=>{
    const ok=s.ok, col=SRC_COLORS[String(ok)];
    const authTxt=s.auth===true?"支持鉴权":s.auth===false?"不支持鉴权":"";
    return `<div class="src-row ${s.recommended?"best":""}">
      <span class="sr-dot" style="background:${col}"></span>
      <span class="sr-name">${esc(s.name)}</span>
      <span class="sr-base" title="${esc(s.base)}">${esc(s.base)}</span>
      ${authTxt?`<span class="sr-tag">${authTxt}</span>`:""}
      ${s.pending?'<span class="sr-tag">探测中</span>':""}
      ${s.cooling_seconds>0?`<span class="sr-tag">冷却 ${Math.ceil(s.cooling_seconds)}s</span>`:""}
      <span class="sr-ms">${s.ms!=null?s.ms+"ms":(ok===false?"不可用":"-")}</span>
    </div>`}).join(""):'<div class="empty">没有数据源</div>';
  const sel=$("#setSource"),cur=sel.value;
  sel.innerHTML='<option value="">自动（推荐）</option>'+
    list.filter(s=>s.ok!==false).map(s=>
      `<option value="${esc(s.base)}">${esc(s.name)} · ${s.ms!=null?s.ms+"ms":""}</option>`).join("");
  sel.value=payload.preferred||cur||"";
  const bad=list.filter(s=>s.ok===false).map(s=>`${s.name}（${s.error||"不可用"}）`);
  $("#srcNote").innerHTML=`当前推荐：<b style="color:var(--green)">${esc(payload.best||"-")}</b>`
    +(bad.length?`<br>不可用：${esc(bad.join("、"))}`:"")
    +`<br>程序每次导出都会自动选最快的可用源；坏源会被熔断冷却，不再拖慢导出。`;
}
function loadSources(probe){
  $("#probeState").textContent=probe?"探测中...":"";
  api("/api/sources"+(probe?"?probe=1":"")).then(j=>{
    renderSources(j);$("#probeState").textContent="";
  }).catch(()=>{$("#probeState").textContent="加载失败"});
}
$("#probeBtn").onclick=()=>{loadSources(true);toast("正在并发探测数据源...")};
$("#applySourceBtn").onclick=()=>{
  post("/api/config",{source:$("#setSource").value}).then(j=>{
    toast(j.ok?"✓ 已应用数据源":"失败","ok");loadSources(false)});
};

function loadSettings(){
  api("/api/settings").then(j=>{
    if(j.token)$("#token").value=j.token;
    $("#setProxy").value=j.proxy||"";
    $("#setOutput").value=j.output||"";
    $("#setMirror").value=j.api_base||"";
    $("#setUsername").value=j.username||"";
    $("#setWorkers").value=j.workers||6;$("#wkVal").textContent=j.workers||6;
    $("#cacheCount").textContent=(j.cache_count??"-")+" 条";
    $("#dataCacheCount").textContent=(j.data_cache_count??"-")+" 条";
    if(j.data_cache_at){
      const d=new Date(j.data_cache_at*1000);
      $("#dataCacheAt").textContent=d.toLocaleString("zh-CN");
    }else $("#dataCacheAt").textContent="尚无缓存";
    $("#outDirInfo").textContent=j.output_dir||"-";
    $("#verInfo").textContent="v"+(j.version||"3.1");
    // 恢复上次的类型/格式/状态选择
    const st=new Set(j.subject_types||[2]),sf=new Set(j.formats||["csv"]),ss=new Set(j.collection_types||[]);
    $$("#typeChips .chip").forEach(c=>{if(st.has(+c.dataset.code))c.onclick()});
    $$("#fmtChips .chip").forEach(c=>{if(sf.has(c.dataset.fmt))c.onclick()});
    $$("#statusChips .chip").forEach(c=>{if(ss.has(+c.dataset.st))c.onclick()});
  });
  loadSources(false);
}

/* ===== 启动 ===== */
buildChips();
loadSettings();
poll();
</script>
</body>
</html>
"""


def render_page():
    """把常量注入 HTML 模板。"""
    import json
    from .constants import SUBJECT_TYPES, FORMATS, FORMAT_LABEL, COLLECTION_STATUS_OPTIONS
    return (HTML_PAGE
            .replace("__SUBJECT_TYPES__", json.dumps(SUBJECT_TYPES, ensure_ascii=False))
            .replace("__FORMATS__", json.dumps(FORMAT_LABEL, ensure_ascii=False))
            .replace("__STATUS_OPTIONS__", json.dumps(COLLECTION_STATUS_OPTIONS, ensure_ascii=False)))