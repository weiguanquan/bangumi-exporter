# -*- coding: utf-8 -*-
"""HTTP 客户端：重试 / 指数退避 / 代理 / 镜像故障转移 / 并发分页获取。"""

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from .constants import API_BASES, PROBE_RETRIES, PROBE_TIMEOUT  # noqa: F401

# 默认使用系统信任链校验证书（防中间人攻击）。
SSL_CTX = ssl.create_default_context()
# 兼容备用镜像的宽松上下文：仅在证书校验失败时按请求降级使用。
UNVERIFIED_SSL_CTX = ssl.create_default_context()
UNVERIFIED_SSL_CTX.check_hostname = False
UNVERIFIED_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "bangumi-export/3.0",
    "Accept": "application/json",
}

# 镜像连通性探测用的短超时：坏镜像不应让启动卡住好几分钟。
# （PROBE_TIMEOUT / PROBE_RETRIES 定义在 constants.py，供 sources.py 共用）

_proxy_url = ""
_openers = {}          # verify(bool) -> OpenerDirector（仅在配置了代理时使用）


def set_token(token):
    if token:
        HEADERS["Authorization"] = f"Bearer {token}"
    else:
        HEADERS.pop("Authorization", None)


def set_proxy(proxy_url, log=None):
    global _proxy_url, _openers
    _proxy_url = str(proxy_url or "").strip()
    _openers = {}
    if _proxy_url and log:
        log(f"已启用代理: {_proxy_url}")


def _build_opener(ctx):
    handlers = [
        urllib.request.ProxyHandler({"http": _proxy_url, "https": _proxy_url}),
        urllib.request.HTTPSHandler(context=ctx),
    ]
    return urllib.request.build_opener(*handlers)


def _open(req, timeout, verify=True):
    """发起请求并返回响应对象（上下文管理器）。

    注意：OpenerDirector 只有 open()，没有 urlopen()，且不接受 context 参数，
    因此代理路径与直连路径必须分开处理。
    """
    ctx = SSL_CTX if verify else UNVERIFIED_SSL_CTX
    if _proxy_url:
        opener = _openers.get(verify)
        if opener is None:
            opener = _build_opener(ctx)
            _openers[verify] = opener
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def _is_cert_error(exc):
    """判断异常是否为 TLS 证书校验失败（urllib 会把它包进 URLError.reason）。"""
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLCertVerificationError) or isinstance(
        exc, ssl.SSLCertVerificationError)


def _read_json(resp):
    raw = resp.read()
    try:
        return resp.status, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise ValueError(
            f"镜像返回内容不是 JSON（HTTP {resp.status}）: {raw[:120]!r}") from e


def http_get(url, params=None, retries=3, base_delay=1.0, timeout=30, log=None):
    """带指数退避重试的 GET 请求。429/5xx 与网络错误自动重试。

    默认校验证书；仅当证书校验失败时降级为不校验并留日志（兼容证书链
    不完整的第三方镜像），其余情况严格校验。
    """
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with _open(req, timeout) as resp:
                return _read_json(resp)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = base_delay * (2 ** attempt)
                if log:
                    log(f"  HTTP {e.code}，{wait:.1f}s 后重试（{attempt + 1}/{retries}）")
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = e
            if _is_cert_error(e):
                # 证书链不完整：降级重试一次，避免整条导出链路直接失败。
                if log:
                    log(f"  TLS 证书校验失败: {getattr(e, 'reason', e)}"
                        f"，改用不校验证书的方式重试")
                try:
                    with _open(req, timeout, verify=False) as resp:
                        return _read_json(resp)
                except urllib.error.HTTPError:
                    raise
                except (urllib.error.URLError, TimeoutError,
                        ConnectionError, OSError) as e2:
                    last_err = e2
            if attempt < retries - 1:
                wait = base_delay * (2 ** attempt)
                if log:
                    log(f"  网络错误: {last_err}，{wait:.1f}s 后重试（{attempt + 1}/{retries}）")
                time.sleep(wait)
                continue
    raise last_err


def http_post(url, payload=None, retries=3, base_delay=1.0, timeout=30, log=None):
    """带重试的 JSON POST（用于 /v0/search/subjects 这类检索接口）。

    与 http_get 共用代理 / 证书降级策略，保持行为一致。
    """
    data = json.dumps(payload if payload is not None else {},
                      ensure_ascii=False).encode("utf-8")
    last_err = None
    for attempt in range(retries):
        headers = dict(HEADERS)
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with _open(req, timeout) as resp:
                return _read_json(resp)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = base_delay * (2 ** attempt)
                if log:
                    log(f"  HTTP {e.code}，{wait:.1f}s 后重试（{attempt + 1}/{retries}）")
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = e
            if _is_cert_error(e):
                if log:
                    log("  TLS 证书校验失败，改用不校验证书的方式重试")
                try:
                    with _open(req, timeout, verify=False) as resp:
                        return _read_json(resp)
                except urllib.error.HTTPError:
                    raise
                except (urllib.error.URLError, TimeoutError,
                        ConnectionError, OSError) as e2:
                    last_err = e2
            if attempt < retries - 1:
                wait = base_delay * (2 ** attempt)
                if log:
                    log(f"  网络错误: {last_err}，{wait:.1f}s 后重试（{attempt + 1}/{retries}）")
                time.sleep(wait)
                continue
    raise last_err


