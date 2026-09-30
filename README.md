---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: b82594f1be8e85c02fc42784acc7d5b8_9952215abcce11f18442525400de85a5
    ReservedCode1: oM8BTLOVjK0vpxbRoCiYDIJq8rlhIslJqy2IlsO2jIIzPxXcNUl2gVaoF1MZay1LUknTVzbLjx/fPAFqOZggA87/JR51BZU7EqcGXdRsZYOG2GqC4gGORNtY4eGCmHTxRg+Jsx7etnItZxUtLwQdgef+xBeeuM6VxtRb41QTgQnsN9jhWRLweQRNKPI=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: b82594f1be8e85c02fc42784acc7d5b8_9952215abcce11f18442525400de85a5
    ReservedCode2: oM8BTLOVjK0vpxbRoCiYDIJq8rlhIslJqy2IlsO2jIIzPxXcNUl2gVaoF1MZay1LUknTVzbLjx/fPAFqOZggA87/JR51BZU7EqcGXdRsZYOG2GqC4gGORNtY4eGCmHTxRg+Jsx7etnItZxUtLwQdgef+xBeeuM6VxtRb41QTgQnsN9jhWRLweQRNKPI=
---

# 大瑞的信息网

个人自用的**全球热点新闻聚合静态站**：每日两更，五大板块，带归档与检索，托管 GitHub Pages，本地双击即可用 `file://` 打开预览。

> 定位：抖音视频**选题材料库**。只保留标题 + 摘要 + 原始链接，不转载正文，不对外推广、不投放广告。

---

## 功能概览

| 能力 | 说明 |
|---|---|
| 五大板块 | 国际观察 `geopolitics` / 奇闻怪事 `oddities` / 国内热点 `domestic` / 网络舆论 `buzz` / 科技前沿 `tech` |
| 每日两更 | GitHub Actions 在 UTC 00:00 / 12:00（北京时间 08:00 / 20:00）自动抓取并提交 |
| 归档快照 | 每天一份 `docs/archive/YYYY-MM-DD.json`，同日多轮抓取**合并去重**，首见时间保留 |
| 归档索引 | `docs/archive/index.json` 汇总每日轮次、条数、板块分布 |
| 站内检索 | 首页支持「仅最新一期 / 含历史归档」关键词 + 板块 + 日期范围检索；归档页支持跨归档检索 |
| file:// 直开 | 数据同时产出 `.js` 注入版本（`data.js` / `archive/*.js`），无需本地服务器 |
| 容错 | 单个数据源失败不影响整体，失败原因写入 `docs/report.json` 并在 Actions 中告警 |

---

## 目录结构

```
world-intel-station/
├── config/
│   └── sources.json            # 数据源配置（19+ 源，分属 5 板块）
├── scripts/
│   ├── update_data.py          # 抓取 + 归一化 + 归档 + 生成站点数据（仅用 Python 标准库）
│   └── run_local.sh            # 本地一键抓取 + 预览
├── docs/                        # GitHub Pages 站点根目录（Pages 源设为 main 分支 /docs）
│   ├── index.html              # 首页：板块卡片 + 检索面板
│   ├── archive.html            # 归档页：日期浏览 + 跨归档检索
│   ├── styles.css              # 深色霓虹卡片主题
│   ├── common.js               # 公共渲染 / 数据加载 / 检索逻辑
│   ├── app.js                  # 首页逻辑
│   ├── archive.js              # 归档页逻辑
│   ├── data.json / data.js     # 最新一期数据（构建产物）
│   ├── report.json             # 最近一次抓取报告（构建产物）
│   └── archive/
│       ├── index.json / index.js         # 归档索引（构建产物）
│       └── YYYY-MM-DD.json / .js         # 每日快照（构建产物）
├── .github/workflows/
│   └── update-data.yml         # 定时抓取工作流
└── README.md
```

---

## 本地使用

### 1. 抓取数据

```bash
cd world-intel-station
python3 scripts/update_data.py                 # 全量抓取（约 30 秒）
python3 scripts/update_data.py --only tech,buzz # 只抓指定板块
python3 scripts/update_data.py --limit 15       # 每源最多 15 条
python3 scripts/update_data.py --date 2026-09-29 # 指定归档日期（补数据/调试）
```

仅依赖 Python 3.8+ 标准库，**无需 pip install**。

### 2. 预览

