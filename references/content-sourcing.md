# 素材搜集指南

research 阶段的目标：产出一份**去重后的候选清单**（`candidates.txt`，
每行 `URL` 或 `URL<TAB>标题`），供 draft 阶段筛选归类。

## 来源类型与工具

| 类型 | 工具/方式 | 说明 |
|---|---|---|
| 论文 | `scripts/fetch_arxiv.py` | arXiv Atom API；配置 `sources.arxiv_categories`（如 `["cs.RO","cs.CV"]`）；`--query` 可传任意 arXiv 查询式，`--days` 控制回溯窗口 |
| 开源项目 | `scripts/fetch_github_trends.py` | GitHub Search API `created:>CUTOFF topic:...` 按 star 排序；`--topic` 可多次；`--min-stars` 过滤；设 `GITHUB_TOKEN` 提高限速 |
| 中文视频/图文 | agent 用 WebSearch/WebFetch | B 站、公众号、机器之心、量子位等；见下"检索式模板" |
| 官方博客/Release | WebFetch | 已知重点项目的 blog/changelog 页直接抓 |

配置 `sources.sites` 是手工来源清单（名称 + URL + 备注），agent 在 research 时逐个过一遍。

## 检索式模板（WebSearch）

- 领域 + 时间限定：`具身智能 机器人 <最近一周日期范围>`
- 事件驱动：`<公司/项目名> 发布 OR 开源 OR 测评`
- 平台限定：`site:bilibili.com 具身智能`、`site:mp.weixin.qq.com 机器人 评测`
- 中文视频优先的场景（部分运营者偏好视频/图文而非论文列表）：先跑视频平台检索，
  arXiv 结果只挑有配套解读/代码的条目。

## arXiv 查询式要点

- 分类：`cat:cs.RO`；组合：`cat:cs.RO+OR+cat:cs.CV`；短语用 `%22...%22`。
- 排序：脚本默认 `submittedDate` 降序；`--max` 控制条数。
- 过滤：脚本按 published 时间截取 `--days` 窗口，超窗条目直接丢弃。

## GitHub 趋势要点

- Search API 的"趋势"近似 = 近期创建 + star 排序；要抓"老项目突然火"，
  改查询为 `topic:xxx pushed:>CUTOFF`（脚本目前用 created，可按需 --query 思路自行扩展）。
- 无 token 时限速 60 req/h，脚本会 WARN；批量抓取前先 `export GITHUB_TOKEN=...`。

## 去重策略（必须执行）

```bash
python3 scripts/dedup_urls.py --candidates candidates.txt --fuzzy \
    --issues-dir <周刊仓库>/issues
```

1. URL 规范化：剥除 `dedup.url_strip_params` 命中的跟踪参数（utm_*/spm/vd_source）、
   小写 scheme/host、去尾部斜杠、丢 fragment——同一篇文章带不同跟踪参数只算一条。
2. 精确比对：规范化 URL 命中历史 issue → 输出 `DUP` 并回指期号与标题。
3. 模糊比对（--fuzzy）：标题相似度 ≥ `dedup.title_threshold` 提示疑似重复
   （转载/改名场景），agent 人工裁决。
4. 只有 `NEW` 行进草稿；`DUP` 行如果确有重大更新（如项目大版本），
   可在条目里显式写"更新"字样并链接新 URL。

## 大陆网络注意

- arXiv API（export.arxiv.org）通常可直连但慢；脚本内置 3 次退避重试，仍失败 exit 1，
  可改走镜像（如 `https://xxx.itp.ac.cn/` 类 arXiv 镜像，自行替换 base URL）。
- GitHub API 时通时断；失败时降级为 WebSearch `site:github.com`。
- npm 相关操作（安装本 Skill 时）先设国内镜像：`npm config set registry https://registry.npmmirror.com`。

## 质量门槛（进草稿前）

- URL 真实可访问（agent 抽查 WebFetch，不逐个全验）。
- 有实质内容：拒绝纯营销稿、无信息量的转发。
- 与本期其他候选不重复角度（同一事件选信息量最大的一手来源）。
