#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大瑞的信息网 · 公共基础模块

提供常量（时区 / UA / 板块规格 / 路径）、日志与 HTTP 工具、文本清洗、
ID 与时间解析、JSON / JS 数据文件读写。仅供 scripts/ 内模块复用。
"""
import hashlib
import html as html_mod
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

CST = timezone(timedelta(hours=8))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

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