def search_subjects(keyword="", subject_type=2, tags=None, sort="rank",
                    limit=20, offset=0, base=None, log=None):
    """检索条目（POST /v0/search/subjects）。

    返回原始条目列表；接口不可用时抛异常，由调用方决定是否降级。
    """
    base = (base or API_BASES[0]).rstrip("/")
    flt = {"type": [int(subject_type)]}
    if tags:
        flt["tag"] = list(tags)[:8]
    payload = {
        "keyword": keyword or "",
        "sort": sort,
        "filter": flt,
    }
    url = f"{base}/v0/search/subjects?limit={int(limit)}&offset={int(offset)}"
    res = http_post(url, payload, log=log)
    if isinstance(res, tuple):          # _read_json 返回 (status, payload)
        res = res[1]
    if isinstance(res, dict):
        return res.get("data") or []
    return res or []


def tag_names(raw_tags, top=None):
    """把两种标签结构统一成字符串列表。

    收藏接口内嵌的 subject.tags 可能是 ["治愈", ...]，
    检索接口返回的是 [{"name": "治愈", "count": 9}, ...]。
    """
    out = []
    for t in raw_tags or []:
        if isinstance(t, dict):
            n = t.get("name")
            if n:
                out.append(str(n))
        elif t:
            out.append(str(t))
    return out[:top] if top else out


def _probe_identity(base, timeout=PROBE_TIMEOUT, log=None):
    """在单个源上取 /v0/me，返回 (user|None, status, error)。

    刻意把「HTTP 401」与「网络错误」分开返回：401 才可能意味着 Token 有问题，
    而超时/证书错误只是这个源本身不可用。
    """
    url = f"{base}/v0/me"
    try:
        status, data = http_get(url, retries=PROBE_RETRIES, timeout=timeout,
                                log=log)
        if status == 200 and isinstance(data, dict) and data.get("id"):
            return data, status, ""
        return None, status, f"HTTP {status}"
    except urllib.error.HTTPError as e:
        return None, e.code, f"HTTP {e.code}"
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"


def get_me(bases=None, log=None, manager=None):
    """尝试多个源获取当前用户信息，返回 (user_data, working_base)。

    ⚠ 关键修复：默认顺序由 SourceManager 决定（并发探测 + 熔断），
    且**绝不**因为某个源不支持 /v0/me（恒返回 401）就断定 Token 无效——
    必须等到所有支持鉴权的源都返回 401 才下这个结论。
    失败时给出区分「Token 无效」与「网络不通」的准确提示。
    """
    if manager is not None:
        ordered = manager.candidates(bases)
    elif bases is not None:
        ordered = list(bases)
    else:
        ordered = list(API_BASES)

    auth_failed = []      # 明确 401 的源
    net_failed = []       # 网络不通 / 其它错误
    no_auth = []          # 可达但根本不支持 /v0/me 的源

    for base in ordered:
        user, status, err = _probe_identity(base, log=log)
        if user is not None:
            if log:
                log(f"  尝试 {base}/v0/me -> 200")
            if manager is not None:
                manager.record_success(base)
            return user, base
        if status in (401, 403):
            auth_failed.append(base)
            if log:
                log(f"  {base} 认证失败: HTTP {status}")
        elif status == 404:
            # 该源没有 /v0/me 端点 —— 说明它只是「取数镜像」，不代表 Token 失效
            no_auth.append(base)
            if log:
                log(f"  {base} 不支持 /v0/me（HTTP 404），仅可用于取数据")
        else:
            net_failed.append(f"{base}({err})")
            if log:
                log(f"  {base} 获取用户失败: {err}")
            if manager is not None:
                manager.record_failure(base, err)

    if auth_failed and not net_failed and not no_auth:
        raise RuntimeError(
            "Token 无效或已过期（所有数据源均返回 HTTP 401）。"
            "请在 bgm.tv → 设置 → App 授权 重新生成 Access Token 后重试")
    if auth_failed:
        raise RuntimeError(
            "无法完成身份识别：部分数据源认证失败（"
            + "、".join(auth_failed)
            + "），其余数据源不可用（"
            + "、".join(net_failed or no_auth or ["无"])
            + "）。请检查 Token 或改用其它数据源")
    if net_failed:
        raise RuntimeError(
            "无法连接任何 Bangumi 数据源（网络不通或域名被拦截）："
            + "、".join(net_failed)
            + "。可在「设置」中填写 HTTP 代理、切换数据源，或使用 --proxy")
    raise RuntimeError(
        "所有可达的数据源都不支持 /v0/me 身份识别（"
        + "、".join(no_auth)
        + "）。可在「设置 → 数据源」改为支持鉴权的源（如 BGMAPI 镜像），"
        "或用 --username 直接指定用户名跳过该步骤")


