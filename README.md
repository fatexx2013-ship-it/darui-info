---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: b82594f1be8e85c02fc42784acc7d5b8_0b4bfdcfbce511f18442525400de85a5
    ReservedCode1: KlnTwpH6QWgMUenx2lq9H+ptsle6ST9ows/BNtjjWuw79EuSauctZcjoM0kBOrt3mRP1cuNr0SrABGqdetwjPxpRvj+iKSSsTqEB3vXflHnJ1MnUv6R+Xt1rnZMuiVQ0VWJ23y6tfKmJaavTSDjrTtL9B7a0ixrC+l/zTPP0/jcaLkOCVY0roPz0hxA=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: b82594f1be8e85c02fc42784acc7d5b8_0b4bfdcfbce511f18442525400de85a5
    ReservedCode2: KlnTwpH6QWgMUenx2lq9H+ptsle6ST9ows/BNtjjWuw79EuSauctZcjoM0kBOrt3mRP1cuNr0SrABGqdetwjPxpRvj+iKSSsTqEB3vXflHnJ1MnUv6R+Xt1rnZMuiVQ0VWJ23y6tfKmJaavTSDjrTtL9B7a0ixrC+l/zTPP0/jcaLkOCVY0roPz0hxA=
---



# 大瑞的信息网

个人自用的**全球热点新闻聚合静态站**：每日两更，八大板块，顶部**标签一点即切板块**，带归档与检索，托管 GitHub Pages，本地双击即可用 `file://` 打开预览。

> 定位：抖音视频**选题材料库**。只保留标题 + 摘要 + 原始链接，不转载正文，不对外推广、不投放广告。

---

## 功能概览

| 能力 | 说明 |
|---|---|
| 八大板块（标签式导航） | 手机动态 `mobile`（默认落地）/ 天津新闻 `tianjin` / 国内新闻 `domestic` / 国际新闻 `geopolitics` / 地缘冲突 `conflict` / 科技前沿 `tech` / 奇闻怪事 `oddities` / 网络舆论 `buzz` |
| 板块切换 | 顶部 sticky 横向标签栏，点标签即进对应板块（不再是索引勾选式筛选）；标签带条数角标，窄屏可横向滑动 |
| 每日两更 | GitHub Actions 在 UTC 00:00 / 12:00（北京时间 08:00 / 20:00）自动抓取并提交 |
| 外文自动汉化 | 外文源（国际新闻 / 地缘冲突 / 科技外媒等）条目自动附中文译文：标题显示中文、原文小字保留在下方；摘要同样中文优先。主通道 Google 免密端点，备通道 MyMemory，均失败则回退原文，绝不阻断抓取 |
| 归档快照 | 每天一份 `docs/archive/YYYY-MM-DD.json`，同日多轮抓取**合并去重**，首见时间保留 |
| 归档索引 | `docs/archive/index.json` 汇总每日轮次、条数、板块分布 |
| 站内检索 | 首页检索**作用于当前选中板块**（仅最新一期 / 含历史归档）；归档页可先切板块，再按日期或跨归档检索 |
| file:// 直开 | 数据同时产出 `.js` 注入版本（`data.js` / `archive/*.js`），无需本地服务器 |
| 容错 | 单个数据源失败不影响整体，失败原因写入 `docs/report.json` 并在 Actions 中告警 |

### 板块与数据源

共 **39 个源**（RSS / 公开 JSON / 热榜解析器），按板块划分：

| 板块 | 源数 | 代表源 |
|---|---|---|
| 手机动态 | 8 | IT之家、cnBeta、手机中国、GSMArena、9to5Google、XDA Developers、雷科技、Google News·手机新机 |
| 天津新闻 | 3 | Google News·天津、Google News·天津民生、Bing News·天津 |
| 国内新闻 | 5 | 中国新闻网·滚动、界面新闻、人民网·时政、极客公园、少数派 |
| 国际新闻 | 4 | BBC World、The Guardian World、Al Jazeera、NYT World |
| 地缘冲突 | 7 | 联合国新闻·中文、ReliefWeb（联合国人道协调厅）、Crisis Group、Defense News、War on the Rocks、Google News·地缘冲突、Google News·中东局势 |
| 科技前沿 | 6 | Hacker News、TechCrunch、The Verge、Ars Technica、量子位、雷峰网 |
| 奇闻怪事 | 3 | Oddity Central、Atlas Obscura、Boing Boing |
| 网络舆论 | 3 | 百度热搜、今日头条热榜、B站热搜（内置解析器） |

> **手机动态焦点**：该板块综合类数码源（IT之家 / cnBeta / 手机中国 / GSMArena / XDA / 雷科技 / Google News·手机新机）在配置里使用 `"filter_keywords": "@mobile"`，由脚本内置的 `MOBILE_KEYWORDS` 词表按标题+摘要过滤，只留新机型型号、参数规格、功能特色等条目，滤掉汽车 / 半导体 / 泛数码噪音。

---

## 目录结构

