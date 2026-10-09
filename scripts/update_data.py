#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大瑞的信息网 · 数据抓取入口（薄编排层）

职责：解析命令行参数、加载配置与翻译缓存，串联各模块完成
抓取（fetch_sources）-> 当日快照合并（archive）-> 补译（translate）->
归档索引（archive）-> 首页数据与报告（build_report）的端到端流程。

用法：
  python3 scripts/update_data.py                 # 正常抓取
  python3 scripts/update_data.py --limit 15      # 每源最多取 15 条
  python3 scripts/update_data.py --only tech,buzz
  python3 scripts/update_data.py --date 2026-09-30   # 指定日期（调试用）

模块拆分（由原单文件按职责拆分，行为保持一致）：
  scripts/common.py        常量与基础工具
  scripts/translate.py     外文翻译（每轮限流 + 连续失败降级）
  scripts/fetch_sources.py 数据源解析与并发抓取
  scripts/archive.py       当日快照与归档索引
  scripts/build_report.py  首页数据与报告生成
"""

import argparse
import os
import sys

from common import ROOT, iso_cst, load_json, log, now_cst, write_json, write_js
from translate import (TRANS_ENABLED, TRANS_FAIL_THRESHOLD, TRANS_LIMIT,
                       backfill_translations, load_trans_cache, save_trans_cache)
from fetch_sources import fetch_sources
from archive import merge_day_snapshot, rebuild_archive_index
from build_report import build_latest_payload, write_report


def main():
    ap = argparse.ArgumentParser(description="大瑞的信息网 · 数据抓取")
    ap.add_argument("--root", default=ROOT, help="项目根目录（默认脚本上级目录）")
    ap.add_argument("--config", default=None, help="数据源配置路径")
    ap.add_argument("--docs", default=None, help="站点目录路径")
    ap.add_argument("--limit", type=int, default=20, help="每个数据源最多入库条数")
    ap.add_argument("--only", default="", help="仅抓取指定板块，逗号分隔，如 tech,buzz")
    ap.add_argument("--workers", type=int, default=8, help="并发抓取线程数（默认 8）")
    ap.add_argument("--round", default="", help="本轮标签（默认按北京时间自动推断 08:00 / 20:00）")
    ap.add_argument("--date", default="", help="指定归档日期 YYYY-MM-DD（调试用）")
    ap.add_argument("--no-translate", action="store_true", help="关闭外文条目的自动汉化")
    ap.add_argument("--translate-limit", type=int, default=200,
                    help="本轮最多汉化条数（默认 200，0 = 不限）")
    ap.add_argument("--translation-fail-threshold", type=int, default=10,
                    help="翻译连续失败达到该次数后降级跳过本轮剩余翻译（默认 10）")
    ap.add_argument("--no-backfill", action="store_true", help="不给存量旧条目补译文")
    ap.add_argument("--backfill-limit", type=int, default=0, help="存量补译条数上限（0 = 不限）")
    args = ap.parse_args()

    global TRANS_ENABLED, TRANS_LIMIT, TRANS_FAIL_THRESHOLD
    TRANS_ENABLED = not args.no_translate
    TRANS_LIMIT = max(0, args.translate_limit)
    TRANS_FAIL_THRESHOLD = max(1, args.translation_fail_threshold)

    root = os.path.abspath(args.root)
    config_path = args.config or os.path.join(root, "config", "sources.json")
    docs_dir = args.docs or os.path.join(root, "docs")
    archive_dir = os.path.join(docs_dir, "archive")
    trans_cache_path = os.path.join(root, "config", "trans_cache.json")

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

    if TRANS_ENABLED:
        load_trans_cache(trans_cache_path)
    else:
        log("外文汉化：已按 --no-translate 关闭")

    grouped, report_sources = fetch_sources(sources, args.limit, only, focus,
                                            workers=args.workers)

    snapshot_path = os.path.join(archive_dir, "%s.json" % date_str)
    existing = load_json(snapshot_path)
    snapshot = merge_day_snapshot(existing, grouped, date_str, round_label,
                                  iso_cst(now_cst()))

    if TRANS_ENABLED and not args.no_backfill:
        backfill_translations(snapshot, max(0, args.backfill_limit))
        save_trans_cache(trans_cache_path)

    os.makedirs(archive_dir, exist_ok=True)
    write_json(snapshot_path, snapshot)

    index = rebuild_archive_index(archive_dir)
    write_json(os.path.join(archive_dir, "index.json"), index)
    write_js(os.path.join(archive_dir, "index.js"), "window.WIS_ARCHIVE_INDEX = __PAYLOAD__;", index)

    latest = build_latest_payload(snapshot, date_str, round_label, index)
    write_json(os.path.join(docs_dir, "data.json"), latest)
    write_js(os.path.join(docs_dir, "data.js"), "window.WIS_DATA = __PAYLOAD__;", latest)

    write_report(report_sources, snapshot, grouped, docs_dir, date_str, round_label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
