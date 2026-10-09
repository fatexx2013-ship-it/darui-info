#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大瑞的信息网 · 外文自动翻译模块

目标：外文源（国际新闻 / 地缘冲突 / 科技外媒等）条目附带中文译文，与 AI 站口径一致。
通道：主 Google 免密端点（质量好），备 MyMemory 免费接口；两者均失败则保留原文，绝不阻断抓取。
稳定性：每轮翻译条数上限（TRANS_LIMIT，默认 200）；连续失败达 TRANS_FAIL_THRESHOLD 后
降级跳过本轮剩余翻译（统计计入 translation_failures），避免免费接口抖动拖垮整体。
产物：条目新增 title_zh / summary_zh 字段（原文 title / summary 完整保留，便于溯源核对）。
线程安全：并发抓取时通过 _TRANS_LOCK 串行化请求与统计计数。
"""
import json
import re
import threading
import time
import urllib.parse

from common import log, http_get, load_json, write_json

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff]")

LATIN_RE = re.compile(r"[A-Za-z]")

TRANS_CACHE = {}

TRANS_STATS = {"skip": 0, "hit": 0, "ok": 0, "fail": 0, "items": 0,
               "limit_skipped": 0, "translation_failures": 0}

TRANS_ENABLED = True

TRANS_LIMIT = 200

TRANS_FAIL_THRESHOLD = 10

TRANS_DELAY = 0.25

_LAST_CALL = [0.0]

_TRANS_LOCK = threading.Lock()

_TRANS_FAIL_STREAK = [0]

_TRANS_DEGRADED = [False]

def is_foreign(text):
    """判断是否为需要翻译的外文：已含中文（CJK 占比 > 15%）则跳过；无拉丁字母（纯数字/符号）也跳过。"""
    s = (text or "").strip()
    if len(s) < 3:
        return False
    if CJK_RE.search(s) and len(CJK_RE.findall(s)) > len(s) * 0.15:
        return False
    return len(LATIN_RE.findall(s)) >= 3

def claim_item():
    """占用一个翻译名额：未达本轮上限则计数并返回 True（线程安全）。

    降级中返回 True 但不占名额，交由 translate() 记录降级跳过次数。
    """
    with _TRANS_LOCK:
        if _TRANS_DEGRADED[0]:
            return True
        if TRANS_LIMIT > 0 and TRANS_STATS["items"] >= TRANS_LIMIT:
            return False
        TRANS_STATS["items"] += 1
        return True

def _throttle():
    wait = _LAST_CALL[0] + TRANS_DELAY - time.time()
    if wait > 0:
        time.sleep(wait)
    _LAST_CALL[0] = time.time()

def _via_google(text):
    """Google 免密端点，返回中文译文；失败抛异常。"""
    url = ("https://translate.googleapis.com/translate_a/single"
           "?client=gtx&sl=auto&tl=zh-CN&dt=t&q=" + urllib.parse.quote(text[:480]))
    data = json.loads(http_get(url, timeout=15, retries=1).decode("utf-8", "replace"))
    segs = (data[0] if isinstance(data, list) and data else None) or []
    out = "".join(seg[0] for seg in segs if isinstance(seg, list) and seg and seg[0])
    return out.strip()

def _via_mymemory(text):
    """MyMemory 免费接口（与 AI 站同源），返回中文译文；失败抛异常。"""
    url = ("https://api.mymemory.translated.net/get?q=" +
           urllib.parse.quote(text[:450]) + "&langpair=en|zh-CN")
    info = json.loads(http_get(url, timeout=15, retries=1).decode("utf-8", "replace"))
    out = ((info.get("responseData") or {}).get("translatedText") or "").strip()
    if re.search(r"MYMEMORY WARNING|INVALID", out, re.I):
        return ""
    return out

def _translate_locked(s):
    """持锁执行翻译（调用方已持有 _TRANS_LOCK）：主 Google，备 MyMemory，均失败返回空串。"""
    out = ""
    for fn in (_via_google, _via_mymemory):
        try:
            out = fn(s)
        except Exception as exc:
            log("  翻译通道不可用（%s）：%s" % (fn.__name__, exc))
        _throttle()
        if out:
            break
    if out:
        TRANS_CACHE[s] = out
        TRANS_STATS["ok"] += 1
        _TRANS_FAIL_STREAK[0] = 0            # 成功即重置连续失败计数
    else:
        TRANS_CACHE[s] = ""                  # 仅本轮记忆，不落盘，下轮可重试
        TRANS_STATS["fail"] += 1
        _TRANS_FAIL_STREAK[0] += 1
        if _TRANS_FAIL_STREAK[0] >= TRANS_FAIL_THRESHOLD:
            _TRANS_DEGRADED[0] = True        # 连续失败达阈值：本轮剩余翻译降级跳过
            log("  翻译连续失败 %d 次，本轮剩余翻译降级跳过" % TRANS_FAIL_THRESHOLD)
    return out

def translate(text):
    """外文 -> 中文；不需翻译或翻译失败时返回空串（调用方回退原文展示）。线程安全。"""
    if not TRANS_ENABLED or not text:
        return ""
    s = str(text).strip()
    if not is_foreign(s):
        with _TRANS_LOCK:
            TRANS_STATS["skip"] += 1
        return ""
    if s in TRANS_CACHE:
        with _TRANS_LOCK:
            TRANS_STATS["hit"] += 1
        return TRANS_CACHE[s]

    # 串行化翻译请求：天然保证节流与统计计数安全；网络 IO 期间其他线程等待，抓取仍并行
    with _TRANS_LOCK:
        if _TRANS_DEGRADED[0]:
            # 降级中：不再请求通道，记录被跳过的条数
            TRANS_STATS["translation_failures"] += 1
            return ""
        return _translate_locked(s)

def load_trans_cache(path):
    data = load_json(path, {}) or {}
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, str) and v:
                TRANS_CACHE[k] = v
    log("翻译缓存载入 %d 条" % len(TRANS_CACHE))

def save_trans_cache(path):
    ok = {k: v for k, v in TRANS_CACHE.items() if v}
    write_json(path, ok)
    log("翻译缓存写回 %d 条" % len(ok))

def backfill_translations(snapshot, limit=0):
    """给存量条目补译文：本轮未再抓到的旧条目（含归档遗留）也能补齐，避免新旧条目中英混杂。"""
    if not TRANS_ENABLED:
        return 0
    done = 0
    for it in (snapshot or {}).get("items") or []:
        if limit and done >= limit:
            break
        title, summary = it.get("title") or "", it.get("summary") or ""
        need_title = not it.get("title_zh") and is_foreign(title)
        need_sum = not it.get("summary_zh") and is_foreign(summary)
        if not need_title and not need_sum:
            continue
        if need_title:
            it["title_zh"] = translate(title)
        if need_sum:
            it["summary_zh"] = translate(summary)
        done += 1
    if done:
        log("存量补译：本轮补齐 %d 条" % done)
    return done

