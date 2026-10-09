#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大瑞的信息网 · 数据源解析与并发抓取模块

支持 RSS/Atom、公开 JSON API、榜单 HTML 三类源，统一归一化为条目结构；
通过 ThreadPoolExecutor 并发抓取全部数据源，单源失败不中断整体，报告保留出错收集。
"""
import concurrent.futures
import json
import re
import time
import urllib.parse
from xml.etree import ElementTree as ET

from common import (BLOCK_KEYS, BLOCK_MAP, clean_text, http_get, iso_cst, log,
                    make_id, now_cst, parse_pub_date, sort_key)
from translate import (TRANS_ENABLED, TRANS_STATS, _TRANS_LOCK, claim_item,
                       is_foreign, translate)

def _lname(tag):
    return tag.split("}")[-1]

def _child_text(el, names):
    for child in list(el):
        if _lname(child.tag) in names:
            if child.text and child.text.strip():
                return child.text.strip()
    return ""

def _child_link(el):
    """RSS 的 <link> 文本 或 Atom 的 <link href>。"""
    fallback = ""
    for child in list(el):
        if _lname(child.tag) != "link":
            continue
        href = child.get("href")
        rel = (child.get("rel") or "alternate").lower()
        text = (child.text or "").strip()
        value = href or text
        if not value:
            continue
        if rel == "alternate":
            return value
        if not fallback:
            fallback = value
    return fallback

def _sanitize_xml(text):
    """容错处理：修补未转义的裸 & 与多余控制字符，兼容不规范订阅源。"""
    text = re.sub(r"&(?!(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);)", "&amp;", text)
    text = "".join(ch for ch in text if ch >= " " or ch in "\t\n\r")
    return text

def parse_feed(raw_bytes, source):
    """解析 RSS 2.0 / Atom / RDF 订阅源（含不规范 XML 的容错重试）。"""
    text = raw_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text, count=1).strip()
    text = re.sub(r"^\s*<!DOCTYPE[^>]*>", "", text, count=1).strip()
    text = _sanitize_xml(text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        root = ET.fromstring(_sanitize_xml(text))

    entries = [el for el in root.iter() if _lname(el.tag) in ("item", "entry")]
    items = []
    for el in entries:
        title = clean_text(_child_text(el, ("title",)), 300)
        if not title:
            continue
        url = _child_link(el)
        summary = clean_text(
            _child_text(el, ("description", "summary", "content", "encoded")), 260)
        pub = parse_pub_date(_child_text(el, ("pubDate", "published", "updated", "date", "created")))
        items.append({"title": title, "url": url, "summary": summary, "published_at": pub})
    return items

def _dig(obj, path):
    cur = obj
    for seg in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(seg)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(seg)
        else:
            return None
    return cur

def parse_json_list(raw_bytes, source):
    """通用 JSON 列表解析：由 config 中的 map 指定字段路径。"""
    data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
    mapping = source.get("map") or {}
    list_path = mapping.get("list_path", "")
    rows = _dig(data, list_path) if list_path else data
    if not isinstance(rows, list):
        return []
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = _dig(row, mapping.get("title", "title"))
        if not title:
            continue
        url = _dig(row, mapping.get("url", "url")) or ""
        summary = _dig(row, mapping.get("summary", "summary")) or ""
        pub = parse_pub_date(_dig(row, mapping.get("published", "published")))
        items.append({
            "title": clean_text(title, 300),
            "url": str(url),
            "summary": clean_text(summary, 260),
            "published_at": pub,
        })
    return items

def parse_toutiao_hot(raw_bytes, source):
    data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
    rows = data.get("data") or []
    items = []
    for idx, row in enumerate(rows, 1):
        title = row.get("Title") or row.get("title")
        if not title:
            continue
        hot = row.get("HotValue") or row.get("hot_value")
        try:
            hot_txt = "热度 %s" % format(int(hot), ",")
        except (TypeError, ValueError):
            hot_txt = ""
        items.append({
            "title": clean_text(title, 300),
            "url": row.get("Url") or row.get("url") or "",
            "summary": clean_text("今日头条热榜第 %d 位%s" % (idx, ("· " + hot_txt) if hot_txt else ""), 260),
            "published_at": None,
        })
    return items

def parse_bilibili_hot(raw_bytes, source):
    data = json.loads(raw_bytes.decode("utf-8", errors="replace"))
    rows = (((data or {}).get("data") or {}).get("trending") or {}).get("list") or []
    items = []
    for idx, row in enumerate(rows, 1):
        title = row.get("show_name") or row.get("keyword")
        if not title:
            continue
        kw = row.get("keyword") or title
        try:
            hot_txt = "热度 %s" % format(int(row.get("heat_score") or 0), ",")
        except (TypeError, ValueError):
            hot_txt = ""
        items.append({
            "title": clean_text(title, 300),
            "url": "https://search.bilibili.com/all?keyword=" + urllib.parse.quote(str(kw)),
            "summary": clean_text("B站热搜第 %d 位%s" % (idx, ("· " + hot_txt) if hot_txt else ""), 260),
            "published_at": None,
        })
    return items

def _extract_json_object(text, pos):
    """从 text[pos] 处的 '{' 开始做花括号配对扫描，返回该 JSON 对象子串。"""
    if pos < 0 or text[pos] != "{":
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(pos, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[pos:i + 1]
    return None

def parse_baidu_hot(raw_bytes, source):
    """百度热搜榜（HTML 内嵌 JSON）：扫描每个含 "word" 的对象。"""
    text = raw_bytes.decode("utf-8", errors="replace")
    items = []
    seen = set()
    for m in re.finditer(r'"word"\s*:\s*"', text):
        start = text.rfind("{", 0, m.start())
        if start < 0:
            continue
        blob = _extract_json_object(text, start)
        if not blob:
            continue
        try:
            row = json.loads(blob)
        except json.JSONDecodeError:
            continue
        word = row.get("word")
        if not word or word in seen:
            continue
        seen.add(word)
        idx = len(items) + 1
        desc = clean_text(row.get("desc") or "", 260)
        hot = row.get("hotScore") or row.get("hot_score")
        try:
            hot_txt = "热度 %s" % format(int(hot), ",")
        except (TypeError, ValueError):
            hot_txt = ""
        summary = desc or ("百度热搜第 %d 位%s" % (idx, ("· " + hot_txt) if hot_txt else ""))
        items.append({
            "title": clean_text(word, 300),
            "url": row.get("appUrl") or row.get("url") or
                   ("https://www.baidu.com/s?wd=" + urllib.parse.quote(str(word))),
            "summary": summary,
            "published_at": None,
        })
    return items

PARSERS = {
    "json_list": parse_json_list,
    "toutiao_hot": parse_toutiao_hot,
    "bilibili_hot": parse_bilibili_hot,
    "baidu_hot": parse_baidu_hot,
}

def parse_source(raw_bytes, source):
    parser = source.get("parser")
    if parser:
        fn = PARSERS.get(parser)
        if not fn:
            raise ValueError("未知 parser: %s" % parser)
        items = fn(raw_bytes, source)
    else:
        stype = (source.get("type") or "rss").lower()
        if stype in ("rss", "atom"):
            head = raw_bytes[:1200].decode("utf-8", errors="replace").lower()
            if "<rss" not in head and "<feed" not in head and "<?xml" not in head:
                raise ValueError("返回内容不是 XML 订阅源（疑似被反爬拦截或地址已变更）")
            items = parse_feed(raw_bytes, source)
        elif stype == "api":
            items = parse_json_list(raw_bytes, source)
        elif stype == "html":
            raise ValueError("type=html 的数据源必须显式指定 parser")
        else:
            raise ValueError("未知 type: %s" % stype)
    if not items:
        raise ValueError("未解析到任何条目（可能榜单为空或页面结构变更）")
    return items

def build_entry(row, source, seen_at):
    title = clean_text(row.get("title"), 300)
    if not title:
        return None
    url = (row.get("url") or "").strip()
    source_name = source.get("name") or ""
    summary = clean_text(row.get("summary"), 260)

    # 外文条目附带中文译文（原文完整保留；已含中文或达本轮翻译上限则跳过）
    title_zh, summary_zh = "", ""
    need_trans = TRANS_ENABLED and (is_foreign(title) or is_foreign(summary))
    if need_trans and claim_item():
        title_zh = translate(title)
        summary_zh = translate(summary) if summary else ""
    elif need_trans:
        # 达本轮翻译上限：跳过该条并计数，避免静默丢失翻译配额
        with _TRANS_LOCK:
            TRANS_STATS["limit_skipped"] += 1

    return {
        "id": make_id(title, source_name),
        "title": title,
        "title_zh": title_zh,
        "summary": summary,
        "summary_zh": summary_zh,
        "source_name": source_name,
        "source_url": url,
        "published_at": row.get("published_at"),
        "first_seen": seen_at,
        "last_seen": seen_at,
        "block": source.get("block"),
        "credibility": source.get("credibility") or "二手转载",
        "tags": list(source.get("tags") or []),
    }

def match_keywords(row, keywords):
    """按源配置的 filter_keywords 过滤：标题或摘要命中任一关键词即保留（大小写不敏感）。"""
    hay = ((row.get("title") or "") + " " + (row.get("summary") or "")).lower()
    return any(str(k).lower() in hay for k in keywords)

MOBILE_KEYWORDS = [
    "手机", "新机", "旗舰", "折叠", "屏下", "芯片", "骁龙", "天玑", "鸿蒙", "安卓", "影像", "摄像头",
    "电池", "快充", "系统更新", "平板", "手表", "耳机", "苹果", "华为", "小米", "红米", "荣耀",
    "一加", "真我", "努比亚", "魅族", "摩托罗拉", "传音", "vivo", "oppo",
    "iphone", "ipad", "ios", "android", "galaxy", "pixel", "xiaomi", "redmi", "oneplus", "oppo",
    "vivo", "honor", "huawei", "samsung", "snapdragon", "dimensity", "mediatek", "exynos", "tensor",
    "foldable", "smartphone", "smartwatch", "wearable", "tablet", "chipset", "harmonyos", "hyperos",
    "one ui", "magicos", "coloros", "originos", "nothing phone", "moto",
]

def source_keywords(src):
    """取源的关键词过滤配置；支持 "@mobile" 预设。"""
    kws = src.get("filter_keywords") or []
    if isinstance(kws, str):
        return MOBILE_KEYWORDS if kws.strip().lower() == "@mobile" else []
    return kws

def fetch_one(src, limit, only, focus, seen_at):
    """抓取单个数据源（线程池 worker），返回 (报告条目, 板块, 新增条目列表)。单源失败不抛出。"""
    name = src.get("name") or src.get("url") or "未命名源"
    block = src.get("block")
    entry = {"name": name, "block": block, "type": src.get("type"), "url": src.get("url")}
    if not src.get("enabled", True):
        entry.update(status="skipped", count=0, message="配置为 enabled=false，已跳过")
        log("跳过（未启用）：%s" % name)
        return entry, block, []
    if only and block not in only:
        entry.update(status="skipped", count=0, message="本轮 --only 未包含该板块")
        return entry, block, []
    if block not in BLOCK_MAP:
        entry.update(status="failed", count=0, message="未知板块：%s" % block)
        log("失败（未知板块）：%s" % name)
        return entry, block, []

    started = time.time()
    try:
        raw = http_get(src["url"])
        rows = parse_source(raw, src)
        kws = source_keywords(src)
        if kws:
            rows = [r for r in rows if match_keywords(r, kws)]
        cap = int(src.get("per_source_limit") or limit)
        rows = rows[:cap]
        added = []
        for row in rows:
            item = build_entry(row, src, seen_at)
            if item:
                added.append(item)
        entry.update(status="ok", count=len(added), elapsed=round(time.time() - started, 2))
        log("成功：%-16s %2d 条（%.1fs）" % (name, len(added), time.time() - started))
    except Exception as exc:  # 单源失败不阻断整体
        entry.update(status="failed", count=0,
                     elapsed=round(time.time() - started, 2),
                     message="%s: %s" % (type(exc).__name__, exc))
        log("失败：%-16s %s" % (name, exc))
        added = []
    finally:
        if focus:
            time.sleep(0.6)            # focus 模式保留源间节流，避免短时高频请求
    return entry, block, added

def fetch_sources(sources, limit, only, focus, workers=8):
    """并发抓取全部数据源，返回 (按板块分组的条目, 报告)。保留出错收集，单源失败不中断整体。"""
    grouped = {k: [] for k in BLOCK_KEYS}
    seen_at = iso_cst(now_cst())
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        fut_map = {ex.submit(fetch_one, src, limit, only, focus, seen_at): i
                   for i, src in enumerate(sources)}
        results = {}
        for fut in concurrent.futures.as_completed(fut_map):
            idx = fut_map[fut]
            try:
                results[idx] = fut.result()
            except Exception as exc:   # worker 内理论上不抛出，兜底防线程异常
                src = sources[idx]
                results[idx] = ({"name": src.get("name") or src.get("url") or "未命名源",
                                 "block": src.get("block"), "type": src.get("type"),
                                 "url": src.get("url"),
                                 "status": "failed", "count": 0,
                                 "message": "%s: %s" % (type(exc).__name__, exc)}, None, [])
    # 按配置顺序输出报告，保证结果稳定
    report_sources = []
    for idx in sorted(results):
        entry, block, items = results[idx]
        report_sources.append(entry)
        if block and block in grouped and items:
            grouped[block].extend(items)
    return grouped, report_sources

