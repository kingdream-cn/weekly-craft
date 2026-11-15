# Changelog

本文件记录 weekly-craft 的所有重要变更。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。
**major** = issue 格式规范或配置 schema 的不兼容变更。

## [Unreleased]

### Dual-repo editorial integration — 2026-11-15

- 自动生成私有 `review.md`：全部候选按拟入刊／暂未入选分组，展示投稿人、类型、标题、内容要点与具体取舍问题；支持显式复用私有实名映射，姓名不进入公开包，审核无需另填表。
- 新增 `editorial.py connect / prepare / build`：真实连接公开 Git 历史和私有 ledger v1，复用冻结期号、核验和计划入刊周；每期保留一份可编辑素材池，生成正文、预览及正文/侧边栏/README 审阅补丁。
- 私有工作原子落盘、保留人工编辑、源版本变化提示；公开导出按文件与字段投影，不带出成员映射、台账、凭据或私有检查明细。
- 新增 `embodied-ai-weekly-live` 七类预设及 `sections_optional`，支持省略空栏目，取消标签、分钟数及字数的额外要求；原预设保持兼容。
- **发布行为修正**：默认预演真正只读；新增 `--commit` 明确本地提交，`--push` 提交并推送。需要已有目标检出；不再自动临时 clone 或 rebase。核对 origin 和检出分支；`--allow-dirty` 保留无关暂存改动；推送不夹带其他文件的本地未发布提交。
- 修复回归脚本吞掉 Python 失败退出码的问题，增加真实 Git 发布、双库接入和公开导出行为测试。精简 SKILL 与按需参考文档，补充 Codex 安装示例。

下列为本轮之前已在 main 的 Unreleased 改进：

### Added
- **本地素材池链路**（`scripts/_pool.py`、`new_pool.py`、`pool_to_issue.py`、
  `fetch_bilibili.py`）：候选先落盘成单文件 md 池子，人工润色后用脚本确定性搬回 issue 骨架；
  `[x]` 勾选入选、`- 键：值` 字段、`- 板块：` 归类；缺字段不猜、留空交校验器。
- `scripts/fetch_bilibili.py`：抓 B 站视频标题/UP/时长（免登录 API），可 `--pool ... --section ...`
  追加到指定板块。
- 配置新增 `pool_dir`（默认 `"sources"`）与 `pool_filename`（默认 `"issue-{number}-pool.md"`）。
- 预设 `presets/embodied-ai-weekly-legacy.json`：`embodied-ai-weekly` 的**板块变体**示例
  （仅覆盖 `sections`，其余全继承）。
- `preview.py` 增加「本期统计」块（板块条目分布 + 必填字段完整度，纯 CSS，仅预览可见）。
- 工程质量：`.github/workflows/test.yml`（Python 3.9–3.12 矩阵 CI）、`tests/test_common.py` /
  `tests/test_pool.py` 单测、四份 golden、`CONTRIBUTING.md`、Issue/PR 模板。

### Changed
- `scripts/new_issue.py` 抽出 `render_document()`，供 `pool_to_issue.py` 复用，保证池骨架与
  脚手架格式逐字一致。
- `tests/run_tests.sh` 回归扩展为「单测（common + pool）+ 四 golden + 15 坏样本」。

## [0.1.0] - 2026-10-15

首个可用版本（首个公开版本为 1.0.0，待端到端演练与开源发布后打出）。

### Added
- 配置层 `scripts/_common.py`：解析链 `--config` > `$WEEKLY_CONFIG` > `weekly.config.json`
  > `extends` 预设链（深合并、环检测）> 内置中性默认；issue/frontmatter/card 解析器。
- 官方预设：`presets/minimal.json`（中性默认显式化）、
  `presets/embodied-ai-weekly.json`（具身智能周刊风格：5 板块 / 6 色 card / 三字段 / 阈值集）。
- `scripts/validate_issue.py`：校验规则 E01–E16 / W01–W05，全部配置驱动，关闭项自动跳过；
  `--strict` / `--with-history` / `--json`。
- `scripts/new_issue.py` + `scripts/next_number.py`：脚手架与自动取号（本地或 GitHub 只读）。
- `scripts/dedup_urls.py`：URL 规范化（剥跟踪参数）+ 历史比对 + `--fuzzy` 标题相似。
- `scripts/preview.py` + `assets/preview-style.css`：单文件 HTML 预览，
  card 配色按配置注入，暗色模式，未知块降级 `<pre>` + WARN。
- `scripts/fetch_arxiv.py` / `scripts/fetch_github_trends.py`：素材抓取（arXiv Atom / GitHub Search）。
- `scripts/publish.py`：两段式安全发布，默认 dry-run，`--push` 需人工确认；
  期号冲突 / 脏工作区 / rebase 冲突三重拒绝；无 force push；`.publish-history.jsonl` 审计。
- 文档：`SKILL.md`、`references/`（style-guide / workflow / publishing / presets-guide / content-sourcing）、
  `assets/card-spec.md`、`README.md`、`config.example.json`。
- 测试：`tests/run_tests.sh`（双 golden 回归 + 15 坏样本 rule id 断言）。

[Unreleased]: https://github.com/kingdream-cn/weekly-craft/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kingdream-cn/weekly-craft/releases/tag/v0.1.0