```
world-intel-station/
├── config/
│   └── sources.json            # 数据源配置（39 源，分属 8 板块）
├── scripts/
│   ├── update_data.py          # 抓取 + 归一化 + 归档 + 生成站点数据（仅用 Python 标准库）
│   └── run_local.sh            # 本地一键抓取 + 预览
├── docs/                        # GitHub Pages 站点根目录（Pages 源设为 main 分支 /docs）
│   ├── index.html              # 首页：顶部标签栏 + 板块视图 + 板块内检索
│   ├── archive.html            # 归档页：标签切换 + 日期浏览 + 跨归档检索
│   ├── styles.css              # 深色霓虹卡片主题
│   ├── common.js               # 公共渲染（含 tabsHTML 标签栏）/ 数据加载 / 检索逻辑
│   ├── app.js                  # 首页逻辑（标签切换、默认落地首个板块）
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
python3 scripts/update_data.py                 # 全量抓取（约 1 分钟，39 源）
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

> 首次推送前，`docs/` 下已包含本地抓好的数据，可直接预览。
> 若想减少仓库体积，可定期清理久远的 `docs/archive/YYYY-MM-DD.*`，并同步更新 `index.json`（重跑一次脚本会自动重建索引）。

---

## 外文自动汉化

外文源（BBC / The Guardian / Al Jazeera / NYT / ReliefWeb / Defense News / TechCrunch / The Verge / Ars Technica / Boing Boing 等）的条目会自动附上中文译文，与 AI 站的汉化口径一致。

- **判定**：按内容判定而非按源硬编码——CJK 占比 ≤ 15% 且含拉丁字母的文本才翻译，中文条目自动跳过。
- **通道**：主 `translate.googleapis.com` 免密端点（质量优先），失败自动降级到 `api.mymemory.translated.net`（与 AI 站同接口）；两者都失败则回退原文，**绝不阻断抓取**。
- **字段**：译文写入条目的 `title_zh` / `summary_zh`，原文 `title` / `summary` 完整保留；前端标题显中文、原文以小字附在下方，摘要中文优先。
- **缓存**：译文累积在 `config/trans_cache.json`（随仓库提交），已译文本不重复请求，后续轮次接近零开销。
- **存量补译**：每轮抓取后会扫描快照中缺译文的外文旧条目自动补齐，新旧条目不会中英混杂。
- **开关**：`--no-translate` 关闭汉化；`--translate-limit N` 限制本轮新译条数；`--no-backfill` 跳过存量补译；`--backfill-limit N` 限制存量补译条数。

```bash
python3 scripts/update_data.py                        # 抓取 + 汉化（默认全开）
python3 scripts/update_data.py --no-translate         # 只要原文
python3 scripts/update_data.py --only __none__        # 不抓取，只给存量快照补译文
```

---

## 数据源配置（`config/sources.json`）

```jsonc
{
  "version": "2.0",
  "sources": [
    {
      "name": "IT之家",                  // 展示名
      "block": "mobile",                 // 所属板块（8 板块键见上表）
      "type": "rss",                     // rss | api | html
      "url": "https://www.ithome.com/rss/",
      "credibility": "主流媒体",          // 一手官方 | 主流媒体 | 二手转载
      "tags": ["手机", "数码"],
      "enabled": true,
      "per_source_limit": 20,            // 可覆盖全局 --limit
      "filter_keywords": "@mobile"       // 关键词过滤：命中标题或摘要任一即保留
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
- **关键词过滤**：`filter_keywords` 支持显式词数组，或 `"@mobile"` 预设（脚本内置 `MOBILE_KEYWORDS`，用于手机动态板块综合数码源的降噪）。
- **不可用即关**：配置 `"enabled": false` 即跳过该源，不必删配置。
- 已知限制：微博热搜、知乎热榜的公开接口有反爬（403），36氪 / 机器之心的公开 feed 已上反爬挑战页，第三方聚合 API 多已失效，因此**网络舆论**板块以百度 / 头条 / B站榜单为主。

---

## 条目结构与去重规则

```jsonc
{
  "id": "e8b08b8fcf9a2c11",        // sha1(标题 + 来源名) 前 16 位，稳定可复现
  "title": "……",                   // 原始标题（外文源为原文，完整保留）
  "title_zh": "……",                // 外文条目的中文译文；中文源为空串
  "summary": "……",                  // 纯文本摘要，截断至 ~260 字
  "summary_zh": "……",              // 摘要中文译文；中文源为空串
  "source_name": "IT之家",
  "source_url": "https://……",
  "published_at": "2026-10-01T08:00:00+08:00",  // 源未提供则为 null
  "first_seen": "2026-10-01T08:45:00+08:00",
  "last_seen": "2026-10-01T08:45:00+08:00",
  "block": "mobile",
  "credibility": "主流媒体",
  "tags": ["手机", "数码"]
}
```

- **去重**：以 `id`（标题 + 来源）为准。同一日内多轮抓取只保留一条，刷新 `last_seen`、保留最早的 `first_seen`；跨板块重复时会记录 `also_in`。
- **排序**：按板块固定顺序（`meta.blocks` 即前端标签顺序），板块内按发布时间倒序（无发布时间则按首次入库时间）。
- **不存正文**：仅标题与摘要，点击跳转原始来源。

---

## 使用注意

- **版权**：标题与摘要版权归各原始来源所有，本站仅作个人选题参考，不用于再发布或商业用途。
- **红线过滤**：国际新闻 / 地缘冲突板块仅作背景了解，**不进抖音选题**；选题取用请自行规避合规红线（军事、时政敏感、金融荐股、换脸克隆、去水印等）。
- **抓取礼节**：默认每个源最多 20 条、单次抓取约 1 分钟，请勿把频率调到分钟级；新增源前先确认其 robots 与订阅条款。
- **数据可逆**：全部数据都在 `docs/`，删除即清空；配置改动只影响下一次抓取。
*（内容由AI生成，仅供参考）*
