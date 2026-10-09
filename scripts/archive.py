#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大瑞的信息网 · 当日快照与归档索引模块

负责当日快照合并去重（同日多次抓取累加，保留 first_seen）、板块负载构建、
归档索引重建。每日快照仅保留 .json（.js 由前端 fetch 加载，历史 .js 已停止生成）。
"""
import os
import re

from common import (BLOCK_KEYS, BLOCK_MAP, iso_cst, load_json, now_cst, sort_key)

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