```bash
open docs/index.html          # macOS：直接双击也能用（file:// 可直读）
# 或起一个本地服务（更接近线上效果）
python3 -m http.server 8080 --directory docs
```

或一键脚本：

```bash
bash scripts/run_local.sh      # 抓取 + 打开本地预览
```

---

## 部署到 GitHub Pages（个人自用）

1. 把整个 `world-intel-station/` 作为仓库根目录推送到 GitHub（建议 **Private** 仓库，Pages 私有仓库需 Pro；若用 Free 账号，站点公开但内容仅为标题+链接）。
2. 仓库 **Settings → Actions → General → Workflow permissions** 选择 *Read and write permissions*（工作流需要提交数据）。
3. 仓库 **Settings → Pages**：Source 选 `Deploy from a branch`，分支选 `main`，目录选 **`/docs`**。
4. 到 **Actions** 页手动触发一次 `更新全球热点数据`（workflow_dispatch），确认抓取与提交正常。
5. 之后每 UTC 00:00 / 12:00 自动更新，无需干预。

> 首次推送前，`docs/` 下已包含本地抓好的一天数据，可直接预览。
> 若想减少仓库体积，可定期清理久远的 `docs/archive/YYYY-MM-DD.*`，并同步更新 `index.json`（重跑一次脚本会自动重建索引）。

---

## 数据源配置（`config/sources.json`）

```jsonc
{
  "version": "1.0.0",
  "sources": [
    {
      "name": "BBC World",              // 展示名
      "block": "geopolitics",           // 所属板块
      "type": "rss",                    // rss | api | html
      "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
      "credibility": "主流媒体",         // 一手官方 | 主流媒体 | 二手转载
      "tags": ["国际", "时政"],
      "enabled": true,
      "per_source_limit": 20            // 可覆盖全局 --limit
    }
  ]
}
```

- **`type: rss`**：标准 RSS 2.0 / Atom，自动解析标题、链接、摘要、发布时间，并对不规范 XML 做容错。
- **`type: api`**：公开 JSON 接口，需配 `map` 指定字段路径：

```jsonc
{
  "name": "某 JSON 源", "block": "tech", "type": "api",
  "url": "https://example.com/api.json",
  "map": { "list_path": "data.list", "title": "title", "url": "link", "summary": "desc", "published": "pub_time" }
}
```

- **榜单类**用内置 `parser`：`baidu_hot`（百度热搜）、`toutiao_hot`（今日头条热榜）、`bilibili_hot`（B站热搜）。
- **不可用即关**：配置 `"enabled": false` 即跳过该源，不必删配置。
- 已知限制：微博热搜、知乎热榜的公开接口有反爬（403），第三方聚合 API 多已失效，因此**网络舆论**板块以百度 / 头条 / B站榜单为主。

---

## 条目结构与去重规则

```jsonc
{
  "id": "e8b08b8fcf9a2c11",        // sha1(标题 + 来源名) 前 16 位，稳定可复现
  "title": "……",
  "summary": "……",                  // 纯文本摘要，截断至 ~260 字
  "source_name": "BBC World",
  "source_url": "https://……",
  "published_at": "2026-09-30T18:03:00+08:00",  // 源未提供则为 null
  "first_seen": "2026-09-30T20:49:00+08:00",
  "last_seen": "2026-09-30T20:49:00+08:00",
  "block": "geopolitics",
  "credibility": "主流媒体",
  "tags": ["国际", "时政"]
}
```

- **去重**：以 `id`（标题 + 来源）为准。同一日内多轮抓取只保留一条，刷新 `last_seen`、保留最早的 `first_seen`；跨板块重复时会记录 `also_in`。
- **排序**：按板块固定顺序，板块内按发布时间倒序（无发布时间则按首次入库时间）。
- **不存正文**：仅标题与摘要，点击跳转原始来源。

---

## 使用注意

- **版权**：标题与摘要版权归各原始来源所有，本站仅作个人选题参考，不用于再发布或商业用途。
- **红线过滤**：国际观察板块仅作背景了解，**不进抖音选题**；选题取用请自行规避合规红线（军事、时政敏感、金融荐股、换脸克隆、去水印等）。
- **抓取礼节**：默认每个源最多 20 条、单次抓取约 30 秒，请勿把频率调到分钟级；新增源前先确认其 robots 与订阅条款。
- **数据可逆**：全部数据都在 `docs/`，删除即清空；配置改动只影响下一次抓取。
*（内容由AI生成，仅供参考）*
