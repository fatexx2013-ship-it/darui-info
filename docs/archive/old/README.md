# 归档压缩说明（old/）

本目录存放按日快照 `YYYY-MM-DD.json` 的 gzip 压缩版（.json.gz），用于在保留历史数据的同时减小仓库体积。

## 归档范围
- 2026-09-30.json.gz
- 2026-10-01.json.gz
- 2026-10-02.json.gz

归档规则：超过保留窗口（最近 7 天）的每日快照压缩为 .json.gz 后移入本目录，原 .json 从 `docs/archive/` 移除；
每日快照仅保留 .json（数据源），不再生成同名 .js 注入文件（前端改为 fetch JSON 加载，file:// 直开时历史日期需本地起服务）。

## 恢复方式
如需恢复某天到归档列表，解压回 `docs/archive/` 并重跑一次脚本即可重建索引：

```bash
gunzip -k docs/archive/old/2026-09-30.json.gz -c > docs/archive/2026-09-30.json
python3 scripts/update_data.py --only __none__ --no-translate
```
