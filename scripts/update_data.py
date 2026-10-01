#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大瑞的信息网 · 数据抓取脚本（Python 3，仅依赖标准库）

职责：
  1) 读取 config/sources.json 中的全部数据源，抓取 RSS/Atom、公开 JSON API、榜单 HTML；
  2) 归一化为统一条目结构（仅标题 + 摘要，不入库全文）；
  3) 写入当日快照 docs/archive/YYYY-MM-DD.json（同日多次抓取合并去重）；
  4) 重建归档索引 docs/archive/index.json；
  5) 输出首页数据 docs/data.json 与 file:// 可直读的 docs/data.js、docs/archive/*.js；
  6) 本轮抓取报告 docs/report.json（单源失败不阻断整体）。

用法：
  python3 scripts/update_data.py                 # 正常抓取
  python3 scripts/update_data.py --limit 15      # 每源最多取 15 条
  python3 scripts/update_data.py --only tech,buzz
  python3 scripts/update_data.py --date 2026-09-30   # 指定日期（调试用）
"""

import argparse
import hashlib
import html as html_mod
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

CST = timezone(timedelta(hours=8))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# 板块固定顺序与展示名（v2 规格：8 板块，顺序即前端标签展示顺序，首个为默认落地板块）
BLOCKS = [
    ("mobile", "手机动态", "新机发布、参数规格与新功能特性（用户最关注，默认落地板块）"),
    ("tianjin", "天津新闻", "天津本地民生、政策与城建动态（常驻地视角）"),
    ("domestic", "国内新闻", "国内民生、政策与产业动态"),
    ("geopolitics", "国际新闻", "国际时政与全球动态"),
    ("conflict", "地缘冲突", "国际冲突、战争与安全局势专题"),
    ("tech", "科技前沿", "与 AI 站互补，抖音视频主力选题来源"),
    ("oddities", "奇闻怪事", "全球离奇事件、自然奇观与科技奇事"),
    ("buzz", "网络舆论", "百度热搜 / 头条热榜 / B站热搜榜单聚合"),
]
BLOCK_KEYS = [b[0] for b in BLOCKS]
BLOCK_MAP = {b[0]: {"key": b[0], "name": b[1], "desc": b[2]} for b in BLOCKS}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)


# ---------------------------------------------------------------- 基础工具

def now_cst():
    return datetime.now(CST)


def iso_cst(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def log(msg):
    print("[%s] %s" % (now_cst().strftime("%H:%M:%S"), msg), flush=True)


def http_get(url, timeout=25, retries=2, headers=None):
    """带 UA、重试与超时的 GET，返回 bytes。"""
    hdrs = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        hdrs.update(headers)
    last_err = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, OSError) as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_err


TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)


def clean_text(raw, limit=240):
    """剥离 HTML 标签、反转义、压缩空白并截断。"""
    if not raw:
        return ""
    s = str(raw)
    s = SCRIPT_STYLE_RE.sub(" ", s)
    s = TAG_RE.sub(" ", s)
    s = html_mod.unescape(s)
    s = s.replace("\u00a0", " ")
    s = WS_RE.sub(" ", s).strip()
    if limit and len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s


def make_id(title, source_name):
    """稳定哈希：标题 + 来源。"""
    base = "%s||%s" % (clean_text(title, 400), source_name or "")
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


def parse_pub_date(raw):
    """解析 RFC822 / ISO8601 时间，统一转为北京时间 ISO 字符串。"""
    if not raw:
        return None
    s = str(raw).strip()
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return iso_cst(dt)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return iso_cst(dt)
    except Exception:
        return None


def sort_key(item):
    """最新在前：有发布时间按时间排，无时间按首次入库时间排。"""
    return (item.get("published_at") or item.get("first_seen") or "")


# ---------------------------------------------------------------- RSS / Atom

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


# ---------------------------------------------------------------- JSON API

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


# ---------------------------------------------------------------- 归一化

def build_entry(row, source, seen_at):
    title = clean_text(row.get("title"), 300)
    if not title:
        return None
    url = (row.get("url") or "").strip()
    source_name = source.get("name") or ""
    return {
        "id": make_id(title, source_name),
        "title": title,
        "summary": clean_text(row.get("summary"), 260),
        "source_name": source_name,
        "source_url": url,
        "published_at": row.get("published_at"),
        "first_seen": seen_at,
        "last_seen": seen_at,
        "block": source.get("block"),
        "credibility": source.get("credibility") or "二手转载",
        "tags": list(source.get("tags") or []),
    }


# ---------------------------------------------------------------- 文件读写

def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def js_payload(var_setup, obj):
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return "/* 自动生成，请勿手工编辑 */\n%s\n" % var_setup.replace("__PAYLOAD__", payload)


def write_js(path, var_setup, obj):
    """写出 file:// 可直接 <script> 引入的数据文件，避免 fetch 同源限制。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(js_payload(var_setup, obj))


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


# ---------------------------------------------------------------- 主流程