def fetch_collections(uid, base, subject_type, log=None):
    """分页获取某一类型（动画/书籍/...）的全部收藏。"""
    all_items = []
    offset = 0
    limit = 50
    total = None

    while True:
        url = f"{base}/v0/users/{uid}/collections"
        params = {"subject_type": subject_type, "limit": limit, "offset": offset}
        try:
            status, j = http_get(url, params, log=log)
        except urllib.error.HTTPError as e:
            if log:
                log(f"  获取收藏 HTTP {e.code}，放弃该镜像")
            return []

        data = j.get("data", []) if isinstance(j, dict) else j
        total = j.get("total", total) if isinstance(j, dict) else None

        if not data:
            break

        all_items.extend(data)
        offset += len(data)
        if log:
            log("  已获取 %d" % len(all_items) + (f" / {total}" if total else ""))

        if total is not None and offset >= total:
            break
        if len(data) < limit:
            break

        time.sleep(0.4)

    return all_items


def normalize_embedded(items, log=None):
    """把 collections 响应里内嵌的 score/rank 提升为 rating（零网络请求）。

    ⚠ 注意语义差异：内嵌的 ``collection_total`` 是「收藏人数」，
    而 rating.total 是「评分人数」，两者完全不同，
    因此这里刻意**不填 total**，避免导出文件里出现错误的评分人数。
    """
    n = 0
    for item in items:
        subj = item.get("subject") or {}
        if (subj.get("rating") or {}).get("score"):
            continue
        score = subj.get("score")
        if not score:
            continue
        subj["rating"] = {"score": score, "rank": subj.get("rank") or None}
        item["subject"] = subj
        n += 1
    return n


# 需要从条目详情里补全的字段（collections 接口不返回）
DETAIL_FIELDS = ("platform",)


def needs_detail(item, want=DETAIL_FIELDS):
    """该条目是否还需要一次详情请求。"""
    subj = item.get("subject") or {}
    if not (subj.get("rating") or {}).get("total"):
        return True
    return any(not subj.get(f) for f in want)


def _fetch_one_detail(sid, base):
    try:
        _, detail = http_get(f"{base}/v0/subjects/{sid}", retries=2)
        return sid, detail if isinstance(detail, dict) else {}
    except Exception:
        return sid, {}


def enrich_details(items, base, workers=6, log=None, want=DETAIL_FIELDS,
                   cancel_event=None):
    """并发补取条目详情：一次请求同时拿到完整 rating 与 platform。

    旧实现（enrich_ratings）把响应里的 platform 直接丢掉了，
    导致导出文件的「平台」列永远是空的；这里改为合并整份详情。
    """
    missing = []
    for item in items:
        if not needs_detail(item, want):
            continue
        sid = (item.get("subject") or {}).get("id") or item.get("subject_id")
        if sid:
            missing.append((item, sid))

    if not missing:
        if log:
            log("所有条目信息已完整，无需补取")
        return items

    if log:
        log(f"需要补取 {len(missing)} 条条目详情（评分/平台），并发获取中...")
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {ex.submit(_fetch_one_detail, sid, base): sid
                   for _, sid in missing}
        for i, fut in enumerate(as_completed(futures), 1):
            sid, det = fut.result()
            results[sid] = det
            if cancel_event is not None and cancel_event.is_set():
                if log:
                    log("  已取消补取")
                break
            if i % 50 == 0 or i == len(missing):
                if log:
                    log(f"  已补取 {i} / {len(missing)}")

    for item, sid in missing:
        det = results.get(sid) or {}
        if not det:
            continue
        subj = item.get("subject") or {}
        if det.get("rating"):
            subj["rating"] = det["rating"]
        for f in want:
            if not subj.get(f) and det.get(f):
                subj[f] = det[f]
        item["subject"] = subj
    return items


def enrich_ratings(items, base, workers=6, log=None):
    """向后兼容：只补评分（等价于 want=() 的 enrich_details）。"""
    return enrich_details(items, base, workers=workers, log=log, want=())