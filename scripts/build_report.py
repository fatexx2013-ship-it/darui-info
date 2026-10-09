#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大瑞的信息网 · 首页数据与报告生成模块

输出 docs/data.json / docs/data.js（首页数据）与 docs/report.json（本轮抓取报告）。
docs/report.json 输出格式保持不变：generated_at / date / round / sources_* /
items_total / items_new_this_round / counts / translation / sources。
"""
import os

from common import (BLOCK_KEYS, BLOCK_MAP, iso_cst, log, now_cst, write_json, write_js)
from archive import build_blocks_payload
from translate import TRANS_STATS


def build_latest_payload(snapshot, date_str, round_label, index):
    """首页数据负载（docs/data.json / docs/data.js）。"""
    return {
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


def write_report(report_sources, snapshot, grouped, docs_dir, date_str, round_label):
    """写 docs/report.json 并输出本轮摘要日志，返回报告 dict。"""
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
        "translation": dict(TRANS_STATS),
        "sources": report_sources,
    }
    write_json(os.path.join(docs_dir, "report.json"), report)

    log("完成：本轮 %d 条，当日累计 %d 条；源 ok %d / failed %d"
        % (report["items_new_this_round"], snapshot["total"], ok, len(failed)))
    if TRANS_STATS.get("items") or TRANS_STATS.get("ok") or TRANS_STATS.get("hit") \
            or TRANS_STATS.get("fail") or TRANS_STATS.get("skip") \
            or TRANS_STATS.get("limit_skipped") or TRANS_STATS.get("translation_failures"):
        log("汉化：外文条目 %d，新译 %d，命中缓存 %d，失败 %d，跳过（本就是中文）%d，"
            "超限跳过 %d，降级跳过 %d"
            % (TRANS_STATS["items"], TRANS_STATS["ok"], TRANS_STATS["hit"],
               TRANS_STATS["fail"], TRANS_STATS["skip"], TRANS_STATS["limit_skipped"],
               TRANS_STATS["translation_failures"]))
    for s in failed:
        log("  · 失败源 %s：%s" % (s["name"], s.get("message")))
    return report