def match_keywords(row, keywords):
    """按源配置的 filter_keywords 过滤：标题或摘要命中任一关键词即保留（大小写不敏感）。"""
    hay = ((row.get("title") or "") + " " + (row.get("summary") or "")).lower()
    return any(str(k).lower() in hay for k in keywords)


# 「手机动态」板块相关度关键词预设：供综合类数码源（IT之家 / 手机中国 / 雷科技 / XDA /
# GSMArena / Google News 手机新机）过滤掉与手机无关的条目，配置中写 "@mobile" 即可引用。
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


def fetch_sources(sources, limit, only, focus):
    """抓取全部数据源，返回 (按板块分组的条目, 报告)。"""
    grouped = {k: [] for k in BLOCK_KEYS}
    report_sources = []
    seen_at = iso_cst(now_cst())

    for src in sources:
        name = src.get("name") or src.get("url") or "未命名源"
        block = src.get("block")
        entry = {"name": name, "block": block, "type": src.get("type"), "url": src.get("url")}
        if not src.get("enabled", True):
            entry.update(status="skipped", count=0, message="配置为 enabled=false，已跳过")
            report_sources.append(entry)
            log("跳过（未启用）：%s" % name)
            continue
        if only and block not in only:
            entry.update(status="skipped", count=0, message="本轮 --only 未包含该板块")
            report_sources.append(entry)
            continue
        if block not in BLOCK_MAP:
            entry.update(status="failed", count=0, message="未知板块：%s" % block)
            report_sources.append(entry)
            log("失败（未知板块）：%s" % name)
            continue

        started = time.time()
        try:
            raw = http_get(src["url"])
            rows = parse_source(raw, src)
            kws = source_keywords(src)
            if kws:
                rows = [r for r in rows if match_keywords(r, kws)]
            cap = int(src.get("per_source_limit") or limit)
            rows = rows[:cap]
            added = 0
            for row in rows:
                item = build_entry(row, src, seen_at)
                if item:
                    grouped[block].append(item)
                    added += 1
            entry.update(status="ok", count=added, elapsed=round(time.time() - started, 2))
            log("成功：%-16s %2d 条（%.1fs）" % (name, added, time.time() - started))
        except Exception as exc:  # 单源失败不阻断整体
            entry.update(status="failed", count=0,
                         elapsed=round(time.time() - started, 2),
                         message="%s: %s" % (type(exc).__name__, exc))
            log("失败：%-16s %s" % (name, exc))

        report_sources.append(entry)
        if focus:
            time.sleep(0.6)

    return grouped, report_sources


def dedupe(items):
    """同 id 去重：保留先出现的 first_seen，刷新 last_seen。"""
    out = {}
    for it in items:
        old = out.get(it["id"])
        if not old:
            out[it["id"]] = it
            continue
        old["last_seen"] = max(old["last_seen"], it["last_seen"])
        old["first_seen"] = min(old["first_seen"], it["first_seen"])
        if not old.get("summary") and it.get("summary"):
            old["summary"] = it["summary"]
        if not old.get("source_url") and it.get("source_url"):
            old["source_url"] = it["source_url"]
        if it.get("block") and old.get("block") != it.get("block"):
            old.setdefault("also_in", [])
            if it["block"] not in old["also_in"]:
                old["also_in"].append(it["block"])
    return out


def merge_day_snapshot(existing, fresh_by_block, date_str, round_label, now_iso):
    """当日快照合并：同日多次抓取累加去重，保留历史条目的 first_seen。"""
    old_items = (existing or {}).get("items") or []
    old_ids = {it["id"]: it for it in old_items}
    merged = []
    for key in BLOCK_KEYS:
        for it in fresh_by_block.get(key, []):
            prev = old_ids.get(it["id"])
            if prev:
                it["first_seen"] = min(prev.get("first_seen") or it["first_seen"], it["first_seen"])
                if not it.get("summary"):
                    it["summary"] = prev.get("summary") or ""
                if not it.get("published_at"):
                    it["published_at"] = prev.get("published_at")
            merged.append(it)
    merged_ids = {it["id"] for it in merged}
    for it in old_items:                      # 保留本轮未再出现的旧条目
        if it["id"] not in merged_ids:
            merged.append(it)

    uniq = list(dedupe(merged).values())
    uniq.sort(key=lambda x: (BLOCK_KEYS.index(x["block"]) if x.get("block") in BLOCK_KEYS else 99,
                             _neg_key(sort_key(x))))
    counts = {k: sum(1 for it in uniq if it.get("block") == k) for k in BLOCK_KEYS}
    rounds = list((existing or {}).get("rounds") or [])
    if round_label not in rounds:
        rounds.append(round_label)
    rounds.sort()
    return {
        "date": date_str,
        "rounds": rounds,
        "updated_at": now_iso,
        "total": len(uniq),
        "counts": counts,
        "items": uniq,
    }


def _neg_key(s):
    """让字符串按倒序参与元组排序。"""
    return tuple(-ord(c) for c in s)


def build_blocks_payload(snapshot):
    blocks = []
    for key in BLOCK_KEYS:
        items = [it for it in snapshot["items"] if it.get("block") == key]
        meta = BLOCK_MAP[key]
        blocks.append({
            "key": key, "name": meta["name"], "desc": meta["desc"],
            "count": len(items), "items": items,
        })
    return blocks


def rebuild_archive_index(archive_dir):
    days = []
    for fn in sorted(os.listdir(archive_dir)):
        if not re.match(r"^\d{4}-\d{2}-\d{2}\.json$", fn):
            continue
        snap = load_json(os.path.join(archive_dir, fn))
        if not snap:
            continue
        days.append({
            "date": snap.get("date") or fn[:-5],
            "rounds": snap.get("rounds") or [],
            "counts": snap.get("counts") or {},
            "total": snap.get("total") or len(snap.get("items") or []),
            "updated_at": snap.get("updated_at"),
        })
    days.sort(key=lambda d: d["date"], reverse=True)
    return {
        "updated_at": iso_cst(now_cst()),
        "total_days": len(days),
        "total_items": sum(d["total"] for d in days),
        "days": days,
    }


def main():
    ap = argparse.ArgumentParser(description="大瑞的信息网 · 数据抓取")
    ap.add_argument("--root", default=ROOT, help="项目根目录（默认脚本上级目录）")
    ap.add_argument("--config", default=None, help="数据源配置路径")
    ap.add_argument("--docs", default=None, help="站点目录路径")
    ap.add_argument("--limit", type=int, default=20, help="每个数据源最多入库条数")
    ap.add_argument("--only", default="", help="仅抓取指定板块，逗号分隔，如 tech,buzz")
    ap.add_argument("--round", default="", help="本轮标签（默认按北京时间自动推断 08:00 / 20:00）")
    ap.add_argument("--date", default="", help="指定归档日期 YYYY-MM-DD（调试用）")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    config_path = args.config or os.path.join(root, "config", "sources.json")
    docs_dir = args.docs or os.path.join(root, "docs")
    archive_dir = os.path.join(docs_dir, "archive")

    now = now_cst()
    date_str = args.date or now.strftime("%Y-%m-%d")
    round_label = args.round or ("08:00" if now.hour < 14 else "20:00")
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    focus = not only

    log("开始抓取 · 日期 %s · 轮次 %s" % (date_str, round_label))
    cfg = load_json(config_path)
    if not cfg or not cfg.get("sources"):
        log("错误：未找到有效数据源配置 %s" % config_path)
        return 1
    sources = cfg["sources"]

    grouped, report_sources = fetch_sources(sources, args.limit, only, focus)

    snapshot_path = os.path.join(archive_dir, "%s.json" % date_str)
    existing = load_json(snapshot_path)
    snapshot = merge_day_snapshot(existing, grouped, date_str, round_label, iso_cst(now_cst()))

    os.makedirs(archive_dir, exist_ok=True)
    write_json(snapshot_path, snapshot)
    write_js(os.path.join(archive_dir, "%s.js" % date_str),
             'window.WIS_SNAPSHOT = window.WIS_SNAPSHOT || {};\n'
             'window.WIS_SNAPSHOT["%s"] = __PAYLOAD__;' % date_str, snapshot)

    index = rebuild_archive_index(archive_dir)
    write_json(os.path.join(archive_dir, "index.json"), index)
    write_js(os.path.join(archive_dir, "index.js"), "window.WIS_ARCHIVE_INDEX = __PAYLOAD__;", index)

    latest = {
        "meta": {
            "site": "大瑞的信息网",
            "generatedAt": iso_cst(now_cst()),
            "date": date_str,
            "round": round_label,
            "rounds": snapshot["rounds"],
            "total": snapshot["total"],
            "counts": snapshot["counts"],
            "archive_days": index["total_days"],
            "archive_items": index["total_items"],
            "blocks": [{"key": k, "name": BLOCK_MAP[k]["name"], "desc": BLOCK_MAP[k]["desc"]}
                       for k in BLOCK_KEYS],
        },
        "blocks": build_blocks_payload(snapshot),
    }
    write_json(os.path.join(docs_dir, "data.json"), latest)
    write_js(os.path.join(docs_dir, "data.js"), "window.WIS_DATA = __PAYLOAD__;", latest)

    ok = sum(1 for s in report_sources if s["status"] == "ok")
    failed = [s for s in report_sources if s["status"] == "failed"]
    report = {
        "generated_at": iso_cst(now_cst()),
        "date": date_str,
        "round": round_label,
        "sources_total": len(report_sources),
        "sources_ok": ok,
        "sources_failed": len(failed),
        "items_total": snapshot["total"],
        "items_new_this_round": sum(len(v) for v in grouped.values()),
        "counts": snapshot["counts"],
        "sources": report_sources,
    }
    write_json(os.path.join(docs_dir, "report.json"), report)

    log("完成：本轮 %d 条，当日累计 %d 条；源 ok %d / failed %d"
        % (report["items_new_this_round"], snapshot["total"], ok, len(failed)))
    for s in failed:
        log("  · 失败源 %s：%s" % (s["name"], s.get("message")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
